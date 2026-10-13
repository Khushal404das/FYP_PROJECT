"""
streaming_engine.py — MJPEG video streaming engine  (with live YOLOv8 detection)
=================================================================================
Streams frames from dataset .mp4 files as MJPEG.
Each frame is annotated in REAL-TIME with:
  * YOLOv8 bounding boxes  (car / bus / motorcycle / bicycle / truck)
  * Global stable vehicle IDs  (same ID across cameras and reconnections)
  * Cross-camera Re-ID         (vehicle keeps its ID when it moves between cameras)
  * Vehicle count badge
  * Camera / timestamp / REC overlays
Humans are never shown — only vehicle classes are detected and drawn.

Architecture:
  - ONE shared VehicleTrackingPipeline (YOLO + SORT + CrossCameraReID).
  - Each CameraStream has a background detector thread (daemon).
  - Detector thread: reads latest raw frame → calls pipeline.process_camera_frame()
    → caches annotated results with stable global IDs.
  - Render thread  : reads cached boxes → draws them on every frame → streams.
  - SyncClock: all cameras seek to the SAME video frame position on every read,
    so switching cameras shows the same moment in time.
"""

import cv2
import numpy as np
import time
import threading
from pathlib import Path
from datetime import datetime
from collections import deque

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent.parent / "dataset"

# The 6 active cameras run simultaneously on the same timestamps
ACTIVE_CAMERAS = ["c11", "c21", "c31", "c41", "c51", "c61"]


# ── Shared synchronized clock ────────────────────────────────────────────────

class SyncClock:
    """
    A shared wall-clock reference used by all 6 camera streams so every
    stream reports the SAME timestamp on each rendered frame.

    All CameraStream instances that share one SyncClock instance will:
      - start advancing from t=0.0s together
      - use time.time() anchored to a common t0
      - overlay the same HH:MM:SS.mmm on every frame
    """
    def __init__(self):
        self._t0: float | None = None   # None until first stream starts

    def start(self):
        """Start the sync clock at t=0 when first viewer connects."""
        if self._t0 is None:
            self._t0 = time.time()

    def reset(self):
        """Reset the sync clock back to t=0 (beginning)."""
        self._t0 = time.time()

    def elapsed(self) -> float:
        """Seconds since all cameras were started together."""
        if self._t0 is None:
            return 0.0
        return max(0.0, time.time() - self._t0)

    def timestamp_str(self) -> str:
        """Human-readable timestamp synced across all cameras."""
        e = self.elapsed()
        h  = int(e // 3600)
        m  = int((e % 3600) // 60)
        s  = int(e % 60)
        ms = int((e % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


# Module-level shared sync clock (created once, shared by all streams)
_SYNC_CLOCK = SyncClock()


# ── Lazy import of tracker classes (avoids circular imports at module level) ────

def _load_tracker_classes():
    from vehicle_tracker import YOLOVehicleDetector, SORTTracker, draw_tracked_frame
    return YOLOVehicleDetector, SORTTracker, draw_tracked_frame


# ── Shared pipeline singleton (one instance for all cameras) ─────────────────

_PIPELINE_LOCK = threading.Lock()
_SHARED_PIPELINE = None

def _get_pipeline():
    """Return the shared VehicleTrackingPipeline (lazy, thread-safe)."""
    global _SHARED_PIPELINE
    if _SHARED_PIPELINE is None:
        with _PIPELINE_LOCK:
            if _SHARED_PIPELINE is None:
                from vehicle_tracker import VehicleTrackingPipeline
                _SHARED_PIPELINE = VehicleTrackingPipeline()
    return _SHARED_PIPELINE


# ── Per-camera stream state ─────────────────────────────────────────────────────

class CameraStream:
    """
    Manages a looping video reader for one camera with LIVE vehicle detection.

    Synchronized mode
    -----------------
    When constructed with a SyncClock, all 6 cameras seek to the SAME video
    frame position every time get_frame() is called.  Switching cameras always
    shows the same moment in the footage.

    Background thread flow:
      1. Every frame: pass raw frame to the shared VehicleTrackingPipeline
         (YOLO + SORT + CrossCameraReID).  This gives every vehicle a stable
         global_id that persists across reconnections AND across cameras.
      2. Results stored in self._tracked (thread-safe).

    Render thread flow:
      get_frame() -> seek to synced position -> resize -> draw cached boxes
                  -> draw overlays
    """

    FONT         = cv2.FONT_HERSHEY_SIMPLEX
    DETECT_EVERY = 1    # run pipeline every frame

    def __init__(self, camera_id: str, video_path: str,
                 sync_clock: "SyncClock | None" = None):
        self.camera_id  = camera_id
        self.video_path = video_path
        self.sync_clock = sync_clock   # shared SyncClock or None
        self.cap        = None
        self.lock       = threading.Lock()
        self._fps       = 25.0         # filled in _open()
        self._total_frames = 0         # total frames in video

        # ── Frame state and caching ──
        self._tracked: list = []
        self._latest_frame: np.ndarray | None = None
        self._last_frame_ts: float = 0.0
        self._frame_count: int = 0
        self._det_ready: bool = True

        # Open video
        self._open()

    # ── Video reader ────────────────────────────────────────────────────────────

    def _open(self):
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"[WARN] Cannot open {self.video_path}")
            return
        self._fps          = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    # ── Compute synchronized target frame index ──────────────────────────────

    def _sync_frame_idx(self) -> int:
        """
        Return the video frame index that corresponds to the shared clock's
        current elapsed time. Guarantees all cameras show the exact same moment.
        """
        if self.sync_clock is None:
            return -1
        elapsed = self.sync_clock.elapsed()
        target  = int(elapsed * self._fps)
        if self._total_frames > 0:
            target = target % self._total_frames
        return target

    def rewind(self):
        """Rewind video reader to frame 0 and reset tracking state."""
        with self.lock:
            if self.cap is not None and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._frame_count = 0
            self._latest_frame = None
            self._last_frame_ts = 0.0
            self._tracked = []

    # ── Main frame getter (100% synchronized detection & render) ────────────────

    def get_frame(self, width: int = 640, height: int = 360) -> np.ndarray | None:
        with self.lock:
            if self.cap is None or not self.cap.isOpened():
                return None

            now = time.time()
            # If a recently rendered frame is available (< 38ms), return it resized
            if self._latest_frame is not None and (now - self._last_frame_ts) < 0.038:
                return cv2.resize(self._latest_frame, (width, height))

            # Synchronized seek: jump to target frame index for the shared clock
            target_idx = self._sync_frame_idx()
            if target_idx >= 0 and self._total_frames > 0:
                cur_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                if abs(cur_pos - target_idx) > 2:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)

            ret, frame = self.cap.read()
            if not ret:
                # Video reached end — loop back cleanly
                if self._total_frames > 0:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    return None

            actual_fidx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self._frame_count += 1
            self._last_frame_ts = now

            orig_h, orig_w = frame.shape[:2]
            ts = self.sync_clock.elapsed() if self.sync_clock is not None else now

            # Process detection & tracking ON THIS EXACT FRAME so boxes are 100% aligned
            pipeline = _get_pipeline()
            tracked, _ = pipeline.process_camera_frame(
                self.camera_id, frame, actual_fidx, ts, draw_boxes=False
            )
            self._tracked = tracked

            # Resize to target output resolution
            disp = cv2.resize(frame, (width, height))
            sx = width  / orig_w
            sy = height / orig_h

            scaled = []
            for item in tracked:
                x, y, w, h = item["bbox"]
                scaled.append({
                    **item,
                    "bbox": (int(x * sx), int(y * sy), int(w * sx), int(h * sy))
                })

            _, _, draw_tracked_frame = _load_tracker_classes()
            disp = draw_tracked_frame(disp, scaled, box_thickness=2)

            # ── Benchmark style green frame number at top-left (e.g. 1531) ──
            fc_text = str(actual_fidx)
            cv2.putText(disp, fc_text, (16, 44), self.FONT, 1.25, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(disp, fc_text, (16, 44), self.FONT, 1.25, (0, 255, 0), 2, cv2.LINE_AA)

            # Standard camera overlays
            disp = self._draw_overlays(disp)

            self._latest_frame = disp.copy()
            return disp

    def get_thumbnail(self, width: int = 213, height: int = 120) -> np.ndarray | None:
        """Return small thumbnail (uses latest cached annotated frame)."""
        with self.lock:
            if self._latest_frame is None:
                return self.get_frame(width, height)
            return cv2.resize(self._latest_frame, (width, height))

    # ── Overlay drawing helpers ─────────────────────────────────────────────────

    def _draw_overlays(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]

        # ── Top-left timestamp (synced or local) ──
        if self.sync_clock is not None:
            # All 6 cameras share this timestamp — always identical
            ts_str  = self.sync_clock.timestamp_str()
            now_str = f"SYNC  {ts_str}"
            ts_color = (0, 255, 200)   # cyan-green to distinguish synced cameras
        else:
            now_str  = datetime.now().strftime("%m-%d-%Y  %a  %H:%M:%S")
            ts_color = (255, 255, 255)
        self._put_text(frame, now_str, (10, 22), 0.45, ts_color, 1)

        # ── Bottom gradient bar ──
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 38), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        # ── Camera label bottom-center ──
        cam_label = f"Camera_{self.camera_id.upper()}"
        (tw, _), _ = cv2.getTextSize(cam_label, self.FONT, 0.5, 1)
        cx = (w - tw) // 2
        self._put_text(frame, cam_label, (cx, h - 12), 0.5, (255, 255, 255), 1)

        # ── Zone info bottom-left ──
        info = (f"CAM {self.camera_id.upper()} (ZONE {self._zone()}) | "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._put_text(frame, info, (8, h - 14), 0.38, (200, 220, 200), 1)

        # ── REC indicator top-right ──
        rec_color = (0, 0, 255) if int(time.time()) % 2 == 0 else (80, 0, 0)
        cv2.circle(frame, (w - 20, 14), 6, rec_color, -1)
        self._put_text(frame, "REC", (w - 42, 19), 0.4, (255, 255, 255), 1)

        return frame

    def _zone(self) -> str:
        # Only the 6 active cameras — one per zone
        zones = {
            "c11": "1",
            "c21": "2",
            "c31": "3",
            "c41": "4",
            "c51": "5",
            "c61": "6",
        }
        return zones.get(self.camera_id, "?")

    @staticmethod
    def _put_text(img, text, pos, scale, color, thick):
        # Shadow then main text
        cv2.putText(img, text, (pos[0]+1, pos[1]+1),
                    CameraStream.FONT, scale, (0, 0, 0), thick + 1, cv2.LINE_AA)
        cv2.putText(img, text, pos,
                    CameraStream.FONT, scale, color, thick, cv2.LINE_AA)

    # ── Legacy API stubs (kept for API compatibility) ───────────────────────────

    def set_vehicle_box(self, gid: int, bbox: tuple, color: tuple = (0, 255, 80)):
        pass   # Live detection now handles all box drawing

    def clear_vehicle_box(self, gid: int):
        pass   # Live detection now handles all box drawing

    def release(self):
        if self.cap:
            self.cap.release()


# ── Placeholder frame (NO SIGNAL) ──────────────────────────────────────────────

def make_offline_frame(camera_id: str, width: int = 640, height: int = 360) -> np.ndarray:
    """Return a stylised 'NO SIGNAL' frame for cameras without video."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    noise = np.random.randint(0, 25, (height, width, 3), dtype=np.uint8)
    frame = cv2.add(frame, noise)
    for y in range(0, height, 4):
        frame[y, :] = np.clip(frame[y, :].astype(int) + 15, 0, 255)
    cv2.putText(frame, "NO SIGNAL", (width//2 - 70, height//2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 180, 180), 2)
    cv2.putText(frame, f"Camera {camera_id.upper()}", (width//2 - 55, height//2 + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120, 120, 120), 1)
    now = datetime.now().strftime("%m-%d-%Y  %H:%M:%S")
    cv2.putText(frame, now, (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)
    return frame


# ── StreamManager singleton ─────────────────────────────────────────────────────

class StreamManager:
    """
    Singleton that manages all camera streams.
    Provides frame generators for MJPEG and SSE endpoints.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        from vehicle_tracker import CAMERA_IDS
        self.camera_ids  = ACTIVE_CAMERAS   # always exactly c11,c21,c31,c41,c51,c61
        self.streams: dict[str, CameraStream | None] = {}
        self.log_entries: deque = deque(maxlen=50)
        self.active_camera: str = "c11"
        self.followed_gid: int | None = None
        self._vehicle_camera_map: dict = {}   # gid -> camera_id

        # Reset the shared sync clock so ALL 6 cameras start at t=0 together.
        # Every camera will seek to the same video frame index on each get_frame()
        # call, so switching cameras always shows the same moment in the footage.
        _SYNC_CLOCK.reset()

        # Pre-warm the shared pipeline so the first frame doesn't incur a cold start
        try:
            _get_pipeline()
            self._log("[INFO] Shared tracking pipeline ready")
        except Exception as exc:
            self._log(f"[WARN] Pipeline init: {exc}")

        for cam in self.camera_ids:
            path = DATA_DIR / f"camera_{cam}.mp4"
            if path.exists():
                # Pass shared clock so every stream seeks to the same position
                self.streams[cam] = CameraStream(cam, str(path),
                                                 sync_clock=_SYNC_CLOCK)
                self._log(f"[SYNC] Opened stream for {cam.upper()} (zone {self._zone_name(cam)})")
            else:
                self.streams[cam] = None
                self._log(f"[WARN] No video for {cam.upper()} — showing offline frame")

    @staticmethod
    def _zone_name(cam: str) -> str:
        return {"c11":"1","c21":"2","c31":"3",
                "c41":"4","c51":"5","c61":"6"}.get(cam, "?")

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_entries.appendleft(f"[{ts}] {msg}")

    def restart_sync(self):
        """Reset synchronized clock to 0 and rewind all cameras to the beginning."""
        _SYNC_CLOCK.reset()
        for stream in self.streams.values():
            if stream is not None:
                stream.rewind()
        self._log("[SYNC] All cameras rewound and restarted at t=0.0s")

    # ── MJPEG generators ────────────────────────────────────────────────────────

    def get_mjpeg_generator(self, camera_id: str, width=640, height=360,
                             fps: float = 20.0):
        """Yield live-annotated MJPEG byte chunks for a specific camera."""
        _SYNC_CLOCK.start()
        delay  = 1.0 / fps
        stream = self.streams.get(camera_id)
        while True:
            t0    = time.time()
            frame = (stream.get_frame(width, height)
                     if stream else make_offline_frame(camera_id, width, height))
            if frame is None:
                frame = make_offline_frame(camera_id, width, height)
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n'
                   + jpeg.tobytes() + b'\r\n')
            elapsed = time.time() - t0
            time.sleep(max(0, delay - elapsed))

    def get_thumbnail_generator(self, camera_id: str, fps: float = 6.0):
        """Yield low-fps thumbnail MJPEG for camera grid view."""
        delay  = 1.0 / fps
        stream = self.streams.get(camera_id)
        while True:
            t0    = time.time()
            frame = (stream.get_frame(213, 120)
                     if stream else make_offline_frame(camera_id, 213, 120))
            if frame is None:
                frame = make_offline_frame(camera_id, 213, 120)
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n'
                   + jpeg.tobytes() + b'\r\n')
            elapsed = time.time() - t0
            time.sleep(max(0, delay - elapsed))

    def get_active_generator(self, width=960, height=540, fps=25.0):
        """Yield live-annotated frames from the currently-active camera."""
        delay = 1.0 / fps
        while True:
            t0     = time.time()
            cam    = self.active_camera
            stream = self.streams.get(cam)
            frame  = (stream.get_frame(width, height)
                      if stream else make_offline_frame(cam, width, height))
            if frame is None:
                frame = make_offline_frame(cam, width, height)

            # FOLLOWING overlay
            if self.followed_gid is not None:
                h, w = frame.shape[:2]
                cv2.rectangle(frame, (w - 85, 4), (w - 4, 26), (0, 200, 0), -1)
                cv2.putText(frame, "LIVE", (w - 78, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                label = f"FOLLOWING  VH-{self.followed_gid:03d}"
                cv2.putText(frame, label, (w - 220, h - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 80), 2, cv2.LINE_AA)

            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n'
                   + jpeg.tobytes() + b'\r\n')
            elapsed = time.time() - t0
            time.sleep(max(0, delay - elapsed))

    # ── Camera control ──────────────────────────────────────────────────────────

    def follow_vehicle(self, gid: int, camera_id: str):
        if camera_id in self.streams:
            old = self.active_camera
            self.active_camera = camera_id
            self.followed_gid  = gid
            self._log(f"Following VH-{gid:03d} — switched {old.upper()} -> {camera_id.upper()}")

    def update_vehicle_position(self, gid: int, camera_id: str,
                                bbox: tuple, color=(0, 255, 80)):
        old_cam = self._vehicle_camera_map.get(gid)
        if old_cam and old_cam != camera_id:
            self._log(f"VH-{gid:03d} exited {old_cam.upper()} -> {camera_id.upper()}")
            if self.followed_gid == gid:
                self.active_camera = camera_id
                self._log(f"Auto-switched to {camera_id.upper()} (following VH-{gid:03d})")
        self._vehicle_camera_map[gid] = camera_id

    # ── Info APIs ───────────────────────────────────────────────────────────────

    def get_roster(self) -> list:
        from vehicle_tracker import VehicleTrackingPipeline
        try:
            pipeline = VehicleTrackingPipeline()
            roster = []
            for gid, gtrk in pipeline.reid.global_tracks.items():
                meta = gtrk.get("meta", {})
                roster.append({
                    "global_id":    gid,
                    "label":        f"VH-{gid:03d}",
                    "color":        meta.get("color", "unknown"),
                    "vehicle_type": meta.get("vehicle_type", "car"),
                    "plate":        meta.get("plate", "—"),
                    "cameras":      sorted(gtrk["cameras"]),
                    "last_camera":  gtrk.get("last_camera", "—"),
                    "active":       gid in self._vehicle_camera_map,
                    "current_cam":  self._vehicle_camera_map.get(gid, "—"),
                })
            return roster
        except Exception:
            return []

    def get_log(self) -> list:
        return list(self.log_entries)

    def get_camera_status(self) -> list:
        status = []
        for cam in self.camera_ids:
            stream   = self.streams.get(cam)
            live_cnt = len(stream._tracked) if stream else 0
            status.append({
                "id":        cam,
                "has_video": stream is not None,
                "is_active": cam == self.active_camera,
                "vehicles":  [gid for gid, c in self._vehicle_camera_map.items() if c == cam],
                "live_count": live_cnt,
            })
        return status
