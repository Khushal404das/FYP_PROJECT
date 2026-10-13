<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Process Video — FYP Vehicle Tracking System</title>
  <meta name="description" content="Process camera video files to extract and track vehicles across the camera network."/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="css/style.css"/>
</head>
<body>
<?php
require_once 'config.php';

$result  = null;
$error   = '';
$status  = api_request('/status');
$cameras_api = api_request('/cameras');

// From cameras.php quick-process
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['process_now'])) {
    $_POST['action'] = 'dataset';
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? 'dataset';

    if ($action === 'dataset') {
        $camera_id  = trim($_POST['camera_id'] ?? '');
        $max_frames = intval($_POST['max_frames'] ?? 200);
        $sample     = intval($_POST['sample_every'] ?? 5);

        if (empty($camera_id)) {
            $error = 'Please select a camera.';
        } else {
            $result = api_request('/process_video', 'POST', [
                'camera_id'   => $camera_id,
                'max_frames'  => $max_frames,
                'sample_every' => $sample,
            ]);
        }
    } elseif ($action === 'upload') {
        $camera_id = trim($_POST['upload_camera_id'] ?? '');
        if (!isset($_FILES['video_file']) || $_FILES['video_file']['error'] !== UPLOAD_ERR_OK) {
            $error = 'Please select a valid video file.';
        } else {
            $tmp  = $_FILES['video_file']['tmp_name'];
            $name = basename($_FILES['video_file']['name']);
            $dest = UPLOAD_DIR . uniqid() . '_' . preg_replace('/[^a-zA-Z0-9._-]/', '_', $name);
            move_uploaded_file($tmp, $dest);

            $result = api_request('/process_upload_video', 'POST',
                ['camera_id'   => $camera_id,
                 'max_frames'  => intval($_POST['up_max_frames'] ?? 200),
                 'sample_every' => intval($_POST['up_sample'] ?? 5)],
                ['video' => $dest]
            );
        }
    } elseif ($action === 'reset') {
        $result = api_request('/reset', 'POST');
    }
}

$cams_list = $cameras_api['cameras'] ?? [];
?>

<!-- SIDEBAR -->
<aside class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="logo-icon"><svg viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="18" stroke="url(#g1)" stroke-width="2"/><path d="M10 24L15 16L20 20L25 14L30 22" stroke="url(#g2)" stroke-width="2" stroke-linecap="round"/><defs><linearGradient id="g1" x1="2" y1="2" x2="38" y2="38"><stop stop-color="#6C63FF"/><stop offset="1" stop-color="#00D4FF"/></linearGradient><linearGradient id="g2" x1="10" y1="24" x2="30" y2="14"><stop stop-color="#FF6B9D"/><stop offset="1" stop-color="#FFD93D"/></linearGradient></defs></svg></div>
    <div class="logo-text"><span class="logo-title">VehicleTrack</span><span class="logo-sub">FYP System</span></div>
  </div>
  <nav class="sidebar-nav">
    <a href="dashboard.php" class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>Dashboard</a>
    <a href="query.php"    class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>Query Vehicle</a>
    <a href="cameras.php"  class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>Camera Network</a>
    <a href="tracks.php"   class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Track Journeys</a>
    <a href="process.php"  class="nav-item active"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>Process Video</a>
  </nav>
  <div class="sidebar-status">
    <div class="status-dot <?= ($status['success'] ?? false) ? 'online' : 'offline' ?>"></div>
    <span><?= ($status['success'] ?? false) ? 'API Online' : 'API Offline' ?></span>
  </div>
</aside>

<!-- MAIN -->
<main class="main-content">
  <header class="topbar">
    <div class="topbar-left">
      <button class="sidebar-toggle" onclick="document.getElementById('sidebar').classList.toggle('collapsed')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button>
      <h1 class="page-title">Process Video</h1>
    </div>
    <div class="topbar-right"><div class="topbar-time" id="clock"></div></div>
  </header>

  <?php if (!empty($error)): ?>
  <div class="alert alert-error"><?= htmlspecialchars($error) ?></div>
  <?php endif; ?>

  <!-- RESULT BANNER -->
  <?php if ($result !== null): ?>
  <div class="alert <?= ($result['success'] ?? false) ? 'alert-success' : 'alert-error' ?>">
    <?php if ($result['success'] ?? false): ?>
      ✅ <strong>Processing complete!</strong>
      Camera <strong><?= htmlspecialchars($result['camera_id'] ?? '') ?></strong> —
      Processed <strong><?= $result['frames_processed'] ?? 0 ?></strong> frames.
      Total global tracks: <strong><?= $result['global_tracks'] ?? 0 ?></strong>.
      <a href="tracks.php" style="margin-left:1rem;" class="btn btn-ghost btn-sm">View Tracks →</a>
    <?php else: ?>
      ❌ <?= htmlspecialchars($result['error'] ?? 'Unknown error') ?>
    <?php endif; ?>
  </div>
  <?php endif; ?>

  <!-- PROCESS FROM DATASET -->
  <section class="section-card">
    <div class="section-header">
      <h2>Process Dataset Camera</h2>
      <span class="section-badge">Auto-Detect</span>
    </div>
    <form method="POST" id="form-dataset" onsubmit="showProcessing()">
      <input type="hidden" name="action" value="dataset" />
      <div class="form-grid">
        <div class="form-group">
          <label for="camera_id">Select Camera</label>
          <select name="camera_id" id="camera_id" class="form-input" required>
            <option value="">— select camera —</option>
            <?php foreach ($cams_list as $cam): ?>
            <option value="<?= $cam['id'] ?>"
              <?= (($_POST['camera_id'] ?? '') === $cam['id']) ? 'selected' : '' ?>
              <?= !$cam['has_video'] ? 'style="color:var(--text-muted)"' : '' ?>>
              <?= strtoupper($cam['id']) ?> <?= $cam['has_video'] ? '(video available)' : '(no video)' ?>
            </option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="form-group">
          <label for="max_frames">Max Frames</label>
          <input type="number" id="max_frames" name="max_frames" value="<?= intval($_POST['max_frames'] ?? 200) ?>" min="10" max="5000" class="form-input" />
        </div>
        <div class="form-group">
          <label for="sample_every">Sample Every N Frames</label>
          <input type="number" id="sample_every" name="sample_every" value="<?= intval($_POST['sample_every'] ?? 5) ?>" min="1" max="30" class="form-input" />
        </div>
      </div>
      <button type="submit" class="btn btn-primary btn-lg" id="btn-process">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        Start Processing
      </button>
    </form>

    <!-- Processing spinner -->
    <div id="processing-indicator" style="display:none;margin-top:1.5rem;">
      <div class="processing-box">
        <div class="spinner"></div>
        <div>
          <strong>Processing video...</strong><br/>
          <span style="color:var(--text-muted);font-size:.875rem">This may take a minute. Please wait.</span>
        </div>
      </div>
    </div>
  </section>

  <!-- UPLOAD CUSTOM VIDEO -->
  <section class="section-card">
    <div class="section-header">
      <h2>Upload Custom Video</h2>
      <span class="section-badge">Custom Feed</span>
    </div>
    <form method="POST" enctype="multipart/form-data">
      <input type="hidden" name="action" value="upload" />
      <div class="form-grid">
        <div class="form-group">
          <label for="upload_camera_id">Assign to Camera</label>
          <select name="upload_camera_id" id="upload_camera_id" class="form-input">
            <?php foreach ($cams_list as $cam): ?>
            <option value="<?= $cam['id'] ?>"><?= strtoupper($cam['id']) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="form-group">
          <label for="video_file">Video File (MP4, AVI, MOV)</label>
          <input type="file" id="video_file" name="video_file" accept="video/*" class="form-input" />
        </div>
        <div class="form-group">
          <label for="up_max_frames">Max Frames</label>
          <input type="number" id="up_max_frames" name="up_max_frames" value="200" min="10" max="5000" class="form-input" />
        </div>
        <div class="form-group">
          <label for="up_sample">Sample Every N Frames</label>
          <input type="number" id="up_sample" name="up_sample" value="5" min="1" max="30" class="form-input" />
        </div>
      </div>
      <button type="submit" class="btn btn-secondary btn-lg">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        Upload & Process
      </button>
    </form>
  </section>

  <!-- DANGER ZONE -->
  <section class="section-card danger-zone">
    <div class="section-header">
      <h2>⚠️ Danger Zone</h2>
    </div>
    <p>This will clear ALL tracked vehicle data. This action cannot be undone.</p>
    <form method="POST" onsubmit="return confirm('Are you sure? All tracking data will be permanently deleted.')">
      <input type="hidden" name="action" value="reset" />
      <button type="submit" class="btn btn-danger">Reset All Tracking Data</button>
    </form>
  </section>

</main>

<script src="js/app.js"></script>
<script>
function showProcessing() {
  document.getElementById('btn-process').disabled = true;
  document.getElementById('btn-process').textContent = 'Processing…';
  document.getElementById('processing-indicator').style.display = 'flex';
}
function updateClock(){ document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
setInterval(updateClock,1000); updateClock();
</script>
</body>
</html>
