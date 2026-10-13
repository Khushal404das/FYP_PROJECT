"""
FYP Vehicle Tracking System - Flask API Server (with MJPEG Streaming)
======================================================================
Endpoints:
  -- STREAMING --
  GET  /api/stream/<cam_id>           MJPEG stream for one camera
  GET  /api/stream/thumb/<cam_id>     Low-res thumbnail MJPEG stream
  GET  /api/stream/active             MJPEG stream for active/followed camera
  GET  /api/camera_status             All camera statuses (has_video, active, vehicles)
  GET  /api/roster                    Current tracked vehicle roster
  GET  /api/log                       Activity log entries
  POST /api/follow/<gid>              Switch active camera to follow a vehicle
  POST /api/set_active_camera         Manually set active camera
  -- QUERY / TRACKING --
  POST /api/query_image               Match by image
  POST /api/query_description         Match by text description
  POST /api/process_video             Process dataset camera
  POST /api/process_upload_video      Process uploaded video
  GET  /api/summary                   All tracked vehicles
  GET  /api/journey/<gid>             Journey for a global ID
  GET  /api/cameras                   Camera list + topology
  GET  /api/status                    Health check
  POST /api/reset                     Clear all data
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, cv2, json, time, uuid, numpy as np
from pathlib import Path
from werkzeug.utils import secure_filename

import sys
sys.path.insert(0, str(Path(__file__).parent))
from vehicle_tracker import (
    VehicleTrackingPipeline, CAMERA_IDS, CAMERA_TOPOLOGY, DATA_DIR
)
from streaming_engine import StreamManager, _get_pipeline

# ── App setup ────────────────────────────────────────────────────────────────
app    = Flask(__name__)
CORS(app)

UPLOAD_DIR = Path(__file__).parent.parent / "php_frontend" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXT = {"png","jpg","jpeg","bmp","webp","mp4","avi","mov"}

# Use the shared pipeline so live streams and API queries share the same ReID state
pipeline = _get_pipeline()
sm       = StreamManager()          # singleton

def allowed_file(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_EXT
def make_error(msg, code=400): return jsonify({"success":False,"error":msg}), code
def numpy_default(obj):
    if isinstance(obj, np.ndarray):  return obj.tolist()
    if isinstance(obj, np.integer):  return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    if isinstance(obj, set):         return sorted(obj)
    return str(obj)

# ── STREAMING ROUTES ─────────────────────────────────────────────────────────

@app.route("/api/stream/<camera_id>")
def stream_camera(camera_id: str):
    """Full-res MJPEG stream for a specific camera."""
    if camera_id not in CAMERA_IDS:
        return make_error(f"Unknown camera: {camera_id}")
    w = int(request.args.get("w", 960))
    h = int(request.args.get("h", 540))
    fps = float(request.args.get("fps", 20))
    return Response(
        sm.get_mjpeg_generator(camera_id, w, h, fps),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/api/stream/thumb/<camera_id>")
def stream_thumb(camera_id: str):
    """Low-res thumbnail MJPEG stream for camera grid."""
    if camera_id not in CAMERA_IDS:
        return make_error(f"Unknown camera: {camera_id}")
    fps = float(request.args.get("fps", 8))
    return Response(
        sm.get_thumbnail_generator(camera_id, fps),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/api/stream/active")
def stream_active():
    """MJPEG stream of the currently active/followed camera."""
    w   = int(request.args.get("w", 960))
    h   = int(request.args.get("h", 540))
    fps = float(request.args.get("fps", 25))
    return Response(
        sm.get_active_generator(w, h, fps),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/api/camera_status")
def camera_status():
    return jsonify({"success": True,
                    "cameras": sm.get_camera_status(),
                    "active_camera": sm.active_camera,
                    "followed_gid": sm.followed_gid})

@app.route("/api/roster")
def roster():
    return app.response_class(
        response=json.dumps({"success":True, "roster": sm.get_roster()},
                            default=numpy_default),
        mimetype="application/json"
    )

@app.route("/api/log")
def activity_log():
    return jsonify({"success": True, "log": sm.get_log()})

@app.route("/api/follow/<int:gid>", methods=["POST"])
def follow_vehicle(gid: int):
    data   = request.get_json(force=True) or {}
    cam_id = data.get("camera_id", "")
    if not cam_id:
        # Find the camera the vehicle was last seen in
        gtrk = pipeline.reid.global_tracks.get(gid)
        cam_id = (gtrk.get("last_camera","") if gtrk else "") or sm.active_camera
    sm.follow_vehicle(gid, cam_id)
    return jsonify({"success":True,"following":gid,"camera":cam_id})

@app.route("/api/set_active_camera", methods=["POST"])
def set_active_camera():
    data = request.get_json(force=True) or {}
    cam  = data.get("camera_id","")
    if cam not in CAMERA_IDS:
        return make_error(f"Unknown camera: {cam}")
    sm.active_camera  = cam
    sm.followed_gid   = None
    sm._log(f"Manual switch to {cam.upper()}")
    return jsonify({"success":True,"active_camera":cam})

@app.route("/api/sync/reset", methods=["POST", "GET"])
def sync_reset():
    sm.restart_sync()
    return jsonify({"success": True, "message": "All camera streams reset to beginning (t=0.0s)"})

# ── INFO ROUTES ───────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    return jsonify({
        "success": True, "status": "running",
        "tracked_vehicles": len(pipeline.reid.global_tracks),
        "cameras": CAMERA_IDS,
        "active_camera": sm.active_camera,
        "dataset_path": str(DATA_DIR),
    })

@app.route("/api/cameras")
def cameras():
    cam_data = []
    for cam in CAMERA_IDS:
        vpath = DATA_DIR / f"camera_{cam}.mp4"
        cam_data.append({
            "id": cam,
            "has_video": vpath.exists(),
            "next_cameras": CAMERA_TOPOLOGY.get(cam, []),
        })
    return jsonify({"success":True,"cameras":cam_data,"topology":CAMERA_TOPOLOGY})

@app.route("/api/summary")
def summary():
    return jsonify({"success":True, **pipeline.get_all_tracks_summary()})

@app.route("/api/journey/<int:gid>")
def journey(gid):
    result = pipeline.get_vehicle_journey(gid)
    if "error" in result:
        return make_error(result["error"], 404)
    return app.response_class(
        response=json.dumps({"success":True,**result}, default=numpy_default),
        mimetype="application/json"
    )

# ── QUERY ROUTES ──────────────────────────────────────────────────────────────

@app.route("/api/query_image", methods=["POST"])
def query_image():
    if "image" not in request.files:
        return make_error("No image file")
    file = request.files["image"]
    if not allowed_file(file.filename):
        return make_error("Unsupported file type")
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    file.save(str(path))
    result = pipeline.query_image(str(path), top_k=int(request.form.get("top_k",5)))
    return app.response_class(
        response=json.dumps({"success":True,**result}, default=numpy_default),
        mimetype="application/json"
    )

@app.route("/api/query_description", methods=["POST"])
def query_description():
    data = request.get_json(force=True) or request.form.to_dict()
    desc = {k: data.get(k,"") for k in ("color","vehicle_type","plate_number","camera_id")}
    result = pipeline.query_description(desc, top_k=int(data.get("top_k",5)))
    return app.response_class(
        response=json.dumps({"success":True,**result}, default=numpy_default),
        mimetype="application/json"
    )

@app.route("/api/process_video", methods=["POST"])
def process_video():
    data  = request.get_json(force=True) or request.form.to_dict()
    cam   = data.get("camera_id","")
    if cam not in CAMERA_IDS:
        return make_error(f"Unknown camera. Valid: {CAMERA_IDS}")
    vpath = DATA_DIR / f"camera_{cam}.mp4"
    if not vpath.exists():
        return make_error(f"Video not found: {vpath}")
    result = pipeline.process_video_segment(
        cam, str(vpath),
        int(data.get("max_frames",200)),
        int(data.get("sample_every",5))
    )
    return jsonify({"success":True,**result})

@app.route("/api/process_upload_video", methods=["POST"])
def process_upload_video():
    if "video" not in request.files:
        return make_error("No video file")
    file = request.files["video"]
    cam  = request.form.get("camera_id","c11")
    if cam not in CAMERA_IDS:
        return make_error(f"Unknown camera: {cam}")
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    file.save(str(path))
    result = pipeline.process_video_segment(
        cam, str(path),
        int(request.form.get("max_frames",200)),
        int(request.form.get("sample_every",5))
    )
    return jsonify({"success":True,**result})

@app.route("/api/reset", methods=["POST"])
def reset():
    pipeline.reid.global_tracks = {}
    pipeline.reid.next_gid      = 1
    pipeline.cam_trackers       = {}
    pipeline._save_state()
    return jsonify({"success":True,"message":"Tracking data cleared."})

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  FYP Vehicle Tracking System - API + Streaming Server")
    print("  Running on http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False,
            threaded=True, use_reloader=False)
