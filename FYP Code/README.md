# FYP Vehicle Tracking System — "VehicleTrack"

> **Multi-Camera Vehicle Tracking & Re-Identification**  
> Final Year Project | PHP Frontend + Python Backend  
> Inspired by: 2019 CVPR AI City Challenge (Track 1, 2, 3) & TNT Tracker

---

## 🚗 What It Does

Given a **vehicle image** or a **text description** (color, type, plate), the system:

1. Searches all camera feeds for that vehicle
2. Shows **which cameras** the vehicle passed through
3. Displays the **exact route** (Camera → Camera) as a timeline
4. Tracks vehicles **continuously** until they leave the network

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHP Frontend (Port 8080)                      │
│   dashboard.php │ query.php │ tracks.php │ cameras.php           │
│   process.php   │ config.php │ api/proxy.php                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP REST calls
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Python Flask API (Port 5000)                     │
│   api_server.py  →  vehicle_tracker.py                          │
│                                                                 │
│   VehicleFeatureExtractor  (color histogram + HOG features)     │
│   SimpleVehicleDetector    (MOG2 background subtraction)        │
│   SingleCameraTracker      (IoU-based tracklet association)     │
│   CrossCameraReID          (feature similarity + topology)      │
│   VehicleQueryMatcher      (image or description matching)      │
└──────────────────────────────────────────────────────────────── ┘
```

### Camera Network
```
C11 → C12 → C21 → C22 → C41 → C42 → C43 → C61 → C62 → C63 → C64 → C65
              ↓     ↓    ↑
             C23   C31 → C32
              ↓
             C24 → C51 → C52 → C61
```

---

## 📁 Project Structure

```
FYP Code/
├── launch.bat                  ← START HERE (launches both servers)
├── start_api_server.bat        ← Python API only
├── start_php_server.bat        ← PHP frontend only
│
├── python_backend/
│   ├── vehicle_tracker.py      ← Core tracking engine
│   ├── api_server.py           ← Flask REST API
│   ├── demo_seed.py            ← Seed demo data (run once)
│   └── requirements.txt
│
└── php_frontend/
    ├── index.php               ← Entry (redirects to dashboard)
    ├── config.php              ← Config + API helper
    ├── dashboard.php           ← System overview
    ├── query.php               ← Search by image / description
    ├── tracks.php              ← Vehicle journey timeline
    ├── cameras.php             ← Camera network map
    ├── process.php             ← Process video files
    ├── css/style.css           ← Premium dark UI stylesheet
    ├── js/app.js               ← Interactive JS
    ├── api/proxy.php           ← PHP → Python proxy
    └── uploads/                ← User uploaded images/videos
```

---

## 🚀 Quick Start

### Prerequisites

| Software | Version | Download |
|----------|---------|----------|
| Python   | 3.8+    | https://python.org |
| PHP      | 8.0+    | https://windows.php.net |
| pip      | latest  | (comes with Python) |

### Step 1 — Install Python Dependencies

```bash
cd "FYP Code\python_backend"
pip install -r requirements.txt
```

### Step 2 — (Optional) Seed Demo Data

```bash
python demo_seed.py
```
This creates 10 synthetic vehicle tracks so you can explore the UI immediately.

### Step 3 — Launch the System

**Double-click `launch.bat`** — it opens both servers and your browser.

Or run manually in two separate terminals:

```bash
# Terminal 1 — Python API
python "FYP Code\python_backend\api_server.py"

# Terminal 2 — PHP Frontend  
cd "FYP Code\php_frontend"
php -S 127.0.0.1:8080 -t .
```

### Step 4 — Open Browser

- **Dashboard:** http://127.0.0.1:8080/dashboard.php
- **Search Vehicle:** http://127.0.0.1:8080/query.php
- **Track Journeys:** http://127.0.0.1:8080/tracks.php
- **Camera Network:** http://127.0.0.1:8080/cameras.php
- **Process Video:** http://127.0.0.1:8080/process.php

---

## 🔍 How to Use

### Search by Image
1. Go to **Query Vehicle** page
2. Select **"Search by Image"** tab
3. Upload a photo of the vehicle (drag & drop supported)
4. Click **Search Vehicle**
5. Results show matched vehicles with similarity scores
6. Click any result to see the full camera journey

### Search by Description
1. Go to **Query Vehicle** page
2. Select **"Search by Description"** tab
3. Fill in: Color, Vehicle Type, License Plate, Last Known Camera
4. Click **Search Vehicle**

### Process a Camera Video
1. Go to **Process Video** page
2. Select a camera from the dropdown (shows which have dataset videos)
3. Set frame limit (200 is good for testing)
4. Click **Start Processing**
5. Wait for the API to analyze the video and extract vehicles

### View Vehicle Journey
1. Go to **Track Journeys** page
2. Select a Global ID from the dropdown
3. See the full camera-by-camera timeline with timestamps

---

## 🧠 Technical Details

### Re-Identification Method (inspired by AIC Track 2 UWIPL)
- **Feature extraction:** Multi-channel HSV color histogram (3×32 bins) + HOG gradient histogram (64 bins) = 160-dim feature vector
- **Similarity metric:** Cosine similarity
- **Cross-camera matching threshold:** 0.65 (configurable)

### Single-Camera Tracking (inspired by TNT Tracker)
- **Detection:** MOG2 background subtraction + morphological filtering
- **Association:** IoU-based greedy matching (threshold: 0.3)
- **Feature update:** Exponential moving average (EMA: α=0.3)
- **Track termination:** 30 frames without detection

### Camera Topology (inspired by AIC Track 1 Transition Model)
- Hard-coded transition graph based on physical camera placement
- Only allows cross-camera ReID matches between topologically adjacent cameras
- Prevents impossible matches (e.g., C11 → C65 directly)

---

## 🎛️ API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/status`           | Health check + stats |
| GET    | `/api/cameras`          | All cameras + topology |
| GET    | `/api/summary`          | All tracked vehicles |
| GET    | `/api/journey/<gid>`    | Journey for vehicle ID |
| POST   | `/api/query_image`      | Match by image |
| POST   | `/api/query_description`| Match by text |
| POST   | `/api/process_video`    | Process dataset camera |
| POST   | `/api/process_upload_video` | Process uploaded video |
| POST   | `/api/reset`            | Clear all data |

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Alt+D`  | Dashboard |
| `Alt+Q`  | Query Vehicle |
| `Alt+T`  | Track Journeys |

---

## 📊 Dataset

The system uses camera videos from the dataset directory:
- 18 camera feeds: `camera_c11.mp4` through `camera_c65.mp4`
- Device log files: `D23_*.txt`, `D24_*.txt` (Hikvision DVR logs)

---

## 🔬 Research Basis

| Component | Source |
|-----------|--------|
| Multi-camera tracking framework | AIC Track 1 UWIPL (CVPR 2019) |
| Vehicle ReID model | AIC Track 2 UWIPL (Video-Person-ReID) |
| Traffic anomaly detection | AIC Track 3 UWIPL |
| Single-camera tracker | TNT (TrackletNet Tracker) |

---

*FYP Vehicle Tracking System — University Project*
