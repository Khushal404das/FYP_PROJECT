<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Live Streaming — FYP Vehicle Tracking System</title>
  <meta name="description" content="Live multi-camera CCTV streaming with cross-camera vehicle tracking and auto-switching."/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="css/style.css"/>
  <link rel="stylesheet" href="css/stream.css"/>
</head>
<body class="stream-body">

<?php require_once 'config.php'; ?>

<!-- ░░ TOP HEADER BAR ░░ -->
<header class="stream-topbar">
  <div class="stream-topbar-left">
    <div class="stream-logo">
      <svg viewBox="0 0 32 32" fill="none" width="28" height="28">
        <circle cx="16" cy="16" r="14" stroke="url(#sg1)" stroke-width="1.5"/>
        <path d="M8 20L12 13L16 17L20 11L24 18" stroke="url(#sg2)" stroke-width="1.8" stroke-linecap="round"/>
        <defs>
          <linearGradient id="sg1" x1="2" y1="2" x2="30" y2="30"><stop stop-color="#6C63FF"/><stop offset="1" stop-color="#00D4FF"/></linearGradient>
          <linearGradient id="sg2" x1="8" y1="20" x2="24" y2="11"><stop stop-color="#FF6B9D"/><stop offset="1" stop-color="#FFD93D"/></linearGradient>
        </defs>
      </svg>
      <span>AI VISION-MIXER</span>
    </div>
    <nav class="stream-nav">
      <a href="dashboard.php">Dashboard</a>
      <a href="query.php">Query</a>
      <a href="stream.php" class="active">Live Stream</a>
      <a href="tracks.php">Tracks</a>
      <a href="process.php">Process</a>
    </nav>
  </div>
  <div class="stream-topbar-right">
    <div class="stream-clock" id="stream-clock"></div>
    <div class="api-dot" id="api-dot" title="API Status"></div>
    <button class="stream-btn" id="btn-fullscreen" onclick="toggleFullscreen()" title="Fullscreen">⛶</button>
  </div>
</header>

<!-- ░░ MAIN LAYOUT ░░ -->
<div class="stream-layout">

  <!-- ░░ LEFT — MAIN VIDEO FEED ░░ -->
  <div class="main-feed-col">

    <!-- Main video (active camera MJPEG stream) -->
    <div class="main-video-wrap" id="main-video-wrap">
      <img id="main-feed"
           src="http://127.0.0.1:5000/api/stream/active?w=960&h=540&fps=25"
           alt="Main Camera Feed"
           class="main-video-img"
           onerror="handleStreamError(this)" />

      <!-- Overlay: top info bar -->
      <div class="mv-top-bar">
        <div class="mv-cam-label" id="mv-cam-label">CAMERA A5 (PERIMETER C)</div>
        <div class="mv-mode-badge" id="mv-mode-badge">
          <span class="live-dot"></span> LIVE
        </div>
      </div>

      <!-- Overlay: bottom info bar -->
      <div class="mv-bottom-bar">
        <div class="mv-cam-info">
          <span id="mv-cam-id">CAM C11</span>
          <span id="mv-zone-label">ZONE 1</span>
        </div>
        <div class="mv-follow-label" id="mv-follow-label"></div>
        <div class="mv-timestamp" id="mv-timestamp"></div>
      </div>

      <!-- No-signal overlay (shown when stream fails) -->
      <div class="no-signal-overlay" id="no-signal" style="display:none">
        <div>📡</div>
        <div>No Signal</div>
        <div style="font-size:.75rem;margin-top:.25rem;opacity:.6">Start the Python API server</div>
      </div>
    </div>

    <!-- Camera switch buttons (quick access row) -->
    <div class="cam-quick-row" id="cam-quick-row">
      <?php
      $cams = json_decode(CAMERAS, true);
      foreach ($cams as $cam):
      ?>
      <button class="cam-quick-btn" id="qbtn-<?= $cam ?>"
              onclick="switchMainCamera('<?= $cam ?>')"
              title="Switch to <?= strtoupper($cam) ?>">
        <?= strtoupper($cam) ?>
      </button>
      <?php endforeach; ?>
    </div>

  </div><!-- /main-feed-col -->

  <!-- ░░ RIGHT PANEL ░░ -->
  <div class="right-panel">

    <!-- ── Camera Grid ── -->
    <div class="cam-grid-panel" id="cam-grid-panel">
      <?php
      $all_cams = json_decode(CAMERAS, true);
      foreach ($all_cams as $i => $cam):
      ?>
      <div class="cam-thumb-card" id="card-<?= $cam ?>"
           onclick="switchMainCamera('<?= $cam ?>')"
           title="Switch to <?= strtoupper($cam) ?>">
        <img class="cam-thumb-img"
             id="thumb-<?= $cam ?>"
             src="http://127.0.0.1:5000/api/stream/thumb/<?= $cam ?>?fps=8"
             alt="<?= strtoupper($cam) ?>"
             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22213%22 height=%22120%22><rect fill=%22%230a0c14%22 width=%22213%22 height=%22120%22/><text x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 fill=%22%23444%22 font-size=%2214%22>NO SIGNAL</text></svg>'" />
        <!-- Thumb overlay -->
        <div class="thumb-overlay">
          <div class="thumb-cam-id"><?= strtoupper($cam) ?></div>
          <div class="thumb-zone-tag">Zone <?php echo ['c11'=>1,'c12'=>1,'c21'=>2,'c22'=>2,'c23'=>2,'c24'=>2,'c31'=>3,'c32'=>3,'c41'=>4,'c42'=>4,'c43'=>4,'c51'=>5,'c52'=>5,'c61'=>6,'c62'=>6,'c63'=>6,'c64'=>6,'c65'=>6][$cam] ?? '?'; ?></div>
          <div class="thumb-status-badge" id="badge-<?= $cam ?>">0.00</div>
        </div>
        <!-- Live indicator for selected camera -->
        <div class="thumb-live-badge" id="live-<?= $cam ?>" style="display:none">LIVE</div>
        <!-- Vehicle count pill -->
        <div class="thumb-veh-pill" id="vehpill-<?= $cam ?>" style="display:none"></div>
      </div>
      <?php endforeach; ?>
    </div><!-- /cam-grid-panel -->

    <!-- ── Cross-Camera Vehicle Roster (ReID) ── -->
    <div class="roster-panel">
      <div class="roster-header">
        <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
          <path d="M2 13l3-6 3 4 3-6 3 5" stroke="#00D4FF" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        CROSS-CAMERA VEHICLE ROSTER (ReID)
        <span class="roster-count" id="roster-count">0 Active</span>
      </div>
      <div class="roster-list" id="roster-list">
        <div class="roster-empty">No vehicles tracked. Process a video first.</div>
      </div>
    </div><!-- /roster-panel -->

    <!-- ── AI Vision-Mixer Log ── -->
    <div class="log-panel">
      <div class="log-header">
        <span>> AI VISION-MIXER LOG</span>
        <button class="log-clear-btn" onclick="clearLog()">CLEAR</button>
      </div>
      <div class="log-list" id="log-list">
        <div class="log-entry">System initialised. Waiting for stream data...</div>
      </div>
    </div>

  </div><!-- /right-panel -->
</div><!-- /stream-layout -->

<script src="js/app.js"></script>
<script src="js/stream.js"></script>
</body>
</html>
