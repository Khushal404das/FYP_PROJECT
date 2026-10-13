"""
vehicle_model.py -- Pure Python/OpenCV Vehicle Detection, Feature Extraction & Cross-Camera ReID
================================================================================================
No YOLO, no deep learning frameworks required.
Dependencies: opencv-python, numpy, scipy

Pipeline per camera frame:
  1. VehicleDetector   -- MOG2 background subtraction + contour filtering -> bounding boxes
  2. FeatureExtractor  -- color name, HSV histogram, vehicle type (shape-based), size category
  3. CentroidTracker   -- Hungarian-algorithm local per-camera tracker -> stable local IDs
  4. CrossCameraReID   -- cosine similarity on combined feature vectors -> persistent Global IDs
  5. CameraScorer      -- view quality score (0-1) for intelligent camera switching
  6. CameraPipeline    -- wraps all above for one camera stream

Usage:
    python vehicle_model.py                           # run built-in self-test
    python vehicle_model.py --video path/to/video.mp4 # test on a real video
"""

import os
import sys
import cv2
import numpy as np
from collections import OrderedDict
from scipy.spatial import distance as dist
from scipy.optimize import linear_sum_assignment
from typing import Dict, List, Optional, Tuple


# ===============================================================================
# CONSTANTS
# ===============================================================================

# OpenCV HSV hue is 0-179.  Maps dominant hue -> human-readable color name.
COLOR_HUE_MAP: List[Tuple[int, int, str]] = [
    (0,   10,  "red"),
    (10,  20,  "orange"),
    (20,  33,  "yellow"),
    (33,  85,  "green"),
    (85,  100, "cyan"),
    (100, 130, "blue"),
    (130, 160, "purple"),
    (160, 180, "red"),      # wrap-around red
]

# BGR colors for drawing each vehicle type
TYPE_DRAW_COLORS: Dict[str, Tuple[int, int, int]] = {
    "car":        (0,   230,   0),
    "truck":      (0,   165, 255),
    "bus":        (50,  200, 255),
    "motorcycle": (255,   0, 200),
    "unknown":    (160, 160, 160),
}


# ===============================================================================
# 1. VEHICLE DETECTOR
# ===============================================================================

class VehicleDetector:
    """
    Detects moving vehicles using MOG2 background subtraction.

    Steps:
      1. Down-scale frame for fast background modelling
      2. Apply MOG2 -> foreground mask
      3. Remove shadow pixels (value=127), keep only foreground (255)
      4. Morphological close + dilate to fill gaps
      5. Find external contours, filter by area and aspect ratio
      6. Non-maximum suppression to remove overlapping boxes
      7. Scale boxes back to original frame size

    Returns list of [x, y, w, h] bounding boxes.
    """

    def __init__(
        self,
        min_area: int        = 2000,
        max_area: int        = 160000,
        history: int         = 300,
        var_threshold: int   = 40,
        learning_rate: float = 0.004,
    ):
        self.min_area      = min_area
        self.max_area      = max_area
        self.learning_rate = learning_rate

        self._bg = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=True,       # shadows -> 127, ignored below
        )

        # Morphological structuring elements
        self._k_close  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        self._k_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,  5))

    def detect(self, frame: np.ndarray) -> List[List[int]]:
        """
        Detect vehicles in a BGR frame.

        Args:
            frame: BGR image (any resolution)
        Returns:
            list of [x, y, w, h] bounding boxes in original frame coordinates
        """
        fh, fw = frame.shape[:2]

        # Down-scale to at most 800px wide for speed
        scale  = min(1.0, 800.0 / max(fw, 1))
        small  = cv2.resize(frame, (int(fw * scale), int(fh * scale)))

        # Background subtraction
        fg = self._bg.apply(small, learningRate=self.learning_rate)

        # Remove shadow pixels
        _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)

        # Morphological cleanup
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE,  self._k_close)
        fg = cv2.dilate(fg, self._k_dilate, iterations=2)

        contours, _ = cv2.findContours(
            fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        inv = 1.0 / max(scale, 1e-6)
        boxes: List[List[int]] = []

        for cnt in contours:
            area_s = cv2.contourArea(cnt)
            area   = area_s * inv * inv

            if not (self.min_area <= area <= self.max_area):
                continue

            xs, ys, ws, hs = cv2.boundingRect(cnt)

            # Scale back to original coords
            x  = int(xs * inv)
            y  = int(ys * inv)
            bw = int(ws * inv)
            bh = int(hs * inv)

            # Clamp to frame
            x  = max(0, min(x,  fw - 1))
            y  = max(0, min(y,  fh - 1))
            bw = min(bw, fw - x)
            bh = min(bh, fh - y)

            # Aspect ratio filter: vehicles are wider than tall in most CCTV views
            aspect = bw / max(bh, 1)
            if aspect < 0.30 or aspect > 6.5:
                continue

            boxes.append([x, y, bw, bh])

        return self._nms(boxes, iou_thresh=0.35)

    @staticmethod
    def _nms(boxes: List[List[int]], iou_thresh: float = 0.35) -> List[List[int]]:
        """Greedy non-maximum suppression on IoU."""
        if not boxes:
            return []

        arr = np.array(boxes, dtype=float)
        x1, y1   = arr[:, 0], arr[:, 1]
        x2, y2   = x1 + arr[:, 2], y1 + arr[:, 3]
        areas    = (x2 - x1) * (y2 - y1)
        order    = np.argsort(areas)[::-1]
        keep: List[int] = []

        while order.size:
            i = order[0]
            keep.append(i)
            xx1   = np.maximum(x1[i], x1[order[1:]])
            yy1   = np.maximum(y1[i], y1[order[1:]])
            xx2   = np.minimum(x2[i], x2[order[1:]])
            yy2   = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
            iou   = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            order = order[1:][iou < iou_thresh]

        return [boxes[k] for k in keep]


# ===============================================================================
# 2. FEATURE EXTRACTOR
# ===============================================================================

class FeatureExtractor:
    """
    Extracts rich, discriminative features from a single vehicle crop.

    Outputs per detected vehicle:
    -----------------------------
    color_name   : str            -- dominant color name  e.g. "blue", "silver", "black"
    vehicle_type : str            -- shape-based type     e.g. "car", "truck", "bus", "motorcycle"
    size         : str            -- relative size        "small" | "medium" | "large"
    histogram    : ndarray(1024,) -- L2-normalized 32x32 H x S histogram
    feature_vec  : ndarray(1029,) -- histogram + type one-hot (used for ReID cosine similarity)
    """

    H_BINS: int = 32
    S_BINS: int = 32
    TYPE_ORDER: List[str] = ["car", "truck", "bus", "motorcycle", "unknown"]

    def extract(
        self,
        frame: np.ndarray,
        bbox:  List[int],
        frame_shape: Optional[Tuple[int, int]] = None,
    ) -> dict:
        """
        Extract all features for one vehicle detection.

        Args:
            frame       : full BGR frame
            bbox        : [x, y, w, h]
            frame_shape : (height, width); auto-detected if None
        Returns:
            dict with keys: color_name, vehicle_type, size, histogram, feature_vec
        """
        fh, fw = frame_shape if frame_shape else frame.shape[:2]
        x, y, w, h = (int(v) for v in bbox)

        x1 = max(0, x);          y1 = max(0, y)
        x2 = min(fw, x + w);     y2 = min(fh, y + h)

        if (x2 - x1) < 8 or (y2 - y1) < 8:
            return self._empty()

        crop     = frame[y1:y2, x1:x2]
        hsv_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        color_name   = self._extract_color(hsv_crop)
        vehicle_type = self._estimate_type(w, h, fw, fh)
        size         = self._estimate_size(w, h, fw, fh)
        histogram    = self._build_histogram(hsv_crop)
        type_onehot  = self._type_onehot(vehicle_type)
        feature_vec  = np.concatenate([histogram, type_onehot]).astype(np.float32)

        return {
            "color_name":   color_name,
            "vehicle_type": vehicle_type,
            "size":         size,
            "histogram":    histogram,
            "feature_vec":  feature_vec,
        }

    @staticmethod
    def _extract_color(hsv_crop: np.ndarray) -> str:
        """
        Identifies dominant vehicle color from an HSV crop.

        Algorithm:
          1. Down-sample to 32x32 for speed
          2. Compute mean saturation and value
          3. Low saturation -> achromatic (black / gray / silver / white)
          4. Otherwise take median hue of chromatic pixels -> color name
        """
        small  = cv2.resize(hsv_crop, (32, 32))
        pixels = small.reshape(-1, 3).astype(np.float32)

        h_vals = pixels[:, 0]   # 0-179
        s_vals = pixels[:, 1]   # 0-255
        v_vals = pixels[:, 2]   # 0-255

        mean_s = float(np.mean(s_vals))
        mean_v = float(np.mean(v_vals))

        # Achromatic branch
        if mean_s < 45:
            if   mean_v < 55:   return "black"
            elif mean_v < 120:  return "gray"
            elif mean_v < 185:  return "silver"
            else:               return "white"

        # Chromatic branch
        chromatic = s_vals > 45
        if chromatic.sum() < 5:
            return "silver"

        dominant_hue = float(np.median(h_vals[chromatic]))

        for lo, hi, name in COLOR_HUE_MAP:
            if lo <= dominant_hue < hi:
                return name

        return "unknown"

    @staticmethod
    def _estimate_type(bw: int, bh: int, fw: int, fh: int) -> str:
        """
        Estimates vehicle class purely from bounding-box geometry.

        Rules (priority order):
          bus        : wide AND large relative area
          truck      : large area, moderate aspect
          motorcycle : small area AND narrow
          car        : default vehicle-sized blob
        """
        aspect   = bw / max(bh, 1)
        rel_area = (bw * bh) / max(fw * fh, 1)

        if aspect >= 1.5 and rel_area >= 0.040:
            return "bus"
        if aspect >= 1.0 and rel_area >= 0.025:
            return "truck"
        if rel_area < 0.018 and aspect < 1.7:
            return "motorcycle"
        if rel_area >= 0.004:
            return "car"
        return "unknown"

    @staticmethod
    def _estimate_size(bw: int, bh: int, fw: int, fh: int) -> str:
        rel = (bw * bh) / max(fw * fh, 1)
        if rel < 0.020:  return "small"
        if rel < 0.070:  return "medium"
        return "large"

    def _build_histogram(self, hsv_crop: np.ndarray) -> np.ndarray:
        """
        Builds a 2D joint histogram on H and S channels.
        Bins: 32 x 32 = 1024 values, L2-normalized.
        """
        hist = cv2.calcHist(
            [hsv_crop], [0, 1], None,
            [self.H_BINS, self.S_BINS],
            [0, 180, 0, 256],
        )
        hist = hist.flatten().astype(np.float32)
        norm = np.linalg.norm(hist)
        if norm > 0:
            hist /= norm
        return hist

    def _type_onehot(self, vehicle_type: str) -> np.ndarray:
        """Returns a 5-dim one-hot encoded type vector."""
        vec = np.zeros(len(self.TYPE_ORDER), dtype=np.float32)
        idx = self.TYPE_ORDER.index(vehicle_type) \
              if vehicle_type in self.TYPE_ORDER else -1
        vec[idx] = 1.0
        return vec

    def _empty(self) -> dict:
        dim = self.H_BINS * self.S_BINS
        return {
            "color_name":   "unknown",
            "vehicle_type": "unknown",
            "size":         "unknown",
            "histogram":    np.zeros(dim, dtype=np.float32),
            "feature_vec":  np.zeros(dim + len(self.TYPE_ORDER), dtype=np.float32),
        }


# ===============================================================================
# 3. CENTROID TRACKER  (Hungarian-algorithm assignment, per-camera)
# ===============================================================================

class CentroidTracker:
    """
    Assigns stable local Track IDs (1, 2, 3, ...) to vehicle detections
    within a single camera stream.

    Uses the optimal Hungarian algorithm (linear_sum_assignment) instead of
    greedy nearest-neighbour, giving better assignment under occlusion.

    One instance per camera.
    """

    def __init__(self, max_disappeared: int = 40, max_distance: int = 130):
        self.next_id         = 1
        self.max_disappeared = max_disappeared
        self.max_distance    = max_distance

        self.objects:     OrderedDict[int, np.ndarray] = OrderedDict()
        self.bboxes:      OrderedDict[int, List[int]]  = OrderedDict()
        self.features:    OrderedDict[int, dict]       = OrderedDict()
        self.disappeared: OrderedDict[int, int]        = OrderedDict()

    def update(self, detections: List[dict]) -> Dict[int, dict]:
        """
        Update tracker with detections for the current frame.

        Args:
            detections: [{"bbox": [x,y,w,h], "features": dict}, ...]
        Returns:
            {local_id: {"centroid", "bbox", "features", "disappeared"}}
        """
        # No detections: age all objects
        if not detections:
            for tid in list(self.disappeared):
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    self._deregister(tid)
            return self._snapshot()

        input_cents = np.array(
            [[d["bbox"][0] + d["bbox"][2] // 2,
              d["bbox"][1] + d["bbox"][3] // 2]
             for d in detections],
            dtype=float,
        )

        # First frame: register all
        if not self.objects:
            for i, det in enumerate(detections):
                self._register(input_cents[i], det["bbox"], det["features"])
            return self._snapshot()

        # Build cost matrix and run Hungarian assignment
        obj_ids   = list(self.objects.keys())
        obj_cents = np.array(list(self.objects.values()), dtype=float)
        D = dist.cdist(obj_cents, input_cents)

        row_idx, col_idx = linear_sum_assignment(D)

        used_rows: set = set()
        used_cols: set = set()

        for r, c in zip(row_idx, col_idx):
            if D[r, c] > self.max_distance:
                continue
            tid = obj_ids[r]
            self.objects[tid]     = input_cents[c]
            self.bboxes[tid]      = detections[c]["bbox"]
            self.features[tid]    = detections[c]["features"]
            self.disappeared[tid] = 0
            used_rows.add(r)
            used_cols.add(c)

        # Unmatched existing objects -> age them
        for r, tid in enumerate(obj_ids):
            if r not in used_rows:
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    self._deregister(tid)

        # Unmatched new detections -> new tracks
        for c in range(len(detections)):
            if c not in used_cols:
                self._register(input_cents[c],
                               detections[c]["bbox"],
                               detections[c]["features"])

        return self._snapshot()

    def _register(self, centroid, bbox, feat):
        tid = self.next_id
        self.objects[tid]     = centroid
        self.bboxes[tid]      = bbox
        self.features[tid]    = feat
        self.disappeared[tid] = 0
        self.next_id += 1

    def _deregister(self, tid):
        del self.objects[tid]
        del self.bboxes[tid]
        del self.features[tid]
        del self.disappeared[tid]

    def _snapshot(self) -> Dict[int, dict]:
        return {
            tid: {
                "centroid":    tuple(self.objects[tid].astype(int)),
                "bbox":        self.bboxes[tid],
                "features":    self.features[tid],
                "disappeared": self.disappeared[tid],
            }
            for tid in self.objects
        }


# ===============================================================================
# 4. CROSS-CAMERA RE-IDENTIFICATION
# ===============================================================================

class CrossCameraReID:
    """
    Re-identifies vehicles across multiple cameras using combined feature vectors.

    One shared instance is passed to ALL CameraPipeline objects.

    Feature vector composition
    -------------------------
    HSV 2D histogram : 1024 dims  (color appearance)
    Vehicle type     :    5 dims  (one-hot: car/truck/bus/motorcycle/unknown)
    Total            : 1029 dims

    Matching logic
    -------------
    - Cosine similarity between incoming feature vector and every stored vehicle
    - Threshold >= 0.75  -> matched (same vehicle)
    - Threshold <  0.75  -> new vehicle, assign next Global ID
    - On match: EMA update  stored = 0.70 x old + 0.30 x new
    - Camera history: list of camera IDs that have seen this vehicle
    - Global IDs: VH-001, VH-002, VH-003, ...
    """

    def __init__(
        self,
        similarity_threshold: float = 0.75,
        ema_alpha:            float = 0.30,
    ):
        self.threshold = similarity_threshold
        self.alpha     = ema_alpha
        self._next_id  = 1
        # global_id -> {feature_vec, color, vehicle_type, size, camera_history, last_seen_cam}
        self._db: Dict[str, dict] = {}

    def match(self, features: dict, cam_id: str) -> dict:
        """
        Match a vehicle against the global database.

        Args:
            features : output dict from FeatureExtractor.extract()
            cam_id   : camera identifier, e.g. "C11"

        Returns dict with:
            global_id, similarity, is_new, color, vehicle_type,
            size, camera_history, last_seen_cam
        """
        fvec = features.get("feature_vec")

        # Guard: degenerate feature vector
        if fvec is None or np.linalg.norm(fvec) < 1e-8:
            gid = self._alloc_id()
            self._store(gid, features, cam_id, np.zeros(1029, dtype=np.float32))
            return self._result(gid, 0.0, True, self._db[gid])

        # Search for best match
        best_gid, best_sim = None, -1.0
        for gid, entry in self._db.items():
            s = self._cosine(fvec, entry["feature_vec"])
            if s > best_sim:
                best_sim, best_gid = s, gid

        # --- MATCH ---
        if best_sim >= self.threshold and best_gid is not None:
            e = self._db[best_gid]
            # Exponential moving average update
            e["feature_vec"] = (1.0 - self.alpha) * e["feature_vec"] + self.alpha * fvec
            # Update appearance metadata
            e["color"]       = features.get("color_name",   e["color"])
            e["size"]        = features.get("size",         e["size"])
            # Record camera
            if cam_id not in e["camera_history"]:
                e["camera_history"].append(cam_id)
            e["last_seen_cam"] = cam_id
            return self._result(best_gid, round(best_sim, 4), False, e)

        # --- NEW VEHICLE ---
        gid = self._alloc_id()
        self._store(gid, features, cam_id, fvec)
        return self._result(gid, 1.0, True, self._db[gid])

    def get_all_vehicles(self) -> Dict[str, dict]:
        return {
            gid: {
                "global_id":      gid,
                "color":          e["color"],
                "vehicle_type":   e["vehicle_type"],
                "size":           e["size"],
                "camera_history": e["camera_history"],
                "last_seen_cam":  e["last_seen_cam"],
            }
            for gid, e in self._db.items()
        }

    def vehicle_count(self) -> int:
        return len(self._db)

    def reset(self):
        self._db.clear()
        self._next_id = 1

    # --- internals ---

    def _alloc_id(self) -> str:
        gid = f"VH-{self._next_id:03d}"
        self._next_id += 1
        return gid

    def _store(self, gid, features, cam_id, fvec):
        self._db[gid] = {
            "feature_vec":    fvec.copy(),
            "color":          features.get("color_name",   "unknown"),
            "vehicle_type":   features.get("vehicle_type", "unknown"),
            "size":           features.get("size",         "unknown"),
            "camera_history": [cam_id],
            "last_seen_cam":  cam_id,
        }

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na < 1e-8 or nb < 1e-8:
            return 0.0
        return float(np.clip(np.dot(a, b) / (na * nb), 0.0, 1.0))

    @staticmethod
    def _result(gid, sim, is_new, entry) -> dict:
        return {
            "global_id":      gid,
            "similarity":     sim,
            "is_new":         is_new,
            "color":          entry["color"],
            "vehicle_type":   entry["vehicle_type"],
            "size":           entry["size"],
            "camera_history": entry["camera_history"],
            "last_seen_cam":  entry["last_seen_cam"],
        }


# ===============================================================================
# 5. CAMERA SCORER
# ===============================================================================

class CameraScorer:
    """
    Computes a quality score (0.0 to 1.0) for a camera view.

    Score = 40% track_count + 40% vehicle_size + 20% sharpness

    Higher score -> better candidate to be the primary (active) feed.
    """

    def score(self, frame: np.ndarray, tracks: Dict[int, dict]) -> float:
        if frame is None:
            return 0.0

        fh, fw = frame.shape[:2]
        n = len(tracks)

        # Track count (capped at 6 vehicles)
        track_score = min(n / 6.0, 1.0)

        # Average vehicle relative area
        size_score = 0.0
        if n > 0:
            rel_areas = [
                (t["bbox"][2] * t["bbox"][3]) / max(fw * fh, 1)
                for t in tracks.values()
            ]
            size_score = min(float(np.mean(rel_areas)) * 12.0, 1.0)

        # Frame sharpness (Laplacian variance)
        gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lap_var   = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharpness = min(lap_var / 400.0, 1.0)

        return round(track_score * 0.40 + size_score * 0.40 + sharpness * 0.20, 4)


# ===============================================================================
# 6. CAMERA PIPELINE
# ===============================================================================

class CameraPipeline:
    """
    Full end-to-end processing pipeline for ONE camera stream.

    Create one CameraPipeline per camera.
    Pass the SAME CrossCameraReID instance to all pipelines.

    Example
    -------
        reid     = CrossCameraReID()
        scorer   = CameraScorer()
        pipe_c11 = CameraPipeline("C11", reid, scorer)
        pipe_c12 = CameraPipeline("C12", reid, scorer)

        tracks, score = pipe_c11.process(frame)
        vis           = pipe_c11.draw(frame, tracks)
    """

    def __init__(
        self,
        cam_id:          str,
        reid:            CrossCameraReID,
        scorer:          CameraScorer,
        detector_kwargs: dict = None,
    ):
        self.cam_id   = cam_id
        self._det     = VehicleDetector(**(detector_kwargs or {}))
        self._feat    = FeatureExtractor()
        self._tracker = CentroidTracker()
        self._reid    = reid
        self._scorer  = scorer

    def process(self, frame: np.ndarray) -> Tuple[Dict[int, dict], float]:
        """
        Process one BGR video frame end-to-end.

        Returns
        -------
        tracks : {
            local_id (int): {
                bbox          : [x, y, w, h],
                centroid      : (cx, cy),
                disappeared   : int,
                global_id     : "VH-001",
                reid_sim      : float,
                is_new        : bool,
                color         : "blue",
                vehicle_type  : "car",
                size          : "medium",
                camera_history: ["C11", "C12"],
                last_seen_cam : "C12",
            }
        }
        cam_score : float in [0.0, 1.0]
        """
        fh, fw = frame.shape[:2]

        # Step 1: Detect moving vehicles
        boxes = self._det.detect(frame)

        # Step 2: Extract features for each detection
        detections = [
            {"bbox": box,
             "features": self._feat.extract(frame, box, (fh, fw))}
            for box in boxes
        ]

        # Step 3: Local tracking (Hungarian assignment -> local IDs)
        local_tracks = self._tracker.update(detections)

        # Step 4: Cross-camera ReID (assign / match global IDs)
        result: Dict[int, dict] = {}
        for lid, track in local_tracks.items():
            reid_info = self._reid.match(track["features"], self.cam_id)
            result[lid] = {
                "bbox":          track["bbox"],
                "centroid":      track["centroid"],
                "disappeared":   track["disappeared"],
                "global_id":     reid_info["global_id"],
                "reid_sim":      reid_info["similarity"],
                "is_new":        reid_info["is_new"],
                "color":         reid_info["color"],
                "vehicle_type":  reid_info["vehicle_type"],
                "size":          reid_info["size"],
                "camera_history":reid_info["camera_history"],
                "last_seen_cam": reid_info["last_seen_cam"],
            }

        # Step 5: Score this camera
        cam_score = self._scorer.score(frame, result)

        return result, cam_score

    def draw(self, frame: np.ndarray, tracks: Dict[int, dict]) -> np.ndarray:
        """
        Draw annotated bounding boxes on a copy of the frame.

        Box color:
          green   = car
          orange  = truck
          cyan    = bus
          magenta = motorcycle
          gray    = unknown
        """
        vis = frame.copy()

        for lid, t in tracks.items():
            if t["disappeared"] > 0:
                continue

            x, y, w, h = t["bbox"]
            vtype = t.get("vehicle_type", "unknown")
            color = TYPE_DRAW_COLORS.get(vtype, (180, 180, 180))

            # Bounding box
            cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)

            gid  = t.get("global_id", "?")
            lbl1 = f"{gid}  {vtype}"

            clr  = t.get("color", "?")
            sz   = t.get("size",  "?")
            sim  = t.get("reid_sim", 0.0)
            cams = ",".join(t.get("camera_history", []))
            lbl2 = f"{clr} | {sz} | sim={sim:.2f} | [{cams}]"

            font = cv2.FONT_HERSHEY_SIMPLEX
            for i, lbl in enumerate([lbl1, lbl2]):
                (tw, th), _ = cv2.getTextSize(lbl, font, 0.45, 1)
                ty = max(y - 22 + i * 16, 14)
                cv2.rectangle(vis, (x, ty - th - 2), (x + tw + 2, ty + 2), (0, 0, 0), -1)
                cv2.putText(vis, lbl, (x + 1, ty), font, 0.45, color, 1, cv2.LINE_AA)

            cx, cy = t["centroid"]
            cv2.circle(vis, (cx, cy), 5, (0, 0, 255), -1)

        return vis


# ===============================================================================
# SELF-TEST
# ===============================================================================

def _self_test():
    print("=" * 65)
    print("  vehicle_model.py  --  self-test (synthetic frames)")
    print("=" * 65)

    reid     = CrossCameraReID(similarity_threshold=0.75)
    scorer   = CameraScorer()
    pipe_c11 = CameraPipeline("C11", reid, scorer)
    pipe_c12 = CameraPipeline("C12", reid, scorer)

    H, W = 720, 1280

    # Warm up C11 background
    bg = np.full((H, W, 3), 70, dtype=np.uint8)
    print("\n[C11] Warming up MOG2 (60 frames)...")
    for _ in range(60):
        pipe_c11._det._bg.apply(bg)

    # Blue car moving right in C11
    fg2 = bg.copy()
    cv2.rectangle(fg2, (320, 300), (580, 410), (180, 80, 40), -1)
    tracks_c11, score_c11 = pipe_c11.process(fg2)

    print(f"\n[C11] Camera score : {score_c11}")
    print(f"[C11] Tracks found : {len(tracks_c11)}")
    for lid, t in tracks_c11.items():
        print(f"   LID={lid}  GID={t['global_id']}  "
              f"color={t['color']:<8}  type={t['vehicle_type']:<12}  "
              f"size={t['size']:<7}  sim={t['reid_sim']:.3f}  cams={t['camera_history']}")

    # Warm up C12 background
    bg2 = np.full((H, W, 3), 70, dtype=np.uint8)
    print("\n[C12] Warming up MOG2 (60 frames)...")
    for _ in range(60):
        pipe_c12._det._bg.apply(bg2)

    # Same blue car appears in C12
    fg4 = bg2.copy()
    cv2.rectangle(fg4, (220, 310), (480, 420), (180, 80, 40), -1)
    tracks_c12, score_c12 = pipe_c12.process(fg4)

    print(f"\n[C12] Camera score : {score_c12}")
    print(f"[C12] Tracks found : {len(tracks_c12)}")
    for lid, t in tracks_c12.items():
        print(f"   LID={lid}  GID={t['global_id']}  "
              f"color={t['color']:<8}  type={t['vehicle_type']:<12}  "
              f"size={t['size']:<7}  sim={t['reid_sim']:.3f}  cams={t['camera_history']}")

    print(f"\n{'-'*65}")
    print(f"  Total global vehicles : {reid.vehicle_count()}")
    print(f"{'-'*65}")
    for gid, v in reid.get_all_vehicles().items():
        print(f"  {gid}  color={v['color']:<8}  type={v['vehicle_type']:<12}  "
              f"size={v['size']:<7}  cameras={v['camera_history']}")
    print("\nSelf-test complete.\n")


def _video_test(video_path: str):
    """Test on a real video file. Press Q to quit."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open: {video_path}")
        return

    cam_id = os.path.splitext(os.path.basename(video_path))[0].upper()
    reid   = CrossCameraReID()
    scorer = CameraScorer()
    pipe   = CameraPipeline(cam_id, reid, scorer)

    print(f"Testing on {video_path}  (cam={cam_id})  -- press Q to quit")
    frame_num = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            if not ok:
                break

        frame_num += 1
        tracks, score = pipe.process(frame)
        vis = pipe.draw(frame, tracks)

        hud = (f"Cam:{cam_id}  F:{frame_num}  Score:{score:.3f}  "
               f"Tracks:{len(tracks)}  GlobalVehicles:{reid.vehicle_count()}")
        cv2.putText(vis, hud, (8, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow(f"Vehicle Tracker -- {cam_id}", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    print(f"\nProcessed {frame_num} frames | Global vehicles: {reid.vehicle_count()}")
    for gid, v in reid.get_all_vehicles().items():
        print(f"  {gid}: color={v['color']}  type={v['vehicle_type']}  cameras={v['camera_history']}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--video":
        _video_test(sys.argv[2])
    else:
        _self_test()

