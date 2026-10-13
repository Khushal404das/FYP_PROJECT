"""
model.py — Vehicle-Only Detection & Tracking with YOLOv8
=========================================================
Uses YOLOv8 (ultralytics) for proper vehicle-only detection:
  - Detects: car, motorcycle, bus, truck, bicycle
  - IGNORES: person, animal, tree, shadow, everything else
  - Works on BOTH moving AND stationary vehicles
  - CentroidTracker for stable per-camera track IDs
  - IoU-based NMS + Colour Histogram ReID cross-camera matching
"""

# ── Windows WinError 206 fix (MUST be before torch/ultralytics import) ──
# PyTorch's DLL loader raises OSError [WinError 206] on Windows paths
# with spaces or long usernames. This patch silently ignores those failures.
import os as _os, sys as _sys
if _sys.platform == "win32":
    _real_add_dll = getattr(_os, "add_dll_directory", None)
    if _real_add_dll:
        def _safe_add_dll(path):
            try:
                return _real_add_dll(path)
            except OSError:
                pass
        _os.add_dll_directory = _safe_add_dll

# Point YOLO & torch caches to a short path to avoid MAX_PATH issues
_os.environ.setdefault("YOLO_CONFIG_DIR",  r"C:\yolo_cache")
_os.environ.setdefault("TORCH_HOME",       r"C:\torch_cache")

import cv2
import numpy as np
from collections import OrderedDict
from scipy.spatial import distance as dist
from typing import Dict, List, Optional, Tuple

# ── YOLOv8 vehicle-only classes (COCO dataset IDs) ─────────────────
# 1=bicycle, 2=car, 3=motorcycle, 5=bus, 7=truck
VEHICLE_CLASSES = {1, 2, 3, 5, 7}
VEHICLE_NAMES   = {1: "Bicycle", 2: "Car", 3: "Motorcycle",
                   5: "Bus",     7: "Truck"}

_yolo_model = None   # lazy-loaded singleton

def _get_yolo():
    """Load YOLOv8n once and reuse (downloads ~6 MB on first run)."""
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO("yolov8n.pt")   # nano — fastest, good accuracy
    return _yolo_model


# ═══════════════════════════════════════════════════════════════════
# 1. YOLOv8 Vehicle Detector
# ═══════════════════════════════════════════════════════════════════

class VehicleDetector:
    """
    Detects vehicles (car, motorcycle, bus, truck, bicycle) using
    YOLOv8. Persons and all other classes are completely ignored.
    Works on BOTH stationary and moving vehicles.
    """

    def __init__(self,
                 conf: float = 0.38,
                 iou:  float = 0.40,
                 imgsz: int  = 640):
        self.conf  = conf
        self.iou   = iou
        self.imgsz = imgsz
        self._model = None   # lazy init inside thread

    def _ensure_model(self):
        if self._model is None:
            self._model = _get_yolo()

    def detect(self, frame: np.ndarray) -> Tuple[List[List[int]], List[int]]:
        """
        Returns (boxes, cls_ids):
          boxes   — list of [x, y, w, h]
          cls_ids — COCO class ID for each box (2=Car, 3=Motorcycle, etc.)
        Persons and non-vehicle classes are filtered out.
        """
        self._ensure_model()
        results = self._model.predict(
            source=frame,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            classes=list(VEHICLE_CLASSES),   # ← only vehicle classes
            verbose=False,
            stream=False,
        )
        boxes, cls_ids = [], []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                w, h = x2 - x1, y2 - y1
                if w > 10 and h > 10:
                    boxes.append([x1, y1, w, h])
                    cls_ids.append(cls_id)
        return boxes, cls_ids


# ═══════════════════════════════════════════════════════════════════
# 2. Centroid Tracker (local per-camera)
# ═══════════════════════════════════════════════════════════════════

class CentroidTracker:
    """
    Assigns stable local track IDs to detected bounding boxes
    by matching centroids frame-to-frame using nearest-neighbour.
    """

    def __init__(self, max_disappeared: int = 40,
                 max_distance: int = 100):
        self.next_id         = 1
        self.max_disappeared = max_disappeared
        self.max_distance    = max_distance
        self.objects:     OrderedDict = OrderedDict()   # id -> centroid
        self.bboxes:      OrderedDict = OrderedDict()   # id -> [x,y,w,h]
        self.disappeared: OrderedDict = OrderedDict()   # id -> frames_missing

    def register(self, centroid, bbox):
        self.objects[self.next_id]     = centroid
        self.bboxes[self.next_id]      = bbox
        self.disappeared[self.next_id] = 0
        self.next_id += 1

    def deregister(self, obj_id):
        del self.objects[obj_id]
        del self.bboxes[obj_id]
        del self.disappeared[obj_id]

    def update(self, boxes: List[List[int]]) -> Dict[int, dict]:
        if not boxes:
            for obj_id in list(self.disappeared):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)
            return self._tracks()

        input_centroids = np.array(
            [[x + w // 2, y + h // 2] for x, y, w, h in boxes],
            dtype=float
        )

        if not self.objects:
            for i, box in enumerate(boxes):
                self.register(input_centroids[i], box)
            return self._tracks()

        obj_ids       = list(self.objects.keys())
        obj_centroids = np.array(list(self.objects.values()), dtype=float)
        D = dist.cdist(obj_centroids, input_centroids)

        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows, used_cols = set(), set()
        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if D[row, col] > self.max_distance:
                continue
            obj_id = obj_ids[row]
            self.objects[obj_id]     = input_centroids[col]
            self.bboxes[obj_id]      = boxes[col]
            self.disappeared[obj_id] = 0
            used_rows.add(row); used_cols.add(col)

        for row in set(range(len(obj_ids))) - used_rows:
            obj_id = obj_ids[row]
            self.disappeared[obj_id] += 1
            if self.disappeared[obj_id] > self.max_disappeared:
                self.deregister(obj_id)

        for col in set(range(len(input_centroids))) - used_cols:
            self.register(input_centroids[col], boxes[col])

        return self._tracks()

    def _tracks(self):
        return {
            oid: {"centroid": tuple(c.astype(int)), "bbox": self.bboxes[oid]}
            for oid, c in self.objects.items()
        }


# ═══════════════════════════════════════════════════════════════════
# 3. Colour Histogram ReID (cross-camera)
# ═══════════════════════════════════════════════════════════════════

class ReIDMatcher:
    """
    Re-identifies vehicles across multiple cameras using HSV colour
    histograms. Assigns a persistent Global ID (GID) to each unique vehicle.
    """

    def __init__(self, threshold: float = 0.60):
        self.threshold = threshold
        self._db: Dict[int, np.ndarray] = {}
        self._next_gid = 1

    def _histogram(self, frame, bbox) -> Optional[np.ndarray]:
        x, y, w, h = [int(v) for v in bbox]
        ih, iw = frame.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(iw, x + w), min(ih, y + h)
        if x2 <= x1 or y2 <= y1 or (x2-x1) < 8 or (y2-y1) < 8:
            return None
        crop = frame[y1:y2, x1:x2]
        hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten().astype(np.float32)

    def match(self, frame, bbox) -> Tuple[int, float]:
        feat = self._histogram(frame, bbox)
        if feat is None:
            gid = self._next_gid; self._next_gid += 1
            return gid, 0.0

        best_gid, best_sim = -1, -1.0
        for gid, db_feat in self._db.items():
            sim = float(cv2.compareHist(feat, db_feat, cv2.HISTCMP_CORREL))
            if sim > best_sim:
                best_sim, best_gid = sim, gid

        if best_sim >= self.threshold and best_gid >= 1:
            self._db[best_gid] = 0.7 * self._db[best_gid] + 0.3 * feat
            return best_gid, best_sim
        else:
            gid = self._next_gid; self._next_gid += 1
            self._db[gid] = feat
            return gid, 1.0


# ═══════════════════════════════════════════════════════════════════
# 4. Camera Scorer
# ═══════════════════════════════════════════════════════════════════

class CameraScorer:
    """Scores a camera view based on track count, vehicle size, sharpness."""

    def score(self, frame: np.ndarray, tracks: Dict) -> float:
        if frame is None or not tracks:
            return 0.0
        h, w = frame.shape[:2]
        n = min(len(tracks), 8)
        track_score = n / 8.0
        size_score = 0.0
        for t in tracks.values():
            bx, by, bw, bh = t["bbox"]
            size_score += (bw * bh) / (w * h)
        size_score = min(size_score / max(n, 1) * 5, 1.0)
        gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharpness = min(cv2.Laplacian(gray, cv2.CV_64F).var() / 300.0, 1.0)
        return round(track_score * 0.4 + size_score * 0.4 + sharpness * 0.2, 4)


# ═══════════════════════════════════════════════════════════════════
# 5. Full Per-Camera Pipeline
# ═══════════════════════════════════════════════════════════════════

class CameraPipeline:
    """
    Wraps YOLO vehicle detector + centroid tracker for one camera.
    Shared ReIDMatcher is passed in (same instance for all cameras).
    """

    def __init__(self, cam_id: str, reid: ReIDMatcher, scorer: CameraScorer):
        self.cam_id   = cam_id
        self._det     = VehicleDetector(conf=0.38, iou=0.40)
        self._tracker = CentroidTracker()
        self._reid    = reid
        self._scorer  = scorer

    def process(self, frame: np.ndarray) -> Tuple[Dict, float]:
        """
        Returns:
            tracks: {local_id: {"bbox", "centroid", "global_id", "reid_sim"}}
            cam_score: float
        """
        boxes, cls_ids = self._det.detect(frame)

        # Map each box index -> cls_id for lookup after tracking
        box_to_cls = {i: cls_ids[i] for i in range(len(boxes))}

        local  = self._tracker.update(boxes)
        result = {}
        for lid, info in local.items():
            gid, sim = self._reid.match(frame, info["bbox"])
            # Find cls_id by matching bbox to original detection
            cls_id = -1
            for i, b in enumerate(boxes):
                if b == list(info["bbox"]):
                    cls_id = cls_ids[i]
                    break
            result[lid] = {
                "bbox":      info["bbox"],
                "centroid":  info["centroid"],
                "global_id": gid,
                "reid_sim":  round(sim, 3),
                "cls_id":    cls_id,
            }
        cam_score = self._scorer.score(frame, result)
        return result, cam_score


# ═══════════════════════════════════════════════════════════════════
# Quick self-test
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading YOLOv8 model …")
    reid   = ReIDMatcher()
    scorer = CameraScorer()
    pipe   = CameraPipeline("TEST", reid, scorer)
    # warm up
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    tracks, score = pipe.process(dummy)
    print(f"  Tracks on blank frame : {len(tracks)}")
    print(f"  Camera score          : {score}")
    print("Model self-test passed — YOLOv8 vehicle detector ready.")
