# Multi-Camera Vehicle Tracking and Re-Identification System (FYP)

An end-to-end intelligent transportation surveillance platform featuring real-time multi-camera vehicle detection, single-camera tracking (SORT), temporal feature extraction (ResNet-50 Temporal Attention), and cross-camera vehicle re-identification (Re-ID).

---

## 🚀 Key Features

- **Real-Time Vehicle Detection:** Powered by YOLOv8 for detecting vehicles (`car`, `bus`, `truck`, `motorcycle`, `bicycle`) while filtering out noise and non-vehicle classes.
- **Single-Camera Tracking (SORT):** Multi-object tracking with Hungarian algorithm and IoU association for stable tracklet generation without flickering.
- **Cross-Camera Re-Identification (Re-ID):** Preserves vehicle Global ID across multiple camera views based on visual feature extraction and spatio-temporal camera network topology.
- **Synchronized Video Playback:** Multi-camera streaming engine locked to a unified clock reference (`t=0.0s`) for synchronized multi-angle traffic monitoring.
- **Interactive Web Dashboard:** Modern PHP & Vanilla JavaScript frontend dashboard providing live camera feeds, active track journey views, query-by-image search, and camera topology monitoring.

---

## 🛠️ Tech Stack & Architecture

- **Backend:** Python 3.10+, PyTorch, OpenCV (`cv2`), Ultralytics YOLOv8, Flask, SQLite3
- **Frontend:** PHP 8.x, Vanilla CSS (Modern Dark Mode with glassmorphism), Vanilla JavaScript, MJPEG Streams
- **Dataset:** NVIDIA AI City Challenge (AIC Track 1 & Track 2 benchmark video feeds)

---

## 📂 Project Structure

```text
├── FYP Code/
│   ├── python_backend/
│   │   ├── api_server.py           # Flask REST API + MJPEG streaming endpoints
│   │   ├── streaming_engine.py      # Real-time multi-camera MJPEG streaming engine
│   │   ├── vehicle_tracker.py       # YOLOv8 + SORT + ResNet50TA + CrossCameraReID
│   │   └── yolov8n.pt               # YOLOv8 nano model weights
│   └── php_frontend/
│       ├── dashboard.php            # Main live multi-camera monitoring dashboard
│       ├── query.php                # Image-based vehicle search & re-identification
│       ├── tracks.php               # Vehicle journey and trajectory timeline
│       ├── cameras.php              # Camera network status and topology map
│       └── process.php              # Video processing interface
├── dataset/                         # Surveillance camera footage (camera_c*.mp4)
├── Final/                           # Research experiments, training scripts & data
├── TNT-master/                      # Tracklet-to-Target reference implementation
└── README.md
```

---

## ⚙️ Setup and Installation

### 1. Prerequisites
- Python 3.10+
- PHP 8.0+
- Git

### 2. Install Python Dependencies
```bash
cd "FYP Code/python_backend"
pip install torch torchvision ultralytics opencv-python flask flask-cors numpy pillow scipy
```

### 3. Add Dataset Videos
Place surveillance camera MP4 files inside the `dataset/` directory:
- `dataset/camera_c11.mp4`
- `dataset/camera_c21.mp4`
- `dataset/camera_c31.mp4`
- `dataset/camera_c41.mp4`
- `dataset/camera_c51.mp4`
- `dataset/camera_c61.mp4`

---

## ▶️ Running the Application

### Start Python Backend Server
```bash
cd "FYP Code/python_backend"
python api_server.py
```
*API server runs on `http://127.0.0.1:5000`*

### Start PHP Frontend Server
```bash
cd "FYP Code/php_frontend"
php -S 127.0.0.1:8080 -t .
```
*Frontend dashboard runs on `http://127.0.0.1:8080/dashboard.php`*
