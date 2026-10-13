"""
vehicle_search.py — Vehicle Search & Journey Tracker
=====================================================
Usage:
  python vehicle_search.py --query queries/q_<id>.json --output results/r_<id>.json

Algorithm:
  1. Load query (image upload OR colour/type/plate description)
  2. Build HSV colour histogram as the search signature
  3. Load YOLOv8n, process each camera sequentially
  4. When a matching vehicle is found: record entry, track until exit
  5. Move to next camera — write live progress after each camera
"""

# ── Windows WinError 206 fix (must be before torch) ──────────────────────────
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

import json, time, argparse, traceback
import cv2
import numpy as np

VEHICLE_CLASSES = {1:'Bicycle',2:'Car',3:'Motorcycle',5:'Bus',7:'Truck'}
CLASS_NAME_TO_ID = {
    'bicycle':1,'bike':1,'car':2,'sedan':2,'hatchback':2,
    'motorcycle':3,'motorbike':3,'bus':5,'truck':7,'pickup':7,
}
COLOR_RANGES = {
    'red':    [([0,80,80],[10,255,255]),([160,80,80],[180,255,255])],
    'orange': [([10,100,100],[25,255,255])],
    'yellow': [([25,100,100],[35,255,255])],
    'green':  [([35,50,50],[85,255,255])],
    'blue':   [([100,80,50],[130,255,255])],
    'purple': [([130,50,50],[160,255,255])],
    'white':  [([0,0,200],[180,25,255])],
    'black':  [([0,0,0],[180,255,50])],
    'silver': [([0,0,150],[180,25,210])],
    'gray':   [([0,0,80],[180,25,180])],
    'grey':   [([0,0,80],[180,25,180])],
    'brown':  [([10,50,40],[20,220,180])],
}

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, '..', 'dataset')
CAMERAS_ORDER = [
    'C11','C12','C21','C22','C23','C24','C31','C32',
    'C41','C42','C43','C51','C52','C61','C62','C63','C64','C65'
]
CAMERA_FILES = {c: f"camera_{c.lower()}.mp4" for c in CAMERAS_ORDER}

MATCH_THRESHOLD  = 0.52
FRAME_SKIP       = 8
MAX_FRAMES_CAM   = 450
CONSEC_MISS_EXIT = 30


def extract_histogram(img_bgr):
    hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv],[0,1],None,[32,32],[0,180,0,256])
    cv2.normalize(hist, hist)
    return hist.flatten().astype(np.float32)


def colour_name_to_histogram(colour):
    ranges = COLOR_RANGES.get(colour.lower(), COLOR_RANGES['white'])
    lo, hi = np.array(ranges[0][0]), np.array(ranges[0][1])
    mid    = ((lo.astype(int)+hi.astype(int))//2).astype(np.uint8)
    hsv_img = np.zeros((100,100,3), dtype=np.uint8)
    hsv_img[:] = mid
    return extract_histogram(cv2.cvtColor(hsv_img, cv2.COLOR_HSV2BGR))


def hist_sim(h1, h2):
    return float(cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL))


def frames_to_ts(frame_idx, fps):
    t = frame_idx / max(fps, 1)
    return f"{int(t//3600):02d}:{int((t%3600)//60):02d}:{int(t%60):02d}"


def save_progress(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def save_thumb(frame, bbox, out_path):
    x,y,w,h = [int(v) for v in bbox]
    ih,iw   = frame.shape[:2]
    crop = frame[max(0,y):min(ih,y+h), max(0,x):min(iw,x+w)]
    if crop.size:
        cv2.imwrite(out_path, cv2.resize(crop,(160,90)))


_yolo = None
def get_yolo():
    global _yolo
    if _yolo is None:
        from ultralytics import YOLO
        _yolo = YOLO('yolov8n.pt')
    return _yolo


def detect_vehicles(frame, cls_set=None, conf=0.30):
    classes = list(cls_set) if cls_set else list(VEHICLE_CLASSES.keys())
    results = get_yolo().predict(source=frame, conf=conf, classes=classes,
                                  imgsz=416, verbose=False, stream=False)
    dets = []
    for r in results:
        for box in r.boxes:
            cid = int(box.cls[0])
            if cid not in VEHICLE_CLASSES:
                continue
            x1,y1,x2,y2 = map(int, box.xyxy[0])
            dets.append({'bbox':[x1,y1,x2-x1,y2-y1],'cls_id':cid,
                         'conf':float(box.conf[0])})
    return dets


def search_vehicle(query, out_file, thumb_dir):
    os.makedirs(thumb_dir, exist_ok=True)

    # Build query histogram
    query_hist = None
    if query.get('mode') == 'image' and query.get('image_path'):
        img = cv2.imread(query['image_path'])
        if img is not None:
            query_hist = extract_histogram(img)
    if query_hist is None:
        query_hist = colour_name_to_histogram(query.get('color','white'))

    vtype   = query.get('vehicle_type','any').lower()
    cls_set = None
    if vtype != 'any':
        cid = CLASS_NAME_TO_ID.get(vtype)
        if cid:
            cls_set = {cid}

    cameras = query.get('cameras', CAMERAS_ORDER)
    result  = {
        'status':'running','query':query,'journey':[],
        'current_cam':None,'cameras_done':0,'cameras_total':len(cameras),
        'started_at':time.strftime('%Y-%m-%d %H:%M:%S'),'finished_at':None,'error':None,
    }
    save_progress(out_file, result)

    for ci, cam_id in enumerate(cameras):
        result['current_cam']  = cam_id
        result['cameras_done'] = ci
        save_progress(out_file, result)

        video_path = os.path.join(VIDEOS_DIR, CAMERA_FILES.get(cam_id,''))
        if not os.path.exists(video_path):
            continue
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            cap.release()
            continue

        fps       = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total     = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        in_cam    = False
        entry_f   = None
        exit_f    = None
        best_sim  = 0.0
        best_bbox = None
        best_img  = None
        miss      = 0
        fidx      = 0

        while fidx < min(MAX_FRAMES_CAM, total):
            ok, frame = cap.read()
            if not ok:
                break
            fidx += 1
            if fidx % FRAME_SKIP != 0:
                continue
            try:
                dets = detect_vehicles(frame, cls_set)
            except Exception:
                continue

            matched = False
            for det in dets:
                x,y,w,h = det['bbox']
                crop = frame[max(0,y):y+h, max(0,x):x+w]
                if crop.size == 0:
                    continue
                sim = hist_sim(query_hist, extract_histogram(crop))
                if sim >= MATCH_THRESHOLD:
                    matched = True
                    if not in_cam:
                        in_cam  = True
                        entry_f = fidx
                        miss    = 0
                    if sim > best_sim:
                        best_sim  = sim
                        best_bbox = det['bbox']
                        best_img  = frame.copy()
                    break

            if in_cam:
                if matched:
                    miss    = 0
                    exit_f  = fidx
                else:
                    miss += 1
                    if miss >= CONSEC_MISS_EXIT:
                        break

        cap.release()

        if in_cam and entry_f:
            thumb_name = f"{cam_id.lower()}_match.jpg"
            if best_img is not None and best_bbox:
                save_thumb(best_img, best_bbox,
                           os.path.join(thumb_dir, thumb_name))
            ef = entry_f or 0
            xf = exit_f  or ef
            result['journey'].append({
                'camera_id':    cam_id,
                'entry_frame':  ef,
                'exit_frame':   xf,
                'entry_time':   frames_to_ts(ef, fps),
                'exit_time':    frames_to_ts(xf, fps),
                'duration_sec': round((xf-ef)/max(fps,1), 1),
                'similarity':   round(best_sim, 3),
                'thumbnail':    f"storage/search_thumbs/{thumb_name}",
                'video_url':    f"api.php?action=stream_video&camera={cam_id}",
                'status':       'confirmed',
            })
            save_progress(out_file, result)

    result.update({'status':'done','current_cam':None,
                   'cameras_done':len(cameras),
                   'finished_at':time.strftime('%Y-%m-%d %H:%M:%S')})
    save_progress(out_file, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--query',  required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--thumbs', default='')
    args = parser.parse_args()

    with open(args.query,'r') as f:
        query = json.load(f)

    thumb_dir = args.thumbs or os.path.abspath(
        os.path.join(os.path.dirname(args.output),'..','public','storage','search_thumbs'))

    try:
        search_vehicle(query, args.output, thumb_dir)
    except Exception as e:
        save_progress(args.output,{'status':'error','error':str(e),
                                    'trace':traceback.format_exc()})
        sys.exit(1)
