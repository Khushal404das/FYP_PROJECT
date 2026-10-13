<?php
/**
 * search.php — Vehicle Search & Journey Tracker
 * User inputs a vehicle (image or description), system finds it across all cameras.
 */
$config = require __DIR__ . '/../config/config.php';
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vehicle Search — FAST NUCES Vision-Mixer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg-base:     #090d14;
  --bg-card:     #0d1421;
  --bg-elevated: #131d2e;
  --border:      #1e2d45;
  --border-glow: #1e6fff44;
  --accent-blue: #1e6fff;
  --accent-green:#00e676;
  --accent-amber:#ffab00;
  --accent-red:  #ff4444;
  --accent-purple:#a855f7;
  --text:        #e2e8f0;
  --text-muted:  #64748b;
  --text-dim:    #334155;
  --font-main:   'Inter', sans-serif;
  --font-mono:   'JetBrains Mono', monospace;
  --radius:      10px;
  --radius-sm:   6px;
  --glow-blue:   0 0 20px #1e6fff33;
  --glow-green:  0 0 20px #00e67633;
}
*, *::before, *::after { box-sizing: border-box; margin:0; padding:0; }
html, body { height:100%; background:var(--bg-base); color:var(--text);
             font-family:var(--font-main); overflow:hidden; }

/* ── Navbar ── */
.navbar {
  display:flex; align-items:center; justify-content:space-between;
  padding:0 24px; height:56px; background:rgba(9,13,20,0.95);
  border-bottom:1px solid var(--border); backdrop-filter:blur(12px);
  position:fixed; top:0; left:0; right:0; z-index:100;
}
.brand { display:flex; align-items:center; gap:12px; }
.brand-icon { width:32px; height:32px; background:var(--accent-blue);
  border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:16px; }
.brand-title { font-size:13px; font-weight:700; letter-spacing:0.08em;
               color:#fff; font-family:var(--font-mono); }
.brand-sub { font-size:10px; color:var(--text-muted); margin-top:1px; }
.navbar-links { display:flex; gap:8px; }
.nav-link { padding:6px 14px; border-radius:6px; font-size:12px; font-weight:500;
  color:var(--text-muted); text-decoration:none; transition:all .2s;
  border:1px solid transparent; }
.nav-link:hover { color:var(--text); background:var(--bg-elevated); border-color:var(--border); }
.nav-link.active { color:var(--accent-blue); background:#1e6fff11;
  border-color:var(--accent-blue)44; }

/* ── Layout ── */
.layout {
  display:grid;
  grid-template-columns: 360px 1fr 320px;
  gap:0;
  height:calc(100vh - 56px);
  margin-top:56px;
  overflow:hidden;
}

/* ── Panel base ── */
.panel {
  border-right:1px solid var(--border);
  overflow-y:auto;
  overflow-x:hidden;
  padding:20px;
  display:flex;
  flex-direction:column;
  gap:16px;
}
.panel:last-child { border-right:none; }
.panel-center { padding:20px; display:flex; flex-direction:column; gap:16px; overflow:hidden; }

/* ── Card ── */
.card {
  background:var(--bg-card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  overflow:hidden;
}
.card-header {
  display:flex; align-items:center; justify-content:space-between;
  padding:12px 16px; border-bottom:1px solid var(--border);
  background:var(--bg-elevated);
}
.card-title { font-size:11px; font-weight:700; letter-spacing:0.08em;
              color:var(--text-muted); text-transform:uppercase; }
.card-body { padding:16px; }

/* ── Search Form ── */
.search-hero {
  text-align:center; padding:16px 16px 0;
}
.search-hero h1 {
  font-size:18px; font-weight:800; color:#fff; margin-bottom:4px;
  background:linear-gradient(135deg,#fff,var(--accent-blue));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.search-hero p { font-size:11px; color:var(--text-muted); line-height:1.5; }

/* Tabs */
.tabs { display:flex; gap:4px; padding:4px; background:var(--bg-base);
  border-radius:8px; margin-bottom:16px; }
.tab-btn { flex:1; padding:8px; font-size:11px; font-weight:600;
  font-family:var(--font-main); border:none; border-radius:6px; cursor:pointer;
  background:transparent; color:var(--text-muted); transition:all .2s; }
.tab-btn.active { background:var(--accent-blue); color:#fff; }
.tab-content { display:none; }
.tab-content.active { display:block; }

/* Upload Zone */
.upload-zone {
  border:2px dashed var(--border); border-radius:var(--radius);
  padding:28px 16px; text-align:center; cursor:pointer;
  transition:all .3s; position:relative; background:var(--bg-base);
}
.upload-zone:hover, .upload-zone.drag-over {
  border-color:var(--accent-blue); background:#1e6fff08; }
.upload-zone input[type=file] { position:absolute; inset:0; opacity:0; cursor:pointer; }
.upload-icon { font-size:28px; margin-bottom:8px; }
.upload-title { font-size:13px; font-weight:600; color:var(--text); margin-bottom:4px; }
.upload-sub { font-size:11px; color:var(--text-muted); }
#imagePreview { width:100%; border-radius:8px; margin-top:12px;
  display:none; max-height:140px; object-fit:cover; }

/* Form fields */
.field-group { display:flex; flex-direction:column; gap:4px; margin-bottom:12px; }
.field-label { font-size:11px; font-weight:600; color:var(--text-muted);
               text-transform:uppercase; letter-spacing:0.05em; }
.field-input, .field-select {
  background:var(--bg-base); border:1px solid var(--border); border-radius:6px;
  padding:8px 12px; color:var(--text); font-size:12px; font-family:var(--font-main);
  width:100%; transition:border-color .2s; outline:none;
}
.field-input:focus, .field-select:focus { border-color:var(--accent-blue); }
.color-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:6px; }
.color-opt { width:100%; aspect-ratio:1; border-radius:6px; border:2px solid transparent;
  cursor:pointer; transition:all .2s; }
.color-opt.selected { border-color:#fff; transform:scale(1.1); box-shadow:0 0 10px #fff4; }

/* Search Button */
.btn-search {
  width:100%; padding:12px; background:var(--accent-blue); border:none;
  border-radius:8px; color:#fff; font-size:13px; font-weight:700;
  font-family:var(--font-main); cursor:pointer; transition:all .3s;
  display:flex; align-items:center; justify-content:center; gap:8px;
}
.btn-search:hover { background:#3d7fff; box-shadow:var(--glow-blue); transform:translateY(-1px); }
.btn-search:disabled { background:var(--bg-elevated); color:var(--text-muted); cursor:not-allowed; transform:none; }

/* Progress */
.progress-wrap { display:none; }
.progress-wrap.active { display:block; }
.progress-label { font-size:11px; color:var(--text-muted); margin-bottom:6px;
  display:flex; justify-content:space-between; }
.progress-bar { height:4px; background:var(--bg-base); border-radius:4px; overflow:hidden; }
.progress-fill { height:100%; background:linear-gradient(90deg,var(--accent-blue),var(--accent-purple));
  border-radius:4px; transition:width .5s ease; width:0%; }
.scanning-cam { font-size:10px; font-family:var(--font-mono);
  color:var(--accent-blue); margin-top:6px; }

/* ── Centre: Camera View ── */
.cam-view {
  flex:1; background:#000; border-radius:var(--radius); overflow:hidden;
  position:relative; min-height:0;
}
.cam-view video { width:100%; height:100%; object-fit:cover; }
.cam-overlay {
  position:absolute; inset:0; pointer-events:none;
  border:2px solid transparent; border-radius:var(--radius); transition:border-color .3s;
}
.cam-overlay.tracking { border-color:var(--accent-green);
  box-shadow:inset 0 0 30px #00e67618; }
.cam-badge {
  position:absolute; top:12px; left:12px;
  background:rgba(0,0,0,0.7); backdrop-filter:blur(8px);
  border:1px solid var(--border); border-radius:6px;
  padding:4px 10px; font-size:11px; font-weight:600;
  font-family:var(--font-mono); color:#fff;
}
.cam-badge.live { border-color:var(--accent-green); color:var(--accent-green); }
.cam-badge.searching { border-color:var(--accent-amber); color:var(--accent-amber); }
.cam-badge.found { border-color:var(--accent-green); color:var(--accent-green); }
.cam-no-signal {
  position:absolute; inset:0; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:8px;
  color:var(--text-muted); font-size:13px;
}
.cam-no-signal .icon { font-size:40px; opacity:0.3; }

/* Target box overlay on canvas */
#detectionCanvas {
  position:absolute; inset:0; width:100%; height:100%;
  pointer-events:none;
}

/* ── Right: Journey Timeline ── */
.journey-empty {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:8px; padding:32px; color:var(--text-muted); text-align:center;
}
.journey-empty .icon { font-size:36px; opacity:0.3; }
.journey-empty p { font-size:12px; line-height:1.6; }

.journey-item {
  display:flex; gap:12px; padding:12px;
  border-radius:8px; background:var(--bg-elevated);
  border:1px solid var(--border); transition:all .3s;
  animation: slideIn .4s ease;
}
.journey-item.active-cam { border-color:var(--accent-green);
  background:#00e67608; box-shadow:var(--glow-green); }
@keyframes slideIn { from { opacity:0; transform:translateX(20px); } to { opacity:1; transform:translateX(0); } }

.journey-thumb {
  width:80px; min-width:80px; height:50px; background:var(--bg-base);
  border-radius:6px; overflow:hidden; border:1px solid var(--border);
}
.journey-thumb img { width:100%; height:100%; object-fit:cover; }
.journey-thumb .no-thumb {
  width:100%; height:100%; display:flex; align-items:center; justify-content:center;
  font-size:18px; color:var(--text-dim);
}
.journey-info { flex:1; min-width:0; }
.journey-cam { font-size:12px; font-weight:700; color:#fff;
  display:flex; align-items:center; gap:6px; margin-bottom:3px; }
.cam-status-dot { width:6px; height:6px; border-radius:50%; background:var(--text-dim); }
.cam-status-dot.active { background:var(--accent-green);
  box-shadow:0 0 6px var(--accent-green); animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.4;} }
.journey-time { font-size:10px; font-family:var(--font-mono); color:var(--text-muted); }
.journey-dur { font-size:10px; color:var(--accent-blue); margin-top:2px; }
.journey-sim { font-size:9px; font-family:var(--font-mono); color:var(--accent-green); }
.journey-line { width:2px; background:linear-gradient(var(--accent-blue),var(--accent-purple));
  margin:4px 0 4px 39px; height:12px; }

/* Stats row */
.stats-row { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
.stat-mini { background:var(--bg-elevated); border:1px solid var(--border);
  border-radius:8px; padding:10px; text-align:center; }
.stat-mini-val { font-size:20px; font-weight:800; color:#fff;
  font-family:var(--font-mono); line-height:1; }
.stat-mini-lbl { font-size:9px; color:var(--text-muted); margin-top:3px;
  text-transform:uppercase; letter-spacing:0.06em; }

/* Result found banner */
.result-banner {
  display:none; padding:10px 14px; border-radius:8px; font-size:12px; font-weight:600;
  margin-bottom:4px; text-align:center; animation:fadeIn .4s;
}
.result-banner.success { background:#00e67618; border:1px solid #00e67644; color:var(--accent-green); display:block; }
.result-banner.notfound { background:#ff444418; border:1px solid #ff444444; color:var(--accent-red); display:block; }
@keyframes fadeIn { from{opacity:0;transform:translateY(-8px);} to{opacity:1;transform:translateY(0);} }

/* ── Scrollbar ── */
::-webkit-scrollbar { width:4px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:4px; }
</style>
</head>
<body>

<!-- Navbar -->
<nav class="navbar">
  <div class="brand">
    <div class="brand-icon">🔍</div>
    <div>
      <div class="brand-title">VISION-MIXER — VEHICLE SEARCH</div>
      <div class="brand-sub">Find any vehicle across all 18 cameras in real-time</div>
    </div>
  </div>
  <div class="navbar-links">
    <a href="index.php" class="nav-link">📡 Live Dashboard</a>
    <a href="search.php" class="nav-link active">🔍 Vehicle Search</a>
  </div>
</nav>

<!-- Main 3-column layout -->
<div class="layout">

  <!-- ── LEFT: Search Query Panel ── -->
  <div class="panel">
    <div class="search-hero">
      <h1>Search a Vehicle</h1>
      <p>Upload a vehicle photo or describe it by colour & type. The system will scan all 18 cameras and show its route.</p>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-title">🚗 Vehicle Query</span>
        <span id="queryModeTag" style="font-size:10px;color:var(--accent-blue);font-family:var(--font-mono);">IMAGE MODE</span>
      </div>
      <div class="card-body">
        <!-- Mode Tabs -->
        <div class="tabs" style="margin-bottom:14px;">
          <button class="tab-btn active" id="tabImage" onclick="switchTab('image')">📷 Image Upload</button>
          <button class="tab-btn"        id="tabDesc"  onclick="switchTab('description')">📝 Description</button>
        </div>

        <!-- Tab: Image Upload -->
        <div class="tab-content active" id="contentImage">
          <div class="upload-zone" id="uploadZone">
            <input type="file" id="vehicleImage" accept="image/*" onchange="handleImageSelect(this)">
            <div class="upload-icon">📤</div>
            <div class="upload-title">Drop vehicle image here</div>
            <div class="upload-sub">JPG, PNG, WEBP — Max 10 MB</div>
          </div>
          <img id="imagePreview" alt="Vehicle preview">
        </div>

        <!-- Tab: Description -->
        <div class="tab-content" id="contentDescription">
          <div class="field-group">
            <label class="field-label">Vehicle Colour</label>
            <div class="color-grid" id="colorGrid">
              <!-- Populated by JS -->
            </div>
            <input type="hidden" id="selectedColor" value="white">
          </div>

          <div class="field-group">
            <label class="field-label">Vehicle Type</label>
            <select id="vehicleType" class="field-select">
              <option value="any">Any Type</option>
              <option value="car">🚗 Car / Sedan</option>
              <option value="motorcycle">🏍️ Motorcycle / Bike</option>
              <option value="bus">🚌 Bus</option>
              <option value="truck">🚚 Truck</option>
              <option value="bicycle">🚲 Bicycle</option>
            </select>
          </div>

          <div class="field-group">
            <label class="field-label">Plate Number (optional)</label>
            <input type="text" id="plateNumber" class="field-input"
              placeholder="e.g. ICT-5421" maxlength="20"
              style="text-transform:uppercase;font-family:var(--font-mono);">
          </div>
        </div>
      </div>
    </div>

    <!-- Search Options -->
    <div class="card">
      <div class="card-header"><span class="card-title">⚙️ Search Scope</span></div>
      <div class="card-body">
        <div class="field-group">
          <label class="field-label">Zone / Camera Set</label>
          <select id="searchZone" class="field-select">
            <option value="all">All 18 Cameras</option>
            <?php foreach ($config['zones'] as $name => $cams): ?>
              <option value="<?= htmlspecialchars($name) ?>"><?= htmlspecialchars($name) ?> (<?= count($cams) ?> cams)</option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="field-group">
          <label class="field-label">Confidence Threshold</label>
          <input type="range" id="confRange" min="30" max="80" value="52"
            oninput="document.getElementById('confVal').textContent = this.value + '%'"
            style="width:100%;accent-color:var(--accent-blue);">
          <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-muted);margin-top:2px;">
            <span>Low (more matches)</span>
            <span id="confVal">52%</span>
            <span>High (strict)</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Search button + progress -->
    <button class="btn-search" id="searchBtn" onclick="startSearch()">
      <span>🔍</span> Start Vehicle Search
    </button>
    <button class="btn-search" id="stopBtn" style="display:none;background:#ff444422;border:1px solid #ff444444;color:var(--accent-red);"
      onclick="stopSearch()">
      ⏹ Cancel Search
    </button>

    <div class="progress-wrap" id="progressWrap">
      <div class="progress-label">
        <span>Scanning cameras…</span>
        <span id="progressPct">0%</span>
      </div>
      <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
      <div class="scanning-cam" id="scanningCam">Initialising YOLO model…</div>
    </div>

    <div id="resultBanner" class="result-banner"></div>
  </div>

  <!-- ── CENTER: Live Camera Feed ── -->
  <div class="panel-center">
    <div class="card" style="flex:1;min-height:0;display:flex;flex-direction:column;">
      <div class="card-header">
        <span class="card-title" id="centerTitle">📷 Camera Feed</span>
        <span id="centerCamBadge" class="cam-badge">SELECT CAMERA</span>
      </div>
      <div class="cam-view" style="flex:1;min-height:0;">
        <video id="mainVideo" autoplay muted loop playsinline></video>
        <canvas id="detectionCanvas"></canvas>
        <div class="cam-overlay" id="camOverlay"></div>
        <div class="cam-badge" id="liveBadge" style="display:none;">● TRACKING</div>
        <div class="cam-no-signal" id="noSignal">
          <div class="icon">📡</div>
          <div>Submit a search query to begin<br>scanning camera feeds</div>
        </div>
      </div>
    </div>

    <!-- Mini stats -->
    <div class="stats-row">
      <div class="stat-mini">
        <div class="stat-mini-val" id="statCamsFound" style="color:var(--accent-green);">0</div>
        <div class="stat-mini-lbl">Cameras Found</div>
      </div>
      <div class="stat-mini">
        <div class="stat-mini-val" id="statScanned" style="color:var(--accent-blue);">0/18</div>
        <div class="stat-mini-lbl">Cameras Scanned</div>
      </div>
      <div class="stat-mini">
        <div class="stat-mini-val" id="statDuration" style="color:var(--accent-purple);">0s</div>
        <div class="stat-mini-lbl">Total Duration</div>
      </div>
    </div>
  </div>

  <!-- ── RIGHT: Journey Timeline ── -->
  <div class="panel" style="border-left:1px solid var(--border);border-right:none;">
    <div class="card-header" style="background:var(--bg-card);border-radius:8px;">
      <span class="card-title">🗺️ Vehicle Journey</span>
      <span id="journeyCount" style="font-size:10px;font-family:var(--font-mono);
        color:var(--accent-blue);">0 sightings</span>
    </div>

    <div id="journeyList">
      <div class="journey-empty">
        <div class="icon">🗺️</div>
        <p>Vehicle route will appear here as cameras are scanned.<br>
        Each card shows where and when the vehicle was spotted.</p>
      </div>
    </div>
  </div>
</div>

<script>
// ─── State ────────────────────────────────────────────────────────────────────
let searchMode     = 'image';
let selectedColor  = 'white';
let searchActive   = false;
let pollTimer      = null;
let currentSearchId = null;
let journeyData    = [];
let videoSources   = {};  // cam_id -> video url

const COLORS = [
  {name:'white',  hex:'#e8e8e8'}, {name:'silver', hex:'#b0b8c8'},
  {name:'gray',   hex:'#6b7280'}, {name:'black',  hex:'#1f2937'},
  {name:'red',    hex:'#ef4444'}, {name:'orange', hex:'#f97316'},
  {name:'yellow', hex:'#eab308'}, {name:'green',  hex:'#22c55e'},
  {name:'blue',   hex:'#3b82f6'}, {name:'brown',  hex:'#92400e'},
];

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildColorGrid();
  setupDragDrop();
});

function buildColorGrid() {
  const grid = document.getElementById('colorGrid');
  COLORS.forEach(c => {
    const d = document.createElement('div');
    d.className = 'color-opt' + (c.name === 'white' ? ' selected' : '');
    d.style.background = c.hex;
    d.title = c.name;
    d.onclick = () => selectColor(c.name, d);
    grid.appendChild(d);
  });
}

function selectColor(name, el) {
  selectedColor = name;
  document.getElementById('selectedColor').value = name;
  document.querySelectorAll('.color-opt').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
}

function switchTab(mode) {
  searchMode = mode;
  document.getElementById('tabImage').classList.toggle('active', mode === 'image');
  document.getElementById('tabDesc').classList.toggle('active', mode === 'description');
  document.getElementById('contentImage').classList.toggle('active', mode === 'image');
  document.getElementById('contentDescription').classList.toggle('active', mode === 'description');
  document.getElementById('queryModeTag').textContent = mode === 'image' ? 'IMAGE MODE' : 'DESCRIPTION MODE';
}

function setupDragDrop() {
  const zone = document.getElementById('uploadZone');
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave',() => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) previewImage(file);
  });
}

function handleImageSelect(input) {
  if (input.files[0]) previewImage(input.files[0]);
}

function previewImage(file) {
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById('imagePreview');
    img.src = e.target.result;
    img.style.display = 'block';
  };
  reader.readAsDataURL(file);
}

// ─── Search ───────────────────────────────────────────────────────────────────
async function startSearch() {
  if (searchActive) return;

  // Build form data
  const fd = new FormData();
  fd.append('mode', searchMode);

  if (searchMode === 'image') {
    const fileInput = document.getElementById('vehicleImage');
    if (!fileInput.files[0]) {
      alert('Please upload a vehicle image first.'); return;
    }
    fd.append('image', fileInput.files[0]);
  } else {
    fd.append('color', selectedColor);
    fd.append('vehicle_type', document.getElementById('vehicleType').value);
    fd.append('plate', document.getElementById('plateNumber').value.trim().toUpperCase());
  }

  const zone = document.getElementById('searchZone').value;
  const conf = document.getElementById('confRange').value;
  fd.append('zone', zone);
  fd.append('confidence', conf);

  // UI: searching state
  searchActive = true;
  setSearching(true);
  clearJourney();
  hideNoSignal(false);

  try {
    const res  = await fetch('api.php?action=submit_search', {method:'POST', body:fd});
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Search failed');
    currentSearchId = data.search_id;
    pollStatus();
  } catch(e) {
    showError(e.message);
    setSearching(false);
  }
}

function stopSearch() {
  if (pollTimer) clearInterval(pollTimer);
  searchActive = false;
  setSearching(false);
}

function pollStatus() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const res  = await fetch(`api.php?action=search_status&id=${currentSearchId}`);
      const data = await res.json();
      updateProgress(data);
      if (data.status === 'done' || data.status === 'error') {
        clearInterval(pollTimer);
        searchActive = false;
        setSearching(false);
        onSearchComplete(data);
      }
    } catch(e) {}
  }, 1500);
}

function updateProgress(data) {
  const total  = data.cameras_total || 18;
  const done   = data.cameras_done  || 0;
  const pct    = Math.round((done / total) * 100);
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressPct').textContent  = pct + '%';
  if (data.current_cam) {
    document.getElementById('scanningCam').textContent =
      `▶ Scanning ${data.current_cam}… (${done}/${total})`;
    loadCameraFeed(data.current_cam, false);
  }

  // Update journey as it arrives
  if (data.journey && data.journey.length > journeyData.length) {
    const newItems = data.journey.slice(journeyData.length);
    newItems.forEach(item => addJourneyItem(item));
    journeyData = data.journey;
    updateStats(data);
  }

  document.getElementById('statScanned').textContent = `${done}/${total}`;
}

function onSearchComplete(data) {
  if (data.status === 'error') {
    showError(data.error || 'Search failed'); return;
  }
  const journey = data.journey || [];
  const banner  = document.getElementById('resultBanner');
  if (journey.length > 0) {
    banner.className = 'result-banner success';
    banner.textContent = `✅ Vehicle found in ${journey.length} camera(s)!`;
    // Switch to last confirmed camera
    const last = journey[journey.length-1];
    loadCameraFeed(last.camera_id, true);
  } else {
    banner.className = 'result-banner notfound';
    banner.textContent = '❌ Vehicle not found in any camera feed.';
    hideNoSignal(true);
  }
  document.getElementById('scanningCam').textContent = 'Search complete.';
  document.getElementById('progressFill').style.width = '100%';
  document.getElementById('progressPct').textContent  = '100%';
}

// ─── Camera Feed ──────────────────────────────────────────────────────────────
function loadCameraFeed(camId, tracking) {
  const vid    = document.getElementById('mainVideo');
  const newSrc = `api.php?action=stream_video&camera=${camId}`;
  if (vid.src !== location.origin + '/' + newSrc) {
    vid.src = newSrc;
    vid.load();
  }
  hideNoSignal(false);
  document.getElementById('centerTitle').textContent = `📷 ${camId} — Live Feed`;
  document.getElementById('centerCamBadge').textContent = camId;
  const overlay = document.getElementById('camOverlay');
  const liveBadge = document.getElementById('liveBadge');
  if (tracking) {
    overlay.className = 'cam-overlay tracking';
    liveBadge.style.display = 'block';
    liveBadge.className = 'cam-badge found';
    liveBadge.textContent = '● VEHICLE FOUND';
  } else {
    overlay.className = 'cam-overlay';
    liveBadge.style.display = 'block';
    liveBadge.className = 'cam-badge searching';
    liveBadge.textContent = '⟳ SCANNING…';
  }
  // Highlight active journey item
  document.querySelectorAll('.journey-item').forEach(el => {
    el.classList.toggle('active-cam', el.dataset.cam === camId);
    const dot = el.querySelector('.cam-status-dot');
    if (dot) dot.className = 'cam-status-dot' + (el.dataset.cam === camId ? ' active' : '');
  });
}

// ─── Journey Timeline ─────────────────────────────────────────────────────────
function addJourneyItem(item) {
  const list = document.getElementById('journeyList');
  // Remove empty state
  const empty = list.querySelector('.journey-empty');
  if (empty) empty.remove();

  // Connector line (after first)
  if (journeyData.length > 0) {
    const line = document.createElement('div');
    line.className = 'journey-line';
    list.appendChild(line);
  }

  const div = document.createElement('div');
  div.className = 'journey-item';
  div.dataset.cam = item.camera_id;
  div.onclick = () => loadCameraFeed(item.camera_id, true);
  div.style.cursor = 'pointer';
  div.innerHTML = `
    <div class="journey-thumb">
      ${item.thumbnail
        ? `<img src="${item.thumbnail}?t=${Date.now()}" alt="${item.camera_id}" onerror="this.parentElement.innerHTML='<div class=\\"no-thumb\\">📷</div>'">`
        : '<div class="no-thumb">📷</div>'}
    </div>
    <div class="journey-info">
      <div class="journey-cam">
        <span class="cam-status-dot"></span>
        <strong>${item.camera_id}</strong>
      </div>
      <div class="journey-time">
        In: ${item.entry_time} → Out: ${item.exit_time}
      </div>
      <div class="journey-dur">⏱ ${item.duration_sec}s on camera</div>
      <div class="journey-sim">Match: ${Math.round(item.similarity * 100)}%</div>
    </div>
  `;
  list.appendChild(div);
  list.scrollTop = list.scrollHeight;
}

function clearJourney() {
  journeyData = [];
  document.getElementById('journeyList').innerHTML = `
    <div class="journey-empty">
      <div class="icon">🗺️</div>
      <p>Scanning cameras… journey route will appear here.</p>
    </div>`;
  document.getElementById('journeyCount').textContent = '0 sightings';
  updateStats({journey:[]});
}

function updateStats(data) {
  const j = data.journey || [];
  document.getElementById('statCamsFound').textContent = j.length;
  document.getElementById('journeyCount').textContent  = `${j.length} sightings`;
  const totalSec = j.reduce((s, c) => s + (c.duration_sec||0), 0);
  document.getElementById('statDuration').textContent  = totalSec + 's';
}

// ─── UI Helpers ───────────────────────────────────────────────────────────────
function setSearching(active) {
  document.getElementById('searchBtn').style.display = active ? 'none' : 'flex';
  document.getElementById('stopBtn').style.display   = active ? 'flex' : 'none';
  document.getElementById('progressWrap').classList.toggle('active', active);
  if (active) {
    document.getElementById('progressFill').style.width = '0%';
    document.getElementById('progressPct').textContent  = '0%';
    document.getElementById('resultBanner').className   = 'result-banner';
  }
}

function hideNoSignal(show) {
  document.getElementById('noSignal').style.display    = show ? 'flex' : 'none';
  document.getElementById('mainVideo').style.display   = show ? 'none' : 'block';
}

function showError(msg) {
  const b = document.getElementById('resultBanner');
  b.className   = 'result-banner notfound';
  b.textContent = '⚠️ Error: ' + msg;
  document.getElementById('scanningCam').textContent = 'Search failed.';
}
</script>
</body>
</html>
