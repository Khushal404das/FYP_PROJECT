"""
FYP Vehicle Tracking System - Core Tracking Engine
===================================================
Multi-camera vehicle tracking using:
- YOLOv8 Vehicle Detection (car, bus, motorcycle, bicycle, truck — NO humans)
- SORT tracker  (IoU-based assignment with stable integer IDs)
- Re-Identification (color histogram + feature embeddings)
- Cross-camera trajectory linking (inspired by TNT / AIC Track 1-3 repos)

Cameras available: c11, c12, c21, c22, c23, c24, c31, c32, c41, c42, c43, c51, c52, c61..c65
"""

import cv2
import numpy as np
import json
import os
import time
import hashlib
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional
from scipy.optimize import linear_sum_assignment


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR.parent.parent / "dataset"
UPLOAD_DIR = BASE_DIR.parent / "php_frontend" / "uploads"
TRACKS_DB  = BASE_DIR / "tracks_db.pkl"

# Active cameras — one per zone, running simultaneously on the same timestamps
ACTIVE_CAMERAS = ["c11", "c21", "c31", "c41", "c51", "c61"]
CAMERA_IDS = ACTIVE_CAMERAS   # alias used across the codebase

# Camera topology — direct transitions between the 6 active cameras
# c11(zone1) -> c21(zone2) -> c31(zone3) -> c41(zone4) -> c51(zone5) -> c61(zone6)
CAMERA_TOPOLOGY = {
    "c11": ["c21"],
    "c21": ["c31", "c41"],   # zone2 can branch to zone3 or zone4
    "c31": ["c41"],
    "c41": ["c51"],
    "c51": ["c61"],
    "c61": [],
}

# Expected travel time window (seconds) between the 6 active cameras.
# A cross-camera match is only accepted when the elapsed time since the
# vehicle was last seen falls inside [min_s, max_s] for that transition.
# All cameras stream simultaneously so timestamps are wall-clock aligned.
CAMERA_TRAVEL_WINDOW: dict = {
    # (from_cam, to_cam): (min_seconds, max_seconds)
    ("c11", "c21"): (3, 120),   # zone1  -> zone2
    ("c21", "c31"): (3,  90),   # zone2  -> zone3
    ("c21", "c41"): (5, 150),   # zone2  -> zone4  (shortcut route)
    ("c31", "c41"): (3,  90),   # zone3  -> zone4
    ("c41", "c51"): (3, 120),   # zone4  -> zone5
    ("c51", "c61"): (5, 180),   # zone5  -> zone6
}
DEFAULT_TRAVEL_WINDOW = (2, 300)   # fallback: 2 s – 5 min

# Minimum pixel displacement (as fraction of bbox diagonal) for a
# tracklet to be considered "moving" and eligible for cross-camera link.
MOTION_DISP_THRESHOLD = 0.15   # 15 % of the bounding-box diagonal

# Minimum number of frames a tracklet must have been observed before
# it is eligible for cross-camera ReID.
MIN_FRAMES_FOR_REID = 3


# ──────────────────────────────────────────────────────────────────────────────
# ResNet50 Temporal Attention  (AIC Track 2 UWIPL — exact architecture)
# Reference: 2019-CVPR-AIC-Track-2-UWIPL-master/Video-Person-ReID/models/ResNet.py
# ──────────────────────────────────────────────────────────────────────────────

import torch
import torch.nn as nn
import torch.nn.functional as F_torch
import torchvision
import torchvision.transforms as T_tv
from PIL import Image as _PIL_Image

# Optional fine-tuned AIC checkpoint (.pth.tar from Track 2 UWIPL Google Drive).
# Download from: https://drive.google.com/open?id=1jjwQhk8i4X12_DjCz9LlgrvL-9uKa2mE
# Place it at:   <repo>/2019-CVPR-AIC-Track-2-UWIPL-master/.../Video-Person-ReID/log/
_AIC_CKPT = (BASE_DIR.parent.parent
             / "2019-CVPR-AIC-Track-2-UWIPL-master"
             / "2019-CVPR-AIC-Track-2-UWIPL-master"
             / "Video-Person-ReID" / "log" / "checkpoint_ep300.pth.tar")


class _ResNet50TABackbone(nn.Module):
    """
    ResNet50 + Temporal Attention backbone.
    Exact implementation of ResNet50TA from AIC Track 2 UWIPL ResNet.py
    (the Track-1 variant — no surface/keypoint features needed).

    Architecture
    ────────────
    base         : ResNet50 conv1..conv5  → 2048×7×7 feature map
    attention_conv: Conv2d 2048→256, kernel [7,7]  (collapses 7×7 → 1×1)
    attention_tconv: Conv1d 256→1, kernel 3        (temporal attention)
    pooling      : weighted sum over T frames
    output       : 2048-dim L2-normalised vector
    """
    FEAT_DIM   = 2048
    MIDDLE_DIM = 256

    def __init__(self):
        super().__init__()
        resnet50 = torchvision.models.resnet50(weights="IMAGENET1K_V2")
        # Strip avgpool + fc  (same as Track 2: children()[:-2])
        self.base            = nn.Sequential(*list(resnet50.children())[:-2])
        # [7,7] kernel matches 224×224 → 7×7 feature map (as in SURFACE variant)
        self.attention_conv  = nn.Conv2d(self.FEAT_DIM, self.MIDDLE_DIM,
                                         kernel_size=7)
        self.attention_tconv = nn.Conv1d(self.MIDDLE_DIM, 1,
                                         kernel_size=3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x : [B, T, 3, H, W]
        out: [B, FEAT_DIM]  — L2-normalised
        """
        b, t = x.size(0), x.size(1)
        x = x.view(b * t, x.size(2), x.size(3), x.size(4))
        x = self.base(x)                                      # [B*T, 2048, 7, 7]

        # Temporal attention
        a = F_torch.relu(self.attention_conv(x))              # [B*T, 256, 1, 1]
        a = a.view(b, t, self.MIDDLE_DIM).permute(0, 2, 1)    # [B, 256, T]
        a = F_torch.relu(self.attention_tconv(a))             # [B, 1, T]
        a = F_torch.softmax(a.view(b, t), dim=1)              # [B, T] softmax weights

        # Spatial global average + weighted temporal sum
        x = F_torch.avg_pool2d(x, x.size()[2:])               # [B*T, 2048, 1, 1]
        x = x.view(b, t, self.FEAT_DIM)                       # [B, T, 2048]
        a = a.unsqueeze(-1).expand_as(x)                      # [B, T, 2048]
        f = torch.sum(x * a, dim=1)                           # [B, 2048]
        return F_torch.normalize(f, p=2, dim=1)               # L2 normalise


class VehicleFeatureExtractor:
    """
    Vehicle Re-Identification feature extractor — ResNet50TA.

    This is the **actual model** used by the AIC 2019 Track 2 UWIPL team
    (CVPR 2019 Workshop, 2nd place multi-camera vehicle tracking).

    Model: ResNet50 + Temporal Attention (Track 1 variant, no keypoints)
    Output: 2048-dim L2-normalised embedding per tracklet sequence (seq_len=4)

    If the fine-tuned AIC checkpoint exists at the expected path it is loaded
    automatically. Otherwise ImageNet pretrained weights are used, which are
    already far superior to colour-histogram approaches for vehicle ReID.
    """

    SEQ_LEN  = 4      # frames per tracklet sequence (same as Track 2 paper)
    IMG_SIZE = 224    # input resolution (224×224 as in paper)
    FEAT_DIM = 2048   # embedding dimensionality

    # Standard ImageNet normalisation (same as Track 2 transforms.py)
    _MEAN = [0.485, 0.456, 0.406]
    _STD  = [0.229, 0.224, 0.225]

    def __init__(self, checkpoint: Path = _AIC_CKPT):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self._transform = T_tv.Compose([
            T_tv.Resize((self.IMG_SIZE, self.IMG_SIZE)),
            T_tv.ToTensor(),
            T_tv.Normalize(mean=self._MEAN, std=self._STD),
        ])

        self._model = _ResNet50TABackbone().to(self.device)
        self._model.eval()

        if Path(str(checkpoint)).exists():
            self._load_checkpoint(checkpoint)
        else:
            print("[INFO] ResNet50TA: ImageNet weights active. "
                  f"Place AIC checkpoint at:\n       {checkpoint}")

    def _load_checkpoint(self, path):
        ckpt  = torch.load(str(path), map_location=self.device)
        state = ckpt.get("state_dict", ckpt)
        state = {k.replace("module.", ""): v for k, v in state.items()}
        own   = self._model.state_dict()
        compat = {k: v for k, v in state.items()
                  if k in own and own[k].shape == v.shape}
        own.update(compat)
        self._model.load_state_dict(own)
        print(f"[INFO] ResNet50TA checkpoint loaded ({len(compat)}/{len(own)} layers).")

    def _to_tensor(self, bgr: np.ndarray) -> torch.Tensor:
        if bgr is None or bgr.size == 0:
            return torch.zeros(3, self.IMG_SIZE, self.IMG_SIZE)
        rgb = _PIL_Image.fromarray(bgr[:, :, ::-1].copy().astype("uint8"))
        return self._transform(rgb)

    def extract(self, crops) -> np.ndarray:
        """
        Extract a 2048-dim feature from one crop or a sequence of crops.

        Args:
            crops: np.ndarray (single crop H×W×3)  OR  list of np.ndarray
        Returns:
            np.ndarray shape (2048,), dtype float32, L2-normalised
        """
        if isinstance(crops, np.ndarray) and crops.ndim == 3:
            crops = [crops]
        if not crops:
            return np.zeros(self.FEAT_DIM, dtype=np.float32)

        # Pad / truncate to SEQ_LEN (Track 2 paper always uses 4 frames)
        if len(crops) < self.SEQ_LEN:
            crops = list(crops) + [crops[-1]] * (self.SEQ_LEN - len(crops))
        else:
            crops = list(crops)[-self.SEQ_LEN:]

        seq = torch.stack([self._to_tensor(c) for c in crops]).unsqueeze(0)
        seq = seq.to(self.device)                 # [1, T, 3, H, W]

        with torch.no_grad():
            feat = self._model(seq)               # [1, 2048]
        return feat.squeeze(0).cpu().numpy().astype(np.float32)

    def similarity(self, f1: np.ndarray, f2: np.ndarray) -> float:
        """
        Cosine similarity of two L2-normalised embeddings → dot product.
        Range: [-1, 1].  Typical true-match score: 0.75–0.98.
        """
        if f1 is None or f2 is None:
            return 0.0
        n1 = float(np.linalg.norm(f1))
        n2 = float(np.linalg.norm(f2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(f1, f2) / (n1 * n2))




# ──────────────────────────────────────────────────────────────────────────────
# YOLOv8 Vehicle Detector  (humans are explicitly excluded)
# ──────────────────────────────────────────────────────────────────────────────

# COCO class IDs for vehicles only — person (0) is intentionally absent
VEHICLE_CLASS_IDS = {
    1:  "bicycle",
    2:  "car",
    3:  "motorcycle",
    5:  "bus",
    7:  "truck",
}

# Per-class box colours (BGR)
CLASS_COLORS = {
    "bicycle":    (255, 165,   0),   # orange
    "car":        ( 50, 220, 255),   # cyan-yellow
    "motorcycle": (180,   0, 255),   # purple
    "bus":        (  0, 200,  80),   # green
    "truck":      (  0, 100, 255),   # blue-orange
}
DEFAULT_BOX_COLOR = (255, 255,  50)  # fallback yellow


class YOLOVehicleDetector:
    """
    YOLOv8-based vehicle detector.
    Only returns detections whose COCO class is in VEHICLE_CLASS_IDS.
    Humans (class 0) and all other non-vehicle classes are silently dropped.
    """

    MODEL_NAME = "yolov8n.pt"   # nano — fast; swap for yolov8s/m for more accuracy

    def __init__(self, conf_thresh: float = 0.50, iou_thresh: float = 0.45):
        self._model = None
        self.conf_thresh = conf_thresh
        self.iou_thresh  = iou_thresh

    def _load(self):
        """Lazy-load YOLOv8 model on first use."""
        if self._model is None:
            try:
                from ultralytics import YOLO
                self._model = YOLO(self.MODEL_NAME)
                print(f"[INFO] YOLOv8 model '{self.MODEL_NAME}' loaded.")
            except ImportError:
                raise RuntimeError(
                    "ultralytics is not installed. "
                    "Run: pip install ultralytics"
                )

    def detect(self, frame: np.ndarray) -> list:
        """
        Run inference on a BGR frame.

        Returns a list of dicts:
            [
              {"bbox": (x, y, w, h), "class_id": int,
               "class_name": str, "conf": float},
              ...
            ]
        where bbox uses (x, y, w, h) format (top-left corner + size).
        Humans and false positive non-vehicles are filtered out.
        """
        self._load()
        results = self._model(
            frame,
            conf=self.conf_thresh,
            iou=self.iou_thresh,
            imgsz=640,
            verbose=False,
        )[0]

        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in VEHICLE_CLASS_IDS:
                continue   # skip person, animal, or anything non-vehicle

            conf = float(box.conf[0])
            if conf < self.conf_thresh:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w, h = x2 - x1, y2 - y1

            # Filter out tiny noise (shadows, ripples) and extreme aspect ratios (fences, wires)
            if w < 28 or h < 24:
                continue
            if w * h < 750:
                continue
            aspect = w / max(1, h)
            if aspect < 0.22 or aspect > 4.5:
                continue

            detections.append({
                "bbox":       (x1, y1, w, h),
                "class_id":   cls_id,
                "class_name": VEHICLE_CLASS_IDS[cls_id],
                "conf":       conf,
            })
        return detections


# ──────────────────────────────────────────────────────────────────────────────
# SORT tracker  (IoU-based + linear assignment — no deep features needed)
# ──────────────────────────────────────────────────────────────────────────────

class SORTTracker:
    """
    Lightweight SORT (Simple Online and Realtime Tracking) implementation.
    Associates detections frame-to-frame using IoU + Hungarian algorithm.
    Each confirmed detection is assigned a stable integer ID.

    Output per frame: list of
        {"track_id": int, "bbox": (x,y,w,h),
         "class_name": str, "conf": float, "age": int}
    """

    def __init__(self, max_age: int = 25, min_hits: int = 2,
                 iou_thresh: float = 0.25):
        self.max_age    = max_age     # frames without a match before track dies
        self.min_hits   = min_hits    # frames needed before a track is "confirmed"
        self.iou_thresh = iou_thresh
        self._tracks: list = []       # list of _Track objects
        self._next_id = 1
        self.frame_count = 0

    # ── internal track object ──────────────────────────────────────────────
    class _Track:
        def __init__(self, track_id: int, det: dict):
            self.track_id   = track_id
            self.bbox       = det["bbox"]        # (x,y,w,h)
            self.class_name = det["class_name"]
            self.conf       = det["conf"]
            self.age        = 0                  # frames since last match
            self.hits       = 1                  # total matched frames
            self.active     = True

        def predict(self):
            """Simple constant-velocity prediction: keep same position."""
            self.age += 1

        def update(self, det: dict):
            self.bbox       = det["bbox"]
            self.class_name = det["class_name"]
            self.conf       = det["conf"]
            self.age        = 0
            self.hits      += 1

    # ── IoU helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _iou(b1, b2) -> float:
        """Compute IoU between two (x,y,w,h) boxes."""
        x1, y1, w1, h1 = b1
        x2, y2, w2, h2 = b2
        ix1 = max(x1, x2);         iy1 = max(y1, y2)
        ix2 = min(x1+w1, x2+w2);   iy2 = min(y1+h1, y2+h2)
        inter = max(0, ix2-ix1) * max(0, iy2-iy1)
        union = w1*h1 + w2*h2 - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _iou_matrix(tracks, dets) -> np.ndarray:
        mat = np.zeros((len(tracks), len(dets)), dtype=np.float32)
        for i, trk in enumerate(tracks):
            for j, det in enumerate(dets):
                mat[i, j] = SORTTracker._iou(trk.bbox, det["bbox"])
        return mat

    # ── Main update step ───────────────────────────────────────────────────
    def update(self, detections: list) -> list:
        """
        Call once per frame with the list of dicts from YOLOVehicleDetector.
        Returns confirmed active tracks as a list of dicts.
        """
        self.frame_count += 1

        # 1. Predict new positions (no-op for constant-position model)
        for trk in self._tracks:
            trk.predict()

        # 2. Build IoU cost matrix and run Hungarian algorithm
        active_trks = [t for t in self._tracks if t.age <= self.max_age]
        matched_trk  = set()
        matched_det  = set()

        if active_trks and detections:
            iou_mat = self._iou_matrix(active_trks, detections)
            # Maximise IoU == minimise negative IoU
            row_ind, col_ind = linear_sum_assignment(-iou_mat)
            for r, c in zip(row_ind, col_ind):
                if iou_mat[r, c] >= self.iou_thresh:
                    active_trks[r].update(detections[c])
                    matched_trk.add(r)
                    matched_det.add(c)

        # 3. Create new tracks for unmatched detections
        for j, det in enumerate(detections):
            if j not in matched_det:
                new_trk = SORTTracker._Track(self._next_id, det)
                self._next_id += 1
                self._tracks.append(new_trk)

        # 4. Remove dead tracks
        self._tracks = [t for t in self._tracks if t.age <= self.max_age]

        # 5. Return confirmed active tracks (age <= 2 bridges 1-2 frame detection misses without flicker)
        out = []
        for trk in self._tracks:
            if trk.hits >= self.min_hits and trk.age <= 2:
                out.append({
                    "track_id":   trk.track_id,
                    "bbox":       trk.bbox,
                    "class_name": trk.class_name,
                    "conf":       round(trk.conf, 3),
                    "age":        trk.age,
                })
        return out

    def reset(self):
        self._tracks = []
        self.frame_count = 0


# ──────────────────────────────────────────────────────────────────────────────
# Drawing utilities — Clean Modern CV Visual Style
# ──────────────────────────────────────────────────────────────────────────────

def _gid_color(gid: int) -> tuple:
    """
    Generate a unique, vivid BGR color for a global vehicle ID.
    Uses a prime-multiplier hue spread so adjacent IDs look very different.
    """
    hue = (gid * 47 + 30) % 180           # spread hues with prime multiplier
    sat = min(255, 220 + (gid % 3) * 10)  # high saturation 220-240
    val = min(255, 210 + (gid % 4) * 10)  # bright value 210-250
    hsv = np.uint8([[[hue, sat, val]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0][0]
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))


def draw_tracked_frame(
    frame: np.ndarray,
    tracked: list,
    box_thickness: int = 2,
    font_scale: float = 0.55,
) -> np.ndarray:
    """
    Draw crisp, tightly-aligned bounding boxes matching the reference benchmark visual:
      - Crisp 2px bounding box outline in the track's persistent color
      - Global ID number horizontally centered directly above the bounding box
      - Exact matching color for both ID and box outline
      - Subtle drop shadow / outline so the ID is readable on all backgrounds
      - Zero clutter, clean aligned geometry
    """
    for item in tracked:
        tid    = item["track_id"]
        gid    = item.get("global_id", tid)
        x, y, w, h = item["bbox"]

        if w < 12 or h < 12:
            continue

        color = _gid_color(gid)

        # ── 1. Crisp, tightly-aligned bounding box ──
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, box_thickness, cv2.LINE_AA)

        # ── 2. Global ID number centered directly above the bounding box ──
        id_text = str(gid)
        scale = max(0.50, min(0.75, w / 110.0))
        thick = 2
        (tw, th), baseline = cv2.getTextSize(id_text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)

        id_x = max(2, x + (w - tw) // 2)
        id_y = max(th + 4, y - 6)

        # High-contrast outline then matching colored text
        cv2.putText(frame, id_text, (id_x, id_y),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
        cv2.putText(frame, id_text, (id_x, id_y),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)

    return frame


# ──────────────────────────────────────────────────────────────────────────────
# Single-camera tracker (IoU-based tracklet association)
# ──────────────────────────────────────────────────────────────────────────────

class SingleCameraTracker:
    """
    Maintains tracklets within a single camera view.
    Associates detections across frames using IoU + ReID similarity.
    Inspired by the TNT tracklet approach.

    Motion detection
    ----------------
    Each tracklet records its bbox history.  is_moving() measures the
    Euclidean displacement between the centre of the first observed bbox
    and the centre of the most-recent bbox, normalised by the diagonal
    of the first bbox.  Only tracklets that have moved more than
    MOTION_DISP_THRESHOLD are considered eligible for cross-camera ReID,
    preventing parked/static vehicles from polluting the global track DB.
    """

    def __init__(self, camera_id: str, extractor: VehicleFeatureExtractor):
        self.camera_id  = camera_id
        self.extractor  = extractor
        self.tracklets  = {}   # track_id -> dict
        self.next_id    = 1
        self.iou_thresh = 0.3
        self.max_age    = 30   # frames before a track is removed

    # ── helpers ────────────────────────────────────────────────────────────
    def _iou(self, b1, b2) -> float:
        x1, y1, w1, h1 = b1
        x2, y2, w2, h2 = b2
        xi1 = max(x1, x2);  yi1 = max(y1, y2)
        xi2 = min(x1+w1, x2+w2);  yi2 = min(y1+h1, y2+h2)
        inter = max(0, xi2-xi1) * max(0, yi2-yi1)
        union = w1*h1 + w2*h2 - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _bbox_centre(bbox):
        x, y, w, h = bbox
        return (x + w / 2.0, y + h / 2.0)

    @staticmethod
    def _bbox_diag(bbox):
        _, _, w, h = bbox
        return float(np.sqrt(w * w + h * h)) if (w > 0 and h > 0) else 1.0

    def is_moving(self, trk: dict) -> bool:
        """
        Return True when the tracklet has moved enough to be considered
        a genuinely moving vehicle (not a parked car or detection noise).

        Motion is measured as the displacement between the centre of the
        *first* recorded bbox and the centre of the *latest* bbox,
        normalised by the diagonal of the first bbox.
        """
        bboxes = trk.get("bboxes", [])
        if len(bboxes) < 2:
            return False
        cx0, cy0 = self._bbox_centre(bboxes[0])
        cx1, cy1 = self._bbox_centre(bboxes[-1])
        diag = self._bbox_diag(bboxes[0])
        displacement = float(np.sqrt((cx1 - cx0) ** 2 + (cy1 - cy0) ** 2))
        return (displacement / diag) >= MOTION_DISP_THRESHOLD

    # ── main update step ───────────────────────────────────────────────────
    def update(self, frame: np.ndarray, detections: list, frame_idx: int):
        matched   = set()
        used_dets = set()

        # Match existing tracklets
        for tid, trk in list(self.tracklets.items()):
            best_iou  = self.iou_thresh
            best_det  = None
            best_didx = -1
            for di, det in enumerate(detections):
                if di in used_dets:
                    continue
                iou = self._iou(trk["bbox"], det)
                if iou > best_iou:
                    best_iou = iou
                    best_det = det
                    best_didx = di

            if best_det is not None:
                x, y, w, h = best_det
                crop = frame[max(0, y):y + h, max(0, x):x + w]

                # Buffer crops for temporal-attention sequence (Track 2 paper: seq_len=4)
                trk.setdefault("crop_buf", [])
                trk["crop_buf"].append(crop)
                if len(trk["crop_buf"]) > VehicleFeatureExtractor.SEQ_LEN:
                    trk["crop_buf"].pop(0)

                # Re-extract feature from the buffered sequence every SEQ_LEN frames
                # (temporal attention benefits from seeing a sequence, not one crop)
                if len(trk["frames"]) % VehicleFeatureExtractor.SEQ_LEN == 0 or trk["feature"] is None:
                    new_feat = self.extractor.extract(trk["crop_buf"])
                    if trk.get("feature") is not None:
                        sim = self.extractor.similarity(trk["feature"], new_feat)
                        if sim > 0.50:   # only update if still same vehicle
                            trk["feature"] = trk["feature"] * 0.55 + new_feat * 0.45
                    else:
                        trk["feature"] = new_feat

                trk["bbox"]      = best_det
                trk["age"]       = 0
                trk["frames"].append(frame_idx)
                trk["bboxes"].append(best_det)
                trk["last_seen"] = frame_idx
                trk["moving"]    = self.is_moving(trk)
                matched.add(tid)
                used_dets.add(best_didx)
            else:
                trk["age"] += 1

        # Create new tracklets for unmatched detections
        for di, det in enumerate(detections):
            if di in used_dets:
                continue
            x, y, w, h = det
            crop    = frame[max(0, y):y + h, max(0, x):x + w]
            # Start crop buffer and extract first feature
            crop_buf = [crop]
            feature  = self.extractor.extract(crop_buf)
            tid = self.next_id
            self.next_id += 1
            self.tracklets[tid] = {
                "id":         tid,
                "camera":     self.camera_id,
                "bbox":       det,
                "age":        0,
                "frames":     [frame_idx],
                "bboxes":     [det],
                "crop_buf":   crop_buf,       # rolling buffer for ResNet50TA
                "feature":    feature,
                "first_seen": frame_idx,
                "last_seen":  frame_idx,
                "global_id":  None,
                "moving":     False,
            }

        # Remove stale tracklets
        to_remove = [tid for tid, trk in self.tracklets.items()
                     if trk["age"] > self.max_age]
        for tid in to_remove:
            del self.tracklets[tid]

        return self.tracklets


# ──────────────────────────────────────────────────────────────────────────────
# Cross-Camera Re-Identification (Transition model)
# ──────────────────────────────────────────────────────────────────────────────

class CrossCameraReID:
    """
    Matches tracklets across cameras using:
    1. Feature similarity (ReID embeddings)  — cosine similarity
    2. Camera transition topology plausibility  — must be a known next-hop
    3. Temporal gating  — elapsed time must fall inside the expected
       travel-time window for the (prev_cam → cur_cam) transition pair
    4. Motion gate  — only moving tracklets trigger cross-camera linking
    5. Frame-count gate  — tracklet must have been seen for at least
       MIN_FRAMES_FOR_REID frames to avoid noisy single-frame blips
    6. Sighting deduplication  — suppresses repeat sightings from the
       same camera within a short time window to avoid log bloat
    Inspired by AIC Track 1 Transition-Model.
    """

    # Seconds within which a repeated sighting on the same camera is ignored
    SAME_CAM_DEDUP_WINDOW = 2.0
    # Higher threshold for cross-camera links (vs. same-camera continuation)
    CROSS_CAM_THRESHOLD   = 0.70
    # Minimum similarity required before updating the feature EMA
    FEATURE_UPDATE_MIN_SIM = 0.75

    def __init__(self, extractor: VehicleFeatureExtractor, threshold: float = 0.65):
        self.extractor  = extractor
        self.threshold  = threshold          # same-camera / within-gap threshold
        self.global_tracks: dict = {}        # global_id -> {camera, feature, timestamp, ...}
        self.next_gid   = 1

    # ── public API ─────────────────────────────────────────────────────────

    def assign_global_id(
        self,
        tracklet: dict,
        camera_id: str,
        timestamp: float,
        is_moving: bool = False,
    ) -> int:
        """
        Try to match *tracklet* to an existing global ID, or assign a new one.

        Parameters
        ----------
        tracklet   : dict with at least 'feature', 'bbox', 'frames' keys
        camera_id  : camera the tracklet was detected on
        timestamp  : wall-clock seconds (frame_idx / fps) of this sighting
        is_moving  : True when the SingleCameraTracker flagged this tracklet
                     as a moving vehicle — required for cross-camera linking
        """
        feature = tracklet.get("feature")
        n_frames = len(tracklet.get("frames", []))

        # No feature → register as brand-new (cannot match anything)
        if feature is None:
            return self._new_global(tracklet, camera_id, timestamp)

        # ── look for the best matching existing global track ───────────────
        best_gid = None
        best_sim = self.threshold       # minimum bar for any match

        for gid, gtrk in self.global_tracks.items():
            prev_cam  = gtrk.get("last_camera", "")
            last_seen = gtrk.get("last_seen", 0.0)
            elapsed   = timestamp - last_seen

            # ── 1. Same-camera continuation (vehicle still in same view) ──
            if prev_cam == camera_id:
                # Accept continuation only when seen again quickly (<30 s)
                if elapsed > 30.0:
                    continue
                # Lower same-camera threshold; no motion requirement
                sim = self.extractor.similarity(feature, gtrk["feature"])
                if sim > best_sim:
                    best_sim = sim
                    best_gid = gid
                continue

            # ── 2. Cross-camera link — stricter requirements ───────────────

            # 2a. Topology: current camera must be a valid next-hop
            if prev_cam and camera_id not in CAMERA_TOPOLOGY.get(prev_cam, []):
                continue

            # 2b. Temporal gate: elapsed time must fit the travel window
            win_min, win_max = CAMERA_TRAVEL_WINDOW.get(
                (prev_cam, camera_id), DEFAULT_TRAVEL_WINDOW
            )
            if not (win_min <= elapsed <= win_max):
                continue

            # 2c. Motion gate: only link if the new tracklet is moving
            if not is_moving:
                continue

            # 2d. Frame-count gate: tracklet must be mature enough
            if n_frames < MIN_FRAMES_FOR_REID:
                continue

            # 2e. Feature similarity — use the stricter cross-camera bar
            sim = self.extractor.similarity(feature, gtrk["feature"])
            if sim > max(best_sim, self.CROSS_CAM_THRESHOLD):
                best_sim = sim
                best_gid = gid

        # ── commit the match (or create a new global track) ──────────────
        if best_gid is not None:
            self._update_global(best_gid, feature, camera_id, timestamp,
                                tracklet.get("bbox"), best_sim)
            return best_gid
        else:
            return self._new_global(tracklet, camera_id, timestamp)

    # ── internal helpers ───────────────────────────────────────────────────

    def _update_global(
        self,
        gid: int,
        feature: np.ndarray,
        camera_id: str,
        timestamp: float,
        bbox,
        sim: float,
    ):
        """Update an existing global track after a successful match."""
        gt = self.global_tracks[gid]

        # Feature EMA — only when the match is confident enough to avoid drift
        if sim >= self.FEATURE_UPDATE_MIN_SIM:
            gt["feature"] = gt["feature"] * 0.6 + feature * 0.4

        gt["last_camera"] = camera_id
        gt["last_seen"]   = timestamp
        gt["cameras"].add(camera_id)

        # Sighting deduplication: skip if same camera was logged very recently
        sightings = gt["sightings"]
        if sightings:
            last_s = sightings[-1]
            if (last_s["camera"] == camera_id and
                    abs(timestamp - last_s["timestamp"]) < self.SAME_CAM_DEDUP_WINDOW):
                return   # duplicate — skip appending

        sightings.append({
            "camera":    camera_id,
            "timestamp": timestamp,
            "bbox":      bbox,
        })

    def _new_global(self, tracklet: dict, camera_id: str, timestamp: float) -> int:
        """Register a brand-new global track and return its ID."""
        gid = self.next_gid
        self.next_gid += 1
        self._register(gid, tracklet, camera_id, timestamp)
        return gid

    def _register(self, gid: int, tracklet: dict, camera_id: str, timestamp: float):
        self.global_tracks[gid] = {
            "global_id":   gid,
            "feature":     tracklet.get("feature",
                                        np.zeros(160, dtype=np.float32)),
            "last_camera": camera_id,
            "first_seen":  timestamp,
            "last_seen":   timestamp,
            "cameras":     {camera_id},
            "sightings":   [{
                "camera":    camera_id,
                "timestamp": timestamp,
                "bbox":      tracklet.get("bbox"),
            }],
        }

    def get_journey(self, global_id: int) -> list:
        """Return ordered list of camera sightings for a given global vehicle ID."""
        if global_id not in self.global_tracks:
            return []
        sightings = sorted(
            self.global_tracks[global_id]["sightings"],
            key=lambda s: s["timestamp"]
        )
        return sightings


# ──────────────────────────────────────────────────────────────────────────────
# Query matcher — matches a query image or description to tracked vehicles
# ──────────────────────────────────────────────────────────────────────────────

class VehicleQueryMatcher:
    """
    Given a query (image crop or text description), find the most similar
    globally tracked vehicle and return its cross-camera journey.
    """

    def __init__(self, extractor: VehicleFeatureExtractor, reid: CrossCameraReID):
        self.extractor = extractor
        self.reid      = reid

    def match_by_image(self, query_image: np.ndarray, top_k: int = 5) -> list:
        """Return top-k matching global vehicle IDs with similarity scores."""
        q_feat = self.extractor.extract(query_image)
        results = []
        for gid, gtrk in self.reid.global_tracks.items():
            sim = self.extractor.similarity(q_feat, gtrk["feature"])
            results.append({
                "global_id":   gid,
                "similarity":  round(float(sim), 4),
                "cameras":     sorted(gtrk["cameras"]),
                "first_seen":  gtrk["first_seen"],
                "last_seen":   gtrk["last_seen"],
                "sightings":   self.reid.get_journey(gid),
            })
        results.sort(key=lambda r: r["similarity"], reverse=True)
        return results[:top_k]

    def match_by_description(self, description: dict, top_k: int = 5) -> list:
        """
        Match by text description fields:
          color, vehicle_type, plate_number, camera_id
        """
        color        = description.get("color", "").lower()
        vtype        = description.get("vehicle_type", "").lower()
        plate        = description.get("plate_number", "").strip().upper()
        target_cam   = description.get("camera_id", "").lower()

        results = []
        for gid, gtrk in self.reid.global_tracks.items():
            score = 0.0
            meta  = gtrk.get("meta", {})

            if color and meta.get("color", "").lower() == color:
                score += 0.4
            if vtype and meta.get("vehicle_type", "").lower() == vtype:
                score += 0.3
            if plate and meta.get("plate", "").upper() == plate:
                score += 1.0   # exact plate match
            if target_cam and target_cam in gtrk["cameras"]:
                score += 0.3

            results.append({
                "global_id":  gid,
                "score":      round(score, 4),
                "cameras":    sorted(gtrk["cameras"]),
                "first_seen": gtrk["first_seen"],
                "last_seen":  gtrk["last_seen"],
                "sightings":  self.reid.get_journey(gid),
                "meta":       meta,
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        return [r for r in results[:top_k] if r["score"] > 0]


# ──────────────────────────────────────────────────────────────────────────────
# Main processing pipeline
# ──────────────────────────────────────────────────────────────────────────────

class VehicleTrackingPipeline:
    """
    Orchestrates:
    1. Per-camera detection + single-camera tracking
    2. Cross-camera ReID and global ID assignment
    3. Query matching (image or description)
    4. Persistent state (pickle DB)
    """

    def __init__(self):
        self.extractor  = VehicleFeatureExtractor()
        self.reid       = CrossCameraReID(self.extractor)
        self.matcher    = VehicleQueryMatcher(self.extractor, self.reid)
        self.cam_trackers: dict = {}
        self._load_state()

    def _load_state(self):
        if TRACKS_DB.exists():
            try:
                with open(TRACKS_DB, "rb") as f:
                    state = pickle.load(f)
                self.reid.global_tracks = state.get("global_tracks", {})
                self.reid.next_gid      = state.get("next_gid", 1)
                print(f"[INFO] Loaded {len(self.reid.global_tracks)} tracked vehicles from DB.")
            except Exception as e:
                print(f"[WARN] Could not load state: {e}")

    def _save_state(self):
        with open(TRACKS_DB, "wb") as f:
            pickle.dump({
                "global_tracks": self.reid.global_tracks,
                "next_gid":      self.reid.next_gid,
            }, f)

    def get_or_create_tracker(self, camera_id: str) -> SingleCameraTracker:
        if camera_id not in self.cam_trackers:
            self.cam_trackers[camera_id] = SingleCameraTracker(camera_id, self.extractor)
        return self.cam_trackers[camera_id]

    def process_camera_frame(
        self,
        camera_id: str,
        frame: np.ndarray,
        frame_idx: int,
        timestamp: float,
        draw_boxes: bool = False,
    ):
        """
        Process one frame from one camera.

        Returns (tracked_list, annotated_frame):
          - tracked_list : list of track dicts from SORTTracker
          - annotated_frame : frame with boxes+IDs drawn (copy) if draw_boxes=True,
                              else the original frame unchanged.
        """
        cam_state  = self._get_cam_state(camera_id)
        yolo       = cam_state["detector"]
        sort       = cam_state["sort"]
        sc_tracker = self.get_or_create_tracker(camera_id)

        # --- YOLOv8 detection (vehicles only, no humans) ---
        detections = yolo.detect(frame)

        # --- SORT tracking ---
        tracked = sort.update(detections)

        # --- Feed into SingleCameraTracker (motion detection + feature EMA) ---
        legacy_dets = [item["bbox"] for item in tracked]
        sc_tracklets = sc_tracker.update(frame, legacy_dets, frame_idx)

        # Build a quick lookup: bbox -> tracklet (for motion flag)
        def _bbox_key(b):
            return (int(b[0]), int(b[1]), int(b[2]), int(b[3]))
        sc_by_bbox = {_bbox_key(t["bbox"]): t for t in sc_tracklets.values()}

        # --- Cross-camera ReID: assign global IDs (cached per tracklet) ---
        for item in tracked:
            bk = _bbox_key(item["bbox"])
            sc_trk = sc_by_bbox.get(bk)

            gid = sc_trk.get("global_id") if sc_trk else None
            is_moving = sc_trk.get("is_moving", False) if sc_trk else False

            if gid is None and item["age"] == 0:
                # First time assigning global_id for this tracklet
                feature = sc_trk.get("feature") if sc_trk else None
                if feature is None:
                    x, y, w, h = item["bbox"]
                    crop = frame[max(0, y):y + h, max(0, x):x + w]
                    feature = self.extractor.extract(crop)
                    if sc_trk is not None:
                        sc_trk["feature"] = feature

                trk_stub = {
                    "id":      item["track_id"],
                    "bbox":    item["bbox"],
                    "feature": feature,
                    "frames":  sc_trk.get("frames", [0]) if sc_trk else [0],
                }

                is_moving = (sc_trk.get("moving", False) or sc_tracker.is_moving(sc_trk)) if sc_trk else False
                gid = self.reid.assign_global_id(
                    trk_stub, camera_id, timestamp, is_moving=is_moving
                )
                if sc_trk is not None:
                    sc_trk["global_id"] = gid
                    sc_trk["is_moving"] = is_moving

            item["global_id"] = gid if gid is not None else item["track_id"]
            item["is_moving"] = is_moving

        # --- Optional annotation ---
        out_frame = draw_tracked_frame(frame.copy(), tracked) if draw_boxes else frame

        return tracked, out_frame

    def _get_cam_state(self, camera_id: str) -> dict:
        """Return (or create) per-camera detector + SORT tracker."""
        if not hasattr(self, "_cam_states"):
            self._cam_states: dict = {}
        if camera_id not in self._cam_states:
            self._cam_states[camera_id] = {
                "detector": YOLOVehicleDetector(),
                "sort":     SORTTracker(),
            }
        return self._cam_states[camera_id]

    def process_video_segment(
        self,
        camera_id: str,
        video_path: str,
        max_frames: int = 300,
        sample_every: int = 5,
        draw_boxes: bool = False,
        output_video: Optional[str] = None,
    ):
        """
        Process a segment of a camera video and update global tracks.

        Args:
            camera_id    : Camera ID string, e.g. 'c21'.
            video_path   : Path to source .mp4 file.
            max_frames   : Maximum number of sampled frames to process.
            sample_every : Process every N-th frame.
            draw_boxes   : If True, annotate frames with bounding boxes + IDs.
            output_video : If given, write annotated frames to this .mp4 path.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": f"Cannot open video: {video_path}"}

        fps       = cap.get(cv2.CAP_PROP_FPS) or 25.0
        orig_w    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_idx = 0
        processed = 0

        # Optional video writer
        writer = None
        if output_video and draw_boxes:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_video, fourcc, fps, (orig_w, orig_h))

        print(f"[INFO] Processing camera {camera_id}: {video_path}")
        while processed < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if frame_idx % sample_every != 0:
                continue

            timestamp = frame_idx / fps
            tracked, out_frame = self.process_camera_frame(
                camera_id, frame, frame_idx, timestamp, draw_boxes=draw_boxes
            )
            processed += 1

            if writer and draw_boxes:
                writer.write(out_frame)

            if processed % 20 == 0:
                print(
                    f"  [cam {camera_id}] frame {frame_idx} "
                    f"— {len(tracked)} vehicles tracked"
                )

        cap.release()
        if writer:
            writer.release()

        self._save_state()
        print(
            f"[INFO] Done — camera {camera_id}. "
            f"Total global tracks: {len(self.reid.global_tracks)}"
        )
        return {
            "camera_id":        camera_id,
            "frames_processed": processed,
            "global_tracks":    len(self.reid.global_tracks),
        }

    def query_image(self, image_path: str, top_k: int = 5) -> dict:
        """Accept a query image and return matched vehicle journeys."""
        img = cv2.imread(image_path)
        if img is None:
            return {"error": "Cannot read image", "results": []}

        matches = self.matcher.match_by_image(img, top_k=top_k)
        return {
            "query_type": "image",
            "query_path": image_path,
            "matches":    matches,
            "total_tracked": len(self.reid.global_tracks),
        }

    def query_description(self, description: dict, top_k: int = 5) -> dict:
        """Accept a text description and return matched vehicle journeys."""
        matches = self.matcher.match_by_description(description, top_k=top_k)
        return {
            "query_type":  "description",
            "description": description,
            "matches":     matches,
            "total_tracked": len(self.reid.global_tracks),
        }

    def get_all_tracks_summary(self) -> dict:
        """Return summary of all tracked vehicles."""
        tracks = []
        for gid, gtrk in self.reid.global_tracks.items():
            tracks.append({
                "global_id":  gid,
                "cameras":    sorted(gtrk["cameras"]),
                "sightings":  len(gtrk["sightings"]),
                "first_seen": gtrk["first_seen"],
                "last_seen":  gtrk["last_seen"],
            })
        tracks.sort(key=lambda t: t["global_id"])
        return {
            "total": len(tracks),
            "tracks": tracks,
            "cameras": CAMERA_IDS,
            "topology": CAMERA_TOPOLOGY,
        }

    def get_vehicle_journey(self, global_id: int) -> dict:
        """Return complete journey of a single vehicle across cameras."""
        if global_id not in self.reid.global_tracks:
            return {"error": f"Global ID {global_id} not found"}

        gtrk     = self.reid.global_tracks[global_id]
        sightings = self.reid.get_journey(global_id)

        # Build route
        seen_cameras = [s["camera"] for s in sightings]
        route = []
        for i, cam in enumerate(seen_cameras):
            route.append({
                "step":       i + 1,
                "camera":     cam,
                "timestamp":  sightings[i]["timestamp"],
                "bbox":       sightings[i].get("bbox"),
                "next_cameras": CAMERA_TOPOLOGY.get(cam, []),
            })

        return {
            "global_id":  global_id,
            "cameras":    sorted(gtrk["cameras"]),
            "route":      route,
            "first_seen": gtrk["first_seen"],
            "last_seen":  gtrk["last_seen"],
            "total_sightings": len(sightings),
        }


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="FYP Vehicle Tracking System")
    sub    = parser.add_subparsers(dest="cmd")

    # process-video command
    pv = sub.add_parser("process-video", help="Process camera video")
    pv.add_argument("--camera",  required=True, help="Camera ID, e.g. c21")
    pv.add_argument("--video",   required=True, help="Path to .mp4 file")
    pv.add_argument("--frames",  type=int, default=300)
    pv.add_argument("--sample",  type=int, default=5)

    # query-image command
    qi = sub.add_parser("query-image", help="Query by vehicle image")
    qi.add_argument("--image",  required=True)
    qi.add_argument("--top",    type=int, default=5)

    # query-description command
    qd = sub.add_parser("query-desc", help="Query by description")
    qd.add_argument("--color",    default="")
    qd.add_argument("--type",     default="")
    qd.add_argument("--plate",    default="")
    qd.add_argument("--camera",   default="")
    qd.add_argument("--top",      type=int, default=5)

    # summary command
    sub.add_parser("summary", help="Show all tracked vehicles")

    args = parser.parse_args()
    pipeline = VehicleTrackingPipeline()

    if args.cmd == "process-video":
        result = pipeline.process_video_segment(args.camera, args.video, args.frames, args.sample)
        print(json.dumps(result, indent=2))

    elif args.cmd == "query-image":
        result = pipeline.query_image(args.image, args.top)
        print(json.dumps(result, indent=2, default=str))

    elif args.cmd == "query-desc":
        desc = {"color": args.color, "vehicle_type": args.type,
                "plate_number": args.plate, "camera_id": args.camera}
        result = pipeline.query_description(desc, args.top)
        print(json.dumps(result, indent=2, default=str))

    elif args.cmd == "summary":
        result = pipeline.get_all_tracks_summary()
        print(json.dumps(result, indent=2, default=str))

    else:
        parser.print_help()
