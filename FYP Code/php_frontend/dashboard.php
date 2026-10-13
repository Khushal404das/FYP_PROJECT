<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FYP Vehicle Tracking System — Dashboard</title>
  <meta name="description" content="Multi-camera vehicle tracking and re-identification system. Track vehicles across camera networks in real time." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="css/style.css" />
</head>
<body>

<?php
require_once 'config.php';

// Fetch API status
$status = api_request('/status');
$cameras_data = api_request('/cameras');
$summary = api_request('/summary');
?>

<!-- ░░ SIDEBAR ░░ -->
<aside class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="logo-icon">
      <svg viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="18" stroke="url(#g1)" stroke-width="2"/><path d="M10 24L15 16L20 20L25 14L30 22" stroke="url(#g2)" stroke-width="2" stroke-linecap="round"/><defs><linearGradient id="g1" x1="2" y1="2" x2="38" y2="38"><stop stop-color="#6C63FF"/><stop offset="1" stop-color="#00D4FF"/></linearGradient><linearGradient id="g2" x1="10" y1="24" x2="30" y2="14"><stop stop-color="#FF6B9D"/><stop offset="1" stop-color="#FFD93D"/></linearGradient></defs></svg>
    </div>
    <div class="logo-text">
      <span class="logo-title">VehicleTrack</span>
      <span class="logo-sub">FYP System</span>
    </div>
  </div>

  <nav class="sidebar-nav">
    <a href="dashboard.php" class="nav-item active" id="nav-dashboard">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      Dashboard
    </a>
    <a href="query.php" class="nav-item" id="nav-query">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
      Query Vehicle
    </a>
    <a href="cameras.php" class="nav-item" id="nav-cameras">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
      Camera Network
    </a>
    <a href="tracks.php" class="nav-item" id="nav-tracks">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      Track Journeys
    </a>
    <a href="process.php" class="nav-item" id="nav-process">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
      Process Video
    </a>
  </nav>

  <div class="sidebar-status">
    <div class="status-dot <?= ($status['success'] ?? false) ? 'online' : 'offline' ?>"></div>
    <span><?= ($status['success'] ?? false) ? 'API Online' : 'API Offline' ?></span>
  </div>
</aside>

<!-- ░░ MAIN CONTENT ░░ -->
<main class="main-content">

  <!-- TOP BAR -->
  <header class="topbar">
    <div class="topbar-left">
      <button class="sidebar-toggle" onclick="document.getElementById('sidebar').classList.toggle('collapsed')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
      <h1 class="page-title">System Dashboard</h1>
    </div>
    <div class="topbar-right">
      <div class="topbar-time" id="clock"></div>
      <a href="query.php" class="btn btn-primary pulse-btn">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        Search Vehicle
      </a>
    </div>
  </header>

  <!-- STATS GRID -->
  <section class="stats-grid">
    <div class="stat-card glow-purple">
      <div class="stat-icon">🚗</div>
      <div class="stat-info">
        <div class="stat-value" id="stat-tracked"><?= $summary['total'] ?? 0 ?></div>
        <div class="stat-label">Tracked Vehicles</div>
      </div>
      <div class="stat-sparkline"></div>
    </div>
    <div class="stat-card glow-blue">
      <div class="stat-icon">📷</div>
      <div class="stat-info">
        <div class="stat-value"><?= count(json_decode(CAMERAS, true)) ?></div>
        <div class="stat-label">Active Cameras</div>
      </div>
    </div>
    <div class="stat-card glow-green">
      <div class="stat-icon">🛰️</div>
      <div class="stat-info">
        <div class="stat-value"><?= ($status['success'] ?? false) ? '<span class="badge-live">LIVE</span>' : '<span class="badge-off">OFF</span>' ?></div>
        <div class="stat-label">API Status</div>
      </div>
    </div>
    <div class="stat-card glow-orange">
      <div class="stat-icon">🗺️</div>
      <div class="stat-info">
        <div class="stat-value">6</div>
        <div class="stat-label">Camera Zones</div>
      </div>
    </div>
  </section>

  <!-- ░░ LIVE VIDEO MONITOR ░░ -->
  <section class="section-card live-monitor-section">
    <div class="section-header">
      <div class="live-monitor-title">
        <span class="live-dot-anim"></span>
        <h2>Live Detection Monitor</h2>
      </div>
      <!-- Camera selector buttons -->
      <div class="cam-selector" id="cam-selector">
        <?php
        $cams = json_decode(CAMERAS, true);
        $cam_statuses = $cameras_data['cameras'] ?? [];
        $first_active = null;
        foreach ($cams as $i => $cam):
          $has_vid = false;
          foreach ($cam_statuses as $cs) { if ($cs['id'] === $cam) { $has_vid = $cs['has_video']; break; } }
          if ($has_vid && $first_active === null) $first_active = $cam;
        ?>
        <?php if ($has_vid): ?>
        <button class="cam-btn <?= $i === 0 || ($first_active && $cam === $first_active) ? 'active' : '' ?>"
                data-cam="<?= $cam ?>"
                onclick="switchStream('<?= $cam ?>', this)">
          <?= strtoupper($cam) ?>
        </button>
        <?php endif; ?>
        <?php endforeach; ?>
        <button class="cam-btn" style="border-color:#00D4FF; color:#00D4FF; margin-left:8px;"
                onclick="restartAllCameras(this)" title="Rewind all cameras and play from beginning">
          ↺ Play from Start
        </button>
      </div>
    </div>

    <!-- Main stream + sidebar layout -->
    <div class="live-monitor-body">

      <!-- Main video player -->
      <div class="stream-player-wrap">
        <div class="stream-overlay-label" id="stream-cam-label">CAM <?= strtoupper($first_active ?? 'C21') ?></div>
        <img id="live-stream"
             src="http://127.0.0.1:5000/api/stream/<?= $first_active ?? 'c21' ?>?w=860&h=480"
             class="stream-img"
             alt="Live vehicle detection stream"
             onerror="this.src=''"
        />
        <div class="stream-no-signal" id="stream-no-signal" style="display:none">
          <span>⚠ Stream Unavailable</span>
          <small>Make sure the Python API is running on port 5000</small>
        </div>
      </div>

      <!-- Detected vehicles sidebar -->
      <div class="detection-sidebar">
        <div class="detection-sidebar-hdr">
          <span>🎯 Detected Now</span>
          <span class="det-count-badge" id="det-count">–</span>
        </div>
        <div class="detection-list" id="detection-list">
          <div class="det-loading">Waiting for detections…</div>
        </div>
        <div class="detection-sidebar-hdr" style="margin-top:14px">
          <span>📡 Camera Status</span>
        </div>
        <div class="cam-status-list" id="cam-status-list">
          <?php foreach ($cams as $cam):
            $has_vid = false;
            foreach ($cam_statuses as $cs) { if ($cs['id'] === $cam) { $has_vid = $cs['has_video']; break; } }
          ?>
          <div class="cam-status-row">
            <span class="cam-status-dot <?= $has_vid ? 'online' : 'offline' ?>"></span>
            <span class="cam-status-name"><?= strtoupper($cam) ?></span>
            <span class="cam-status-lbl"><?= $has_vid ? 'Active' : 'No Video' ?></span>
          </div>
          <?php endforeach; ?>
        </div>
      </div>
    </div>
  </section>

  <!-- CAMERA NETWORK MAP -->
  <section class="section-card">
    <div class="section-header">
      <h2>Camera Network Topology</h2>
      <span class="section-badge">Real-time</span>
    </div>
    <div class="camera-topology" id="topology-map">
      <?php
      $cams = json_decode(CAMERAS, true);
      $topology = $cameras_data['topology'] ?? [];
      foreach ($cams as $cam):
        $has_video = $cameras_data['cameras'][array_search($cam, array_column($cameras_data['cameras'] ?? [], 'id'))]['has_video'] ?? false;
      ?>
      <div class="topo-node <?= $has_video ? 'has-video' : '' ?>" data-cam="<?= $cam ?>"
           onclick="window.location='cameras.php?cam=<?= $cam ?>'"
           title="Camera <?= strtoupper($cam) ?>">
        <div class="topo-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 7l-7 5 7 5V7z"/>
            <rect x="1" y="5" width="15" height="14" rx="2"/>
          </svg>
        </div>
        <span><?= strtoupper($cam) ?></span>
        <?php if ($has_video): ?>
          <div class="topo-pulse"></div>
        <?php endif; ?>
      </div>
      <?php endforeach; ?>
    </div>
  </section>

  <!-- RECENT TRACKS TABLE -->
  <section class="section-card">
    <div class="section-header">
      <h2>Recently Tracked Vehicles</h2>
      <a href="tracks.php" class="btn btn-ghost btn-sm">View All →</a>
    </div>
    <div class="table-wrapper">
      <?php if (!empty($summary['tracks'])): ?>
      <table class="data-table">
        <thead>
          <tr>
            <th>Global ID</th>
            <th>Cameras Seen</th>
            <th>Sightings</th>
            <th>First Seen</th>
            <th>Last Seen</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <?php foreach (array_slice($summary['tracks'], 0, 10) as $track): ?>
          <tr class="table-row" onclick="window.location='tracks.php?gid=<?= $track['global_id'] ?>'">
            <td><span class="gid-badge">#<?= $track['global_id'] ?></span></td>
            <td>
              <?php foreach ($track['cameras'] as $c): ?>
                <?= cam_badge($c) ?>
              <?php endforeach; ?>
            </td>
            <td><?= $track['sightings'] ?></td>
            <td class="mono"><?= fmt_time($track['first_seen']) ?></td>
            <td class="mono"><?= fmt_time($track['last_seen']) ?></td>
            <td>
              <a href="tracks.php?gid=<?= $track['global_id'] ?>" class="btn btn-ghost btn-sm" onclick="event.stopPropagation()">Journey →</a>
            </td>
          </tr>
          <?php endforeach; ?>
        </tbody>
      </table>
      <?php else: ?>
      <div class="empty-state">
        <div class="empty-icon">🚗</div>
        <p>No vehicles tracked yet.</p>
        <a href="process.php" class="btn btn-primary">Process a Camera Video</a>
      </div>
      <?php endif; ?>
    </div>
  </section>

</main>

<style>
/* ── Live Monitor Section ─────────────────────────────────── */
.live-monitor-section { margin-bottom: 28px; }
.live-monitor-title { display:flex; align-items:center; gap:10px; }
.live-dot-anim {
  width:10px; height:10px; border-radius:50%;
  background:#ef4444;
  box-shadow:0 0 0 0 rgba(239,68,68,.4);
  animation: live-pulse 1.5s infinite;
  flex-shrink:0;
}
@keyframes live-pulse {
  0%   { box-shadow:0 0 0 0   rgba(239,68,68,.5); }
  70%  { box-shadow:0 0 0 10px rgba(239,68,68,0);  }
  100% { box-shadow:0 0 0 0   rgba(239,68,68,0);   }
}
.cam-selector { display:flex; gap:6px; flex-wrap:wrap; }
.cam-btn {
  padding:4px 11px; border-radius:6px; font-size:.72rem; font-weight:600;
  cursor:pointer; transition:.18s;
  background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12);
  color:#94a3b8;
}
.cam-btn:hover  { background:rgba(108,99,255,.25); color:#a5b4fc; border-color:#6C63FF; }
.cam-btn.active { background:rgba(108,99,255,.35); color:#fff;    border-color:#6C63FF; }

/* ── Main body layout ────────────────────────────────────── */
.live-monitor-body {
  display:grid;
  grid-template-columns: 1fr 240px;
  gap:18px;
  margin-top:14px;
}
@media(max-width:900px) { .live-monitor-body { grid-template-columns:1fr; } }

/* ── Stream player ───────────────────────────────────────── */
.stream-player-wrap {
  position:relative;
  background:#000;
  border-radius:12px;
  overflow:hidden;
  border:1px solid rgba(255,255,255,.08);
  min-height:300px;
  display:flex; align-items:center; justify-content:center;
}
.stream-overlay-label {
  position:absolute; top:10px; left:12px; z-index:3;
  background:rgba(0,0,0,.65); color:#00d4ff;
  font-size:.72rem; font-weight:700; letter-spacing:.08em;
  padding:3px 9px; border-radius:5px;
  border:1px solid rgba(0,212,255,.3);
  pointer-events:none;
}
.stream-img {
  width:100%; height:auto; display:block;
  border-radius:12px;
  object-fit:cover;
}
.stream-no-signal {
  display:flex; flex-direction:column; align-items:center;
  gap:8px; color:#64748b; padding:40px;
  font-size:.9rem;
}
.stream-no-signal small { font-size:.75rem; color:#475569; }

/* ── Detection sidebar ───────────────────────────────────── */
.detection-sidebar {
  background:rgba(255,255,255,.03);
  border:1px solid rgba(255,255,255,.07);
  border-radius:12px;
  padding:14px;
  display:flex; flex-direction:column;
  overflow:hidden;
}
.detection-sidebar-hdr {
  display:flex; align-items:center; justify-content:space-between;
  font-size:.78rem; font-weight:600; color:#94a3b8;
  margin-bottom:10px; text-transform:uppercase; letter-spacing:.06em;
}
.det-count-badge {
  background:rgba(108,99,255,.3); color:#a5b4fc;
  padding:2px 8px; border-radius:20px; font-size:.72rem; font-weight:700;
}
.detection-list { flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:6px; }
.det-loading { color:#475569; font-size:.8rem; text-align:center; margin-top:20px; }
.det-item {
  display:flex; align-items:center; justify-content:space-between;
  background:rgba(255,255,255,.04); border-radius:7px;
  padding:6px 10px; font-size:.8rem;
  border-left:3px solid var(--item-color, #6C63FF);
  animation: fadeIn .25s ease;
}
@keyframes fadeIn { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:none} }
.det-item-id { font-weight:700; color:#e2e8f0; }
.det-item-cls {
  font-size:.72rem; padding:2px 7px; border-radius:4px;
  font-weight:600; color:#0f172a;
  background:var(--item-color, #6C63FF);
}
.det-item-conf { font-size:.72rem; color:#64748b; }

/* ── Camera status list ──────────────────────────────────── */
.cam-status-list { display:flex; flex-direction:column; gap:4px; overflow-y:auto; max-height:180px; }
.cam-status-row {
  display:flex; align-items:center; gap:7px;
  font-size:.78rem; padding:3px 0;
}
.cam-status-dot {
  width:7px; height:7px; border-radius:50%; flex-shrink:0;
}
.cam-status-dot.online  { background:#22c55e; box-shadow:0 0 6px #22c55e; }
.cam-status-dot.offline { background:#475569; }
.cam-status-name { color:#cbd5e1; font-weight:600; min-width:36px; }
.cam-status-lbl  { color:#64748b; font-size:.72rem; margin-left:auto; }
</style>

<script src="js/app.js"></script>
<script>
// ── Live clock ─────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent = now.toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

// ── Stream camera switcher ──────────────────────────────────────
let currentCam = '<?= $first_active ?? 'c21' ?>';

function switchStream(cam, btn) {
  currentCam = cam;
  const img = document.getElementById('live-stream');
  const label = document.getElementById('stream-cam-label');
  // Force reload by adding timestamp
  img.src = `http://127.0.0.1:5000/api/stream/${cam}?w=860&h=480&t=${Date.now()}`;
  label.textContent = 'CAM ' + cam.toUpperCase();
  // Toggle active button
  document.querySelectorAll('.cam-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  // Reset detection panel
  document.getElementById('detection-list').innerHTML = '<div class="det-loading">Switching camera…</div>';
}

async function restartAllCameras(btn) {
  if (btn) btn.textContent = '↺ Rewinding…';
  try {
    await fetch('http://127.0.0.1:5000/api/sync/reset');
  } catch(e) {
    console.error('Reset error:', e);
  }
  const img = document.getElementById('live-stream');
  img.src = `http://127.0.0.1:5000/api/stream/${currentCam}?w=860&h=480&t=${Date.now()}`;
  if (btn) btn.textContent = '↺ Play from Start';
}

// Handle stream errors
document.getElementById('live-stream').addEventListener('error', function() {
  document.getElementById('stream-no-signal').style.display = 'flex';
  this.style.display = 'none';
});
document.getElementById('live-stream').addEventListener('load', function() {
  document.getElementById('stream-no-signal').style.display = 'none';
  this.style.display = 'block';
});

// ── Poll /api/camera_status for live vehicle counts ─────────────
const CLASS_COLORS = {
  car:        '#d97706',
  truck:      '#2563eb',
  bus:        '#16a34a',
  motorcycle: '#7c3aed',
  bicycle:    '#ea580c',
};

async function pollDetections() {
  try {
    const res  = await fetch('http://127.0.0.1:5000/api/camera_status');
    const data = await res.json();
    if (!data.success) return;

    // Find the active camera's live count
    const activeCam = data.cameras.find(c => c.id === currentCam);
    const count = activeCam ? (activeCam.live_count ?? 0) : 0;
    document.getElementById('det-count').textContent = count;

    // Build detection cards (we have count but not per-class breakdown from status;
    // show placeholder rows based on count)
    const list = document.getElementById('detection-list');
    if (count === 0) {
      list.innerHTML = '<div class="det-loading">No vehicles detected</div>';
    } else {
      // Generic vehicle rows since status only gives count
      let html = '';
      for (let i = 1; i <= Math.min(count, 12); i++) {
        const col = Object.values(CLASS_COLORS)[i % 5];
        html += `<div class="det-item" style="--item-color:${col}">
          <span class="det-item-id">ID: ${i}</span>
          <span class="det-item-cls">vehicle</span>
          <span class="det-item-conf">live</span>
        </div>`;
      }
      if (count > 12) html += `<div class="det-loading">+${count-12} more…</div>`;
      list.innerHTML = html;
    }
  } catch(e) {
    document.getElementById('detection-list').innerHTML =
      '<div class="det-loading">API unreachable</div>';
  }
}

setInterval(pollDetections, 1500);
pollDetections();

// Auto-refresh stats every 60 seconds
setTimeout(() => location.reload(), 60000);
</script>
</body>
</html>
