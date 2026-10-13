"""
Multi-Camera Vehicle Tracking Dashboard
YOLOv8 vehicle-only detection (Car, Motorcycle, Bus, Truck, Bicycle) + ReID.
Run: python app.py
"""

# ── Windows WinError 206 fix — MUST be first, before torch/ultralytics ──
import os, sys
if sys.platform == "win32":
    _real_add_dll = getattr(os, "add_dll_directory", None)
    if _real_add_dll:
        def _safe_add_dll(path):
            try:
                return _real_add_dll(path)
            except OSError:
                pass
        os.add_dll_directory = _safe_add_dll
os.environ.setdefault("YOLO_CONFIG_DIR", r"C:\yolo_cache")
os.environ.setdefault("TORCH_HOME",      r"C:\torch_cache")
# ─────────────────────────────────────────────────────────────────────────

import cv2, time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGridLayout, QTextEdit, QGroupBox,
    QComboBox, QStatusBar, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont

# ── Import detection pipeline ──────────────────────────────────────
from model import CameraPipeline, ReIDMatcher, CameraScorer

# ── Paths ──────────────────────────────────────────────────────────
BASE   = os.path.dirname(os.path.abspath(__file__))
VIDEOS = os.path.join(BASE, "..", "dataset")

CAMERAS = {
    "C11": "camera_c11.mp4", "C12": "camera_c12.mp4",
    "C21": "camera_c21.mp4", "C22": "camera_c22.mp4",
    "C23": "camera_c23.mp4", "C24": "camera_c24.mp4",
    "C31": "camera_c31.mp4", "C32": "camera_c32.mp4",
    "C41": "camera_c41.mp4", "C42": "camera_c42.mp4",
    "C43": "camera_c43.mp4", "C51": "camera_c51.mp4",
    "C52": "camera_c52.mp4", "C61": "camera_c61.mp4",
    "C62": "camera_c62.mp4", "C63": "camera_c63.mp4",
    "C64": "camera_c64.mp4", "C65": "camera_c65.mp4",
}

ZONES = {
    "All Cameras (18)":  list(CAMERAS.keys()),
    "Zone 1 (C11-C12)":  ["C11", "C12"],
    "Zone 2 (C21-C24)":  ["C21", "C22", "C23", "C24"],
    "Zone 3 (C31-C32)":  ["C31", "C32"],
    "Zone 4 (C41-C43)":  ["C41", "C42", "C43"],
    "Zone 5 (C51-C52)":  ["C51", "C52"],
    "Zone 6 (C61-C65)":  ["C61", "C62", "C63", "C64", "C65"],
}

# ── Colour palette for track IDs ──────────────────────────────────
PALETTE = [
    (0, 255, 127), (0, 191, 255), (255, 165, 0),  (255, 99,  71),
    (138, 43, 226),(0, 255, 255), (255, 20, 147),  (173, 255, 47),
    (30, 144, 255),(255, 215, 0), (0, 250, 154),   (255, 127, 80),
]

def track_color(track_id: int):
    return PALETTE[int(track_id) % len(PALETTE)]

STYLE = """
QMainWindow, QWidget {
    background: #0d1117; color: #e6edf3;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QGroupBox {
    border: 1px solid #30363d; border-radius: 8px;
    margin-top: 10px; font-weight: bold;
    color: #58a6ff; padding: 6px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QPushButton {
    background: #238636; color: #fff; border: none;
    border-radius: 6px; padding: 8px 20px;
    font-weight: bold; font-size: 13px;
}
QPushButton:hover { background: #2ea043; }
QPushButton:disabled { background: #21262d; color: #484f58; }
QPushButton#stop { background: #da3633; }
QPushButton#stop:hover { background: #f85149; }
QTextEdit {
    background: #161b22; color: #8b949e;
    border: 1px solid #30363d; border-radius: 6px;
    font-family: 'Courier New', monospace; font-size: 11px;
}
QComboBox {
    background: #21262d; color: #e6edf3;
    border: 1px solid #30363d; border-radius: 6px; padding: 4px 8px;
}
QComboBox QAbstractItemView { background: #21262d; color: #e6edf3; }
QLabel { color: #e6edf3; }
QStatusBar { background: #161b22; color: #8b949e; border-top: 1px solid #30363d; }
QSplitter::handle { background: #21262d; width: 2px; }
"""


def draw_detections(frame: np.ndarray, tracks: dict) -> np.ndarray:
    """
    Draw clean YOLO-style bounding boxes matching the PHP dashboard UI.
    Label format: 'VH-001 • Car • ReID 87%'
    - Semi-transparent filled box
    - Solid coloured border (3 px)
    - No centroid dots
    - Only vehicles (cls_id already filtered by YOLO)
    """
    from model import VEHICLE_NAMES
    out = frame.copy()

    for lid, info in tracks.items():
        x, y, w, h = [int(v) for v in info["bbox"]]
        gid      = info.get("global_id", lid)
        cls_id   = info.get("cls_id", -1)
        reid_sim = info.get("reid_sim", 0.0)
        cls_name = VEHICLE_NAMES.get(cls_id, "Vehicle")
        color    = track_color(gid)

        # ── Semi-transparent fill ──────────────────────────────────────
        overlay = out.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
        cv2.addWeighted(overlay, 0.12, out, 0.88, 0, out)

        # ── Solid border (3 px) ────────────────────────────────────────
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 3)

        # ── Corner ticks (CVPR-AIC style) ─────────────────────────────
        tick = min(w, h) // 5
        for px, py, dx, dy in [
            (x, y, 1, 1), (x+w, y, -1, 1),
            (x, y+h, 1, -1), (x+w, y+h, -1, -1)
        ]:
            cv2.line(out, (px, py), (px + dx*tick, py), color, 3)
            cv2.line(out, (px, py), (px, py + dy*tick), color, 3)

        # ── Label: "VH-001 • Car • ReID 87%" ──────────────────────────
        reid_pct = int(reid_sim * 100)
        label    = f"VH-{gid:03d} \u2022 {cls_name} \u2022 ReID {reid_pct}%"
        font     = cv2.FONT_HERSHEY_DUPLEX
        scale    = 0.48
        thick    = 1
        (tw, th), baseline = cv2.getTextSize(label, font, scale, thick)
        pad = 5

        # Label box above bounding box
        lx1 = x
        ly1 = max(0, y - th - 2*pad)
        lx2 = x + tw + 2*pad
        ly2 = max(th + 2*pad, y)

        # Filled label background
        cv2.rectangle(out, (lx1, ly1), (lx2, ly2), color, -1)
        # Label text in black
        cv2.putText(out, label, (lx1 + pad, ly2 - pad),
                    font, scale, (0, 0, 0), thick, cv2.LINE_AA)

    # ── Vehicle count overlay (top-left) ──────────────────────────────
    count_label = f"Vehicles: {len(tracks)}"
    cv2.putText(out, count_label, (10, 34),
                cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(out, count_label, (10, 34),
                cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 230, 118), 2, cv2.LINE_AA)
    return out



def bgr_to_pixmap(frame, w, h):
    """Convert OpenCV BGR frame to QPixmap."""
    small = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
    rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    img   = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(img)


# ── Detection + Video Thread ───────────────────────────────────────
class VideoWorker(QThread):
    """Reads frames, runs per-camera detection, emits annotated frames."""
    frame_ready   = pyqtSignal(str, object)
    log_msg       = pyqtSignal(str, str)
    system_ready  = pyqtSignal(list)
    switched      = pyqtSignal(str)
    stats_update  = pyqtSignal(dict)
    done          = pyqtSignal()

    def __init__(self, cam_ids):
        super().__init__()
        self.cam_ids  = cam_ids
        self._running = False
        self._frames  = 0
        self._switches= 0

    def stop(self):
        self._running = False

    def run(self):
        self._running = True

        # Shared ReID + scorer across all cameras
        reid   = ReIDMatcher(threshold=0.55)
        scorer = CameraScorer()

        # Per-camera pipelines + captures
        pipelines = {}
        caps      = {}
        for cid in self.cam_ids:
            path = os.path.join(VIDEOS, CAMERAS[cid])
            if os.path.exists(path):
                caps[cid]      = cv2.VideoCapture(path)
                pipelines[cid] = CameraPipeline(cid, reid, scorer)
                self.log_msg.emit("INFO", f"Opened {cid}: {os.path.basename(path)}")
            else:
                self.log_msg.emit("WARNING", f"Not found: {path}")

        if not caps:
            self.log_msg.emit("ERROR", "No video files could be opened!")
            self.done.emit()
            return

        active_ids = list(caps.keys())
        self.log_msg.emit("INFO",
            f"System ready — {len(active_ids)} cameras | YOLOv8 Detection ON")
        self.system_ready.emit(active_ids)

        # Score-based camera switching
        active_cam   = active_ids[0]
        frame_in_cam = 0
        SWITCH_EVERY = 60
        fps_t        = time.time()
        cam_scores   = {cid: 0.0 for cid in active_ids}
        global_seen: set = set()
        thumb_frame_ctr = {cid: 0 for cid in active_ids}
        THUMB_DETECT_EVERY = 6    # run YOLO on thumbnails every 6th frame
        last_thumb_tracks  = {cid: {} for cid in active_ids}  # cache tracks
        self.switched.emit(active_cam)
        self.log_msg.emit("INFO",
            "Strategy: YOLO on active cam every frame; "
            "thumbnails detected every 6th frame")

        while self._running:
            self._frames  += 1
            frame_in_cam  += 1

            for cid, cap in caps.items():
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                if not ok or frame is None:
                    continue

                # ── Active camera: run YOLO every frame ────────
                if cid == active_cam:
                    try:
                        tracks, cam_score = pipelines[cid].process(frame)
                        cam_scores[cid]   = cam_score
                        for info in tracks.values():
                            global_seen.add(info.get("global_id", -1))
                        last_thumb_tracks[cid] = tracks
                        annotated = draw_detections(frame, tracks)
                    except Exception as e:
                        self.log_msg.emit("ERROR", f"Detection error [{cid}]: {e}")
                        annotated = frame

                # ── Thumbnail cameras: YOLO every 4th frame ────
                else:
                    thumb_frame_ctr[cid] += 1
                    if thumb_frame_ctr[cid] >= THUMB_DETECT_EVERY:
                        thumb_frame_ctr[cid] = 0
                        try:
                            tracks, cam_score = pipelines[cid].process(frame)
                            cam_scores[cid] = cam_score
                            for info in tracks.values():
                                global_seen.add(info.get("global_id", -1))
                            last_thumb_tracks[cid] = tracks
                        except Exception as e:
                            self.log_msg.emit("ERROR", f"Thumb error [{cid}]: {e}")
                    # Always draw cached tracks on thumbnails
                    annotated = draw_detections(frame, last_thumb_tracks.get(cid, {}))

                self.frame_ready.emit(cid, annotated)

            # Score-based camera switch
            if frame_in_cam >= SWITCH_EVERY:
                frame_in_cam = 0
                best_cam = max(cam_scores, key=cam_scores.get)
                if best_cam != active_cam:
                    active_cam = best_cam
                    self._switches += 1
                    self.log_msg.emit(
                        "INFO",
                        f"Switched → {active_cam}  "
                        f"(score={cam_scores[active_cam]:.3f}, "
                        f"switches={self._switches})"
                    )
                    self.switched.emit(active_cam)

            if self._frames % 10 == 0:
                now = time.time()
                fps = round(10 / max(now - fps_t, 0.001), 1)
                fps_t = now
                cur_det = len(pipelines[active_cam]._tracker.objects) \
                          if active_cam in pipelines else 0
                self.stats_update.emit({
                    "vehicles":  len(global_seen),
                    "local_det": cur_det,
                    "switches":  self._switches,
                    "frames":    self._frames,
                    "fps":       fps,
                    "cam_score": round(cam_scores.get(active_cam, 0), 3),
                })

        for cap in caps.values():
            cap.release()
        self.log_msg.emit("INFO", "All streams closed.")
        self.done.emit()


# ── Camera Thumbnail ───────────────────────────────────────────────
class CamThumb(QLabel):
    def __init__(self, cam_id):
        super().__init__()
        self.cam_id = cam_id
        self.setFixedSize(200, 118)
        self.setAlignment(Qt.AlignCenter)
        self._active = False
        self._refresh_style()
        self.setText(f"  {cam_id}\nWaiting…")

    def _refresh_style(self):
        border = "#58a6ff" if self._active else "#30363d"
        self.setStyleSheet(
            f"background:#161b22; border: 2px solid {border};"
            f"border-radius:6px; color:#484f58; font-size:11px;"
        )

    def set_active(self, active: bool):
        self._active = active
        self._refresh_style()

    def update_frame(self, frame: np.ndarray):
        pm = bgr_to_pixmap(frame, 196, 114)
        if pm:
            self.setPixmap(pm)


# ── Stat Card ──────────────────────────────────────────────────────
def make_stat_card(icon: str, title: str, init: str = "0"):
    card = QWidget()
    card.setFixedSize(145, 75)
    card.setStyleSheet(
        "background:#161b22; border:1px solid #30363d; border-radius:8px;"
    )
    lay = QVBoxLayout(card); lay.setContentsMargins(10, 6, 10, 6)
    top = QHBoxLayout()
    il = QLabel(icon); il.setStyleSheet(
        "font-size:16px; background:transparent; border:none;")
    tl = QLabel(title); tl.setStyleSheet(
        "color:#8b949e; font-size:9px; background:transparent; border:none;")
    top.addWidget(il); top.addWidget(tl); top.addStretch()
    vl = QLabel(init)
    vl.setStyleSheet(
        "color:#58a6ff; font-size:20px; font-weight:bold;"
        " background:transparent; border:none;")
    lay.addLayout(top); lay.addWidget(vl)
    card._val = vl
    return card


# ── Main Window ────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "Multi-Camera Vehicle Tracking System — FAST NUCES FYP")
        self.resize(1500, 900)
        self.setStyleSheet(STYLE)
        self._worker     = None
        self._thumbs     = {}
        self._active_cam = None
        self._started    = None
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _build_ui(self):
        cw = QWidget(); self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(8, 6, 8, 6); root.setSpacing(6)
        root.addWidget(self._build_toolbar())
        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(self._build_left())
        sp.addWidget(self._build_right())
        sp.setSizes([880, 600])
        root.addWidget(sp, 1)
        sb = QStatusBar(); self.setStatusBar(sb)
        self._status    = QLabel("Ready — select a zone and press ▶ Start")
        self._elapsed   = QLabel("00:00")
        self._fps_lbl   = QLabel("FPS: —")
        self._score_lbl = QLabel("Score: —")
        sb.addWidget(self._status, 1)
        sb.addPermanentWidget(self._score_lbl)
        sb.addPermanentWidget(self._fps_lbl)
        sb.addPermanentWidget(self._elapsed)

    def _build_toolbar(self):
        w = QWidget(); w.setFixedHeight(58)
        w.setStyleSheet("background:#161b22; border-bottom:1px solid #30363d;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 6, 14, 6); lay.setSpacing(10)
        title = QLabel("🎥  Multi-Camera Vehicle Tracking — Live Detection + ReID")
        title.setStyleSheet(
            "font-size:15px; font-weight:bold; color:#58a6ff; background:transparent;")
        lay.addWidget(title); lay.addStretch()
        lay.addWidget(QLabel("Zone:"))
        self._zone_cb = QComboBox()
        self._zone_cb.addItems(list(ZONES.keys()))
        self._zone_cb.setFixedWidth(200)
        lay.addWidget(self._zone_cb)
        self._start_btn = QPushButton("▶  Start")
        self._stop_btn  = QPushButton("⏹  Stop")
        self._stop_btn.setObjectName("stop")
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        lay.addWidget(self._start_btn)
        lay.addWidget(self._stop_btn)
        return w

    def _build_left(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 4, 0); lay.setSpacing(6)
        feed_box = QGroupBox("  Active Camera Feed  (Bounding Boxes + Track IDs)")
        fl = QVBoxLayout(feed_box)
        self._feed = QLabel("▶  Press Start to begin")
        self._feed.setFixedSize(860, 490)
        self._feed.setAlignment(Qt.AlignCenter)
        self._feed.setStyleSheet(
            "background:#161b22; border-radius:8px; color:#484f58; font-size:18px;")
        self._cam_lbl = QLabel("Camera: —")
        self._cam_lbl.setStyleSheet(
            "color:#58a6ff; font-weight:bold; font-size:13px;")
        fl.addWidget(self._feed); fl.addWidget(self._cam_lbl)
        lay.addWidget(feed_box)
        stats_box = QGroupBox("  Statistics"); sl = QHBoxLayout(stats_box)
        self._c_veh  = make_stat_card("🚗", "Unique Vehicles (ReID)")
        self._c_loc  = make_stat_card("📦", "Active Detections")
        self._c_sw   = make_stat_card("🔄", "Cam Switches")
        self._c_frm  = make_stat_card("🎞", "Frames")
        self._c_fps  = make_stat_card("⚡", "FPS", "—")
        for c in [self._c_veh, self._c_loc, self._c_sw, self._c_frm, self._c_fps]:
            sl.addWidget(c)
        sl.addStretch()
        lay.addWidget(stats_box)
        return w

    def _build_right(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 0, 0, 0); lay.setSpacing(6)
        self._grid_box = QGroupBox("  Camera Thumbnails  (with Detection Boxes)")
        self._grid = QGridLayout(self._grid_box); self._grid.setSpacing(4)
        lay.addWidget(self._grid_box, 1)
        log_box = QGroupBox("  System Log"); ll = QVBoxLayout(log_box)
        self._log = QTextEdit(); self._log.setReadOnly(True)
        self._log.setFixedHeight(200)
        clr = QPushButton("Clear"); clr.setFixedWidth(70)
        clr.clicked.connect(self._log.clear)
        ll.addWidget(self._log); ll.addWidget(clr, 0, Qt.AlignRight)
        lay.addWidget(log_box)
        return w

    # ── Handlers ───────────────────────────────────────────────────
    def _on_start(self):
        cam_ids = ZONES[self._zone_cb.currentText()]
        self._worker = VideoWorker(cam_ids)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.log_msg.connect(self._on_log)
        self._worker.system_ready.connect(self._on_ready)
        self._worker.switched.connect(self._on_switched)
        self._worker.stats_update.connect(self._on_stats)
        self._worker.done.connect(self._on_done)
        self._worker.start()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._started = time.time()
        self._status.setText("  Opening streams & starting detection…")

    def _on_stop(self):
        if self._worker:
            self._worker.stop()
        self._stop_btn.setEnabled(False)
        self._status.setText("Stopping…")

    def _on_ready(self, cam_ids):
        self._status.setText(
            f"  Running — {len(cam_ids)} cameras | Detection + ReID ON")
        cols = 3
        for i, cid in enumerate(cam_ids[:12]):
            if cid not in self._thumbs:
                t = CamThumb(cid)
                self._thumbs[cid] = t
                self._grid.addWidget(t, i // cols, i % cols)

    def _on_frame(self, cam_id: str, frame: np.ndarray):
        if cam_id in self._thumbs:
            self._thumbs[cam_id].update_frame(frame)
        if cam_id == self._active_cam:
            pm = bgr_to_pixmap(frame, 860, 490)
            if pm:
                self._feed.setPixmap(pm)

    def _on_switched(self, cam_id: str):
        self._active_cam = cam_id
        self._cam_lbl.setText(
            f"Camera: {cam_id}  |  Score-based auto-switching")
        self._status.setText(f"  Active camera → {cam_id}")
        for cid, thumb in self._thumbs.items():
            thumb.set_active(cid == cam_id)

    def _on_log(self, level: str, msg: str):
        colours = {"INFO": "#8b949e", "WARNING": "#e3b341",
                   "ERROR": "#f85149", "DEBUG": "#3fb950"}
        col = colours.get(level, "#8b949e")
        ts  = time.strftime("%H:%M:%S")
        self._log.append(
            f'<span style="color:#484f58">[{ts}]</span> '
            f'<span style="color:{col}">[{level}]</span> '
            f'<span style="color:#e6edf3">{msg}</span>'
        )
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum())

    def _on_stats(self, s: dict):
        self._c_veh._val.setText(str(s.get("vehicles", 0)))
        self._c_loc._val.setText(str(s.get("local_det", 0)))
        self._c_sw._val.setText(str(s.get("switches", 0)))
        self._c_frm._val.setText(str(s.get("frames", 0)))
        fps = s.get("fps", 0)
        self._c_fps._val.setText(str(fps))
        self._fps_lbl.setText(f"FPS: {fps}")
        self._score_lbl.setText(f"Cam Score: {s.get('cam_score', 0):.3f}")

    def _on_done(self):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.setText("Stopped — press ▶ Start to restart")

    def _tick(self):
        if self._started and self._stop_btn.isEnabled():
            s = int(time.time() - self._started)
            m, s = divmod(s, 60)
            self._elapsed.setText(f"{m:02d}:{s:02d}")

    def closeEvent(self, e):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
