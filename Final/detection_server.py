"""
detection_server.py  —  Real-Time YOLO Detection Service for PHP Dashboard
===========================================================================
Runs continuously in the background.
For each camera, reads current video frame → runs YOLOv8 → writes JSON.
PHP api.php reads these JSON files instead of using hardcoded fake data.

Usage:  python detection_server.py
"""

# ── Windows WinError 206 fix ─────────────────────────────────────────────────
import os, sys
if sys.platform == 'win32':
    _rdll = getattr(os, 'add_dll_directory', None)
    if _rdll:
        def _sdll(p):
            try: return _rdll(p)
            except OSError: pass
        os.add_dll_directory = _sdll
os.environ.setdefault('YOLO_CONFIG_DIR', r'C:\yolo_cache')
os.environ.setdefault('TORCH_HOME',      r'C:\torch_cache')
# ─────────────────────────────────────────────────────────────────────────────

import json, time, threading
import cv2
import numpy as np

# COCO vehicle class IDs (persons excluded)
VEHICLE_CLASSES = {1:'Bicycle', 2:'Car', 3:'Motorcycle', 5:'Bus', 7:'Truck'}
VEHICLE_IDS     = list(VEHICLE_CLASSES.keys())

# Colour palette — one colour per unique vehicle track (deterministic)
_PALETTE = [
    (16,185,129),(245,158,11),(56,189,248),(236,72,153),(168,85,247),
    (251,146,60),(34,197,94), (239,68,68), (99,102,241),(20,184,166),
    (234,179,8), (59,130,246),(217,70,239),(249,115,22),(132,204,22),
]
def palette_color(idx: int):
    c = _PALETTE[idx % len(_PALETTE)]
    return c  # (R, G, B)

# Paths
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR   = os.path.join(BASE_DIR, '..', 'dataset')
DETECT_DIR   = os.path.join(BASE_DIR, 'php', 'public', 'storage', 'detections')
os.makedirs(DETECT_DIR, exist_ok=True)

CAMERAS = {
    'C11':'camera_c11.mp4','C12':'camera_c12.mp4',
    'C21':'camera_c21.mp4','C22':'camera_c22.mp4',
    'C23':'camera_c23.mp4','C24':'camera_c24.mp4',
    'C31':'camera_c31.mp4','C32':'camera_c32.mp4',
    'C41':'camera_c41.mp4','C42':'camera_c42.mp4',
    'C43':'camera_c43.mp4','C51':'camera_c51.mp4',
    'C52':'camera_c52.mp4','C61':'camera_c61.mp4',
    'C62':'camera_c62.mp4','C63':'camera_c63.mp4',
    'C64':'camera_c64.mp4','C65':'camera_c65.mp4',
}

# Simple per-camera centroid-based tracker
class SimpleTracker:
    def __init__(self, max_age=30, dist_thresh=80):
        self.next_id   = 1
        self.tracks    = {}   # id -> {'centroid': (x,y), 'age': int, 'cls': int}
        self.max_age   = max_age
        self.dist      = dist_thresh

    def update(self, centroids_cls):
        """centroids_cls: list of ((cx, cy), cls_id)"""
        # Age out dead tracks
        dead = [k for k,v in self.tracks.items() if v['age'] > self.max_age]
        for k in dead:
            del self.tracks[k]

        if not centroids_cls:
            for k in self.tracks:
                self.tracks[k]['age'] += 1
            return {}

        used_ids   = set()
        new_tracks = {}

        for (cx, cy), cls_id in centroids_cls:
            best_id, best_d = None, float('inf')
            for tid, t in self.tracks.items():
                if tid in used_ids:
                    continue
                d = ((t['centroid'][0]-cx)**2 + (t['centroid'][1]-cy)**2)**0.5
                if d < self.dist and d < best_d:
                    best_d, best_id = d, tid
            if best_id is not None:
                self.tracks[best_id]['centroid'] = (cx, cy)
                self.tracks[best_id]['age']      = 0
                self.tracks[best_id]['cls']      = cls_id
                new_tracks[best_id] = self.tracks[best_id]
                used_ids.add(best_id)
            else:
                nid = self.next_id
                self.next_id += 1
                self.tracks[nid] = {'centroid':(cx,cy),'age':0,'cls':cls_id}
                new_tracks[nid]  = self.tracks[nid]

        # Increase age of unmatched
        for k in self.tracks:
            if k not in used_ids:
                self.tracks[k]['age'] += 1

        return new_tracks


def save_json(cam_id, detections, width, height, frame_num):
    data = {
        'camera_id':  cam_id,
        'frame':      frame_num,
        'timestamp':  time.time(),
        'width':      width,
        'height':     height,
        'detections': detections,
    }
    path = os.path.join(DETECT_DIR, f'{cam_id.lower()}.json')
    tmp  = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)


_yolo = None
def get_yolo():
    global _yolo
    if _yolo is None:
        print('[YOLO] Loading yolov8n.pt …', flush=True)
        from ultralytics import YOLO
        _yolo = YOLO('yolov8n.pt')
        print('[YOLO] Model ready.', flush=True)
    return _yolo


def run_camera(cam_id, video_path):
    """Thread target — processes one camera continuously."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f'[WARN] Cannot open {video_path}', flush=True)
        return

    tracker   = SimpleTracker()
    frame_num = 0
    fps       = cap.get(cv2.CAP_PROP_FPS) or 25.0
    h_vid     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w_vid     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    print(f'[{cam_id}] Started  {w_vid}x{h_vid}  {fps:.1f}fps', flush=True)

    while True:
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.5)
                continue

        frame_num += 1

        # Run YOLO (every frame — server has no UI overhead)
        try:
            model   = get_yolo()
            results = model.predict(
                source=frame,
                conf=0.50,
                iou=0.50,
                classes=VEHICLE_IDS,
                imgsz=640,
                verbose=False,
                stream=False,
            )
        except Exception as e:
            print(f'[{cam_id}] YOLO error: {e}', flush=True)
            time.sleep(0.2)
            continue

        # Parse detections
        raw_dets  = []   # (bbox_xywh, cls_id, conf)
        centroids = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id not in VEHICLE_CLASSES:
                    continue
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                bw, bh = x2-x1, y2-y1
                cx, cy = (x1+x2)//2, (y1+y2)//2
                raw_dets.append(([x1,y1,bw,bh], cls_id, float(box.conf[0])))
                centroids.append(((cx,cy), cls_id))

        # Update tracker → get stable IDs
        active_tracks = tracker.update(centroids)

        # Build output JSON list  (match raw_dets to track IDs by centroid)
        detections = []
        for i, (bbox, cls_id, conf) in enumerate(raw_dets):
            x1,y1,bw,bh = bbox
            cx = x1 + bw//2
            cy = y1 + bh//2
            # Find matching track ID
            tid = None
            for k, t in active_tracks.items():
                if abs(t['centroid'][0]-cx) < 5 and abs(t['centroid'][1]-cy) < 5:
                    tid = k
                    break
            if tid is None:
                tid = i + 1

            r_val, g_val, b_val = palette_color(tid)

            # Scale bbox to 960×540 (canvas size used by JS)
            sx = 960 / max(w_vid, 1)
            sy = 540 / max(h_vid, 1)

            detections.append({
                'track_id':  tid,
                'global_id': f'VH-{tid:03d}',
                'class':     VEHICLE_CLASSES[cls_id].lower(),
                'cls_id':    cls_id,
                'bbox':      [int(x1*sx), int(y1*sy), int(bw*sx), int(bh*sy)],
                'centroid':  [int(cx*sx), int(cy*sy)],
                'confidence':round(conf, 3),
                'reid_sim':  round(conf, 3),
                'speed_kmh': 0,
                'color_hex': f'#{r_val:02x}{g_val:02x}{b_val:02x}',
            })

        save_json(cam_id, detections, 960, 540, frame_num)

        # Small sleep to avoid 100% CPU on each thread
        time.sleep(0.04)   # ~25 detection frames/sec max

    cap.release()


def main():
    print('=' * 60, flush=True)
    print('  VISION-MIXER  Real-Time YOLO Detection Server', flush=True)
    print('  Detects: Car, Motorcycle, Bus, Truck, Bicycle', flush=True)
    print('  Excludes: Person, Animal, Everything else', flush=True)
    print('=' * 60, flush=True)

    # Warm up YOLO once (downloads model if needed)
    get_yolo()

    # Start one thread per camera
    threads = []
    for cam_id, fname in CAMERAS.items():
        vpath = os.path.join(VIDEOS_DIR, fname)
        if not os.path.exists(vpath):
            print(f'[SKIP] {cam_id} — {fname} not found', flush=True)
            continue
        t = threading.Thread(target=run_camera, args=(cam_id, vpath),
                             daemon=True, name=f'cam-{cam_id}')
        t.start()
        threads.append(t)
        time.sleep(0.3)   # stagger thread start to avoid YOLO init race

    print(f'\n[OK] {len(threads)} camera threads running.', flush=True)
    print('[OK] Writing detections to:', DETECT_DIR, flush=True)
    print('[OK] PHP will now serve REAL YOLO detections.\n', flush=True)

    try:
        while True:
            time.sleep(5)
            alive = sum(1 for t in threads if t.is_alive())
            print(f'[STATUS] {alive}/{len(threads)} threads alive', flush=True)
    except KeyboardInterrupt:
        print('\nStopped.', flush=True)


if __name__ == '__main__':
    main()
