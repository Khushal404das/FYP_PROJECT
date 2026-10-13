<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Query Vehicle — FYP Vehicle Tracking System</title>
  <meta name="description" content="Search for a vehicle by image or text description across the multi-camera network." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="css/style.css" />
</head>
<body>

<?php
require_once 'config.php';

$results   = null;
$query_mode = $_POST['query_mode'] ?? '';
$error     = '';

// ── Handle form submit ──────────────────────────────────────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    if ($query_mode === 'image') {
        // IMAGE QUERY
        if (!isset($_FILES['vehicle_image']) || $_FILES['vehicle_image']['error'] !== UPLOAD_ERR_OK) {
            $error = 'Please select a valid image file.';
        } elseif ($_FILES['vehicle_image']['size'] > MAX_FILE_SIZE) {
            $error = 'File too large (max 50 MB).';
        } else {
            $tmp   = $_FILES['vehicle_image']['tmp_name'];
            $name  = basename($_FILES['vehicle_image']['name']);
            $dest  = UPLOAD_DIR . uniqid() . '_' . preg_replace('/[^a-zA-Z0-9._-]/', '_', $name);
            move_uploaded_file($tmp, $dest);

            $results = api_request('/query_image', 'POST',
                ['top_k' => intval($_POST['top_k'] ?? 5)],
                ['image' => $dest]
            );
        }

    } elseif ($query_mode === 'description') {
        // DESCRIPTION QUERY
        $desc = [
            'color'        => trim($_POST['color']        ?? ''),
            'vehicle_type' => trim($_POST['vehicle_type'] ?? ''),
            'plate_number' => strtoupper(trim($_POST['plate_number'] ?? '')),
            'camera_id'    => trim($_POST['camera_id']    ?? ''),
            'top_k'        => intval($_POST['top_k']      ?? 5),
        ];
        $results = api_request('/query_description', 'POST', $desc);
    }
}

$status = api_request('/status');
?>

<!-- SIDEBAR -->
<aside class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="logo-icon">
      <svg viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="18" stroke="url(#g1)" stroke-width="2"/><path d="M10 24L15 16L20 20L25 14L30 22" stroke="url(#g2)" stroke-width="2" stroke-linecap="round"/><defs><linearGradient id="g1" x1="2" y1="2" x2="38" y2="38"><stop stop-color="#6C63FF"/><stop offset="1" stop-color="#00D4FF"/></linearGradient><linearGradient id="g2" x1="10" y1="24" x2="30" y2="14"><stop stop-color="#FF6B9D"/><stop offset="1" stop-color="#FFD93D"/></linearGradient></defs></svg>
    </div>
    <div class="logo-text"><span class="logo-title">VehicleTrack</span><span class="logo-sub">FYP System</span></div>
  </div>
  <nav class="sidebar-nav">
    <a href="dashboard.php" class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>Dashboard</a>
    <a href="query.php"     class="nav-item active"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>Query Vehicle</a>
    <a href="cameras.php"   class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>Camera Network</a>
    <a href="tracks.php"    class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Track Journeys</a>
    <a href="process.php"   class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>Process Video</a>
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
      <h1 class="page-title">Query Vehicle</h1>
    </div>
    <div class="topbar-right"><div class="topbar-time" id="clock"></div></div>
  </header>

  <!-- QUERY MODE TABS -->
  <div class="query-tabs">
    <button class="query-tab <?= ($query_mode !== 'description') ? 'active' : '' ?>" onclick="switchTab('image')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5L5 21"/></svg>
      Search by Image
    </button>
    <button class="query-tab <?= ($query_mode === 'description') ? 'active' : '' ?>" onclick="switchTab('description')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
      Search by Description
    </button>
  </div>

  <!-- IMAGE QUERY FORM -->
  <section class="section-card query-panel" id="panel-image" style="<?= ($query_mode === 'description') ? 'display:none' : '' ?>">
    <div class="section-header">
      <h2>Upload Vehicle Image</h2>
      <span class="section-badge">ReID Matching</span>
    </div>

    <?php if ($error && $query_mode === 'image'): ?>
      <div class="alert alert-error"><?= htmlspecialchars($error) ?></div>
    <?php endif; ?>

    <form method="POST" enctype="multipart/form-data" class="query-form">
      <input type="hidden" name="query_mode" value="image" />

      <div class="upload-zone" id="drop-zone" onclick="document.getElementById('img-input').click()">
        <div class="upload-icon">
          <svg viewBox="0 0 64 64" fill="none"><circle cx="32" cy="32" r="30" stroke="url(#ug)" stroke-width="2" stroke-dasharray="4 4"/><path d="M32 20v16M24 28l8-8 8 8" stroke="url(#ug2)" stroke-width="2.5" stroke-linecap="round"/><rect x="20" y="40" width="24" height="4" rx="2" fill="url(#ug2)" opacity="0.5"/><defs><linearGradient id="ug" x1="2" y1="2" x2="62" y2="62"><stop stop-color="#6C63FF"/><stop offset="1" stop-color="#00D4FF"/></linearGradient><linearGradient id="ug2" x1="20" y1="20" x2="44" y2="44"><stop stop-color="#FF6B9D"/><stop offset="1" stop-color="#FFD93D"/></linearGradient></defs></svg>
        </div>
        <p class="upload-title">Drop vehicle image here</p>
        <p class="upload-sub">or click to browse · PNG, JPG, JPEG, BMP, WebP</p>
        <div class="upload-preview" id="img-preview"></div>
      </div>
      <input type="file" id="img-input" name="vehicle_image" accept="image/*" style="display:none" onchange="previewImage(this)" />

      <div class="form-row">
        <label for="top_k_img">Top K Results</label>
        <input type="number" id="top_k_img" name="top_k" value="5" min="1" max="20" class="form-input" />
      </div>

      <button type="submit" class="btn btn-primary btn-lg" id="img-submit">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        Search Vehicle
      </button>
    </form>
  </section>

  <!-- DESCRIPTION QUERY FORM -->
  <section class="section-card query-panel" id="panel-description" style="<?= ($query_mode !== 'description') ? 'display:none' : '' ?>">
    <div class="section-header">
      <h2>Describe the Vehicle</h2>
      <span class="section-badge">Metadata Search</span>
    </div>

    <?php if ($error && $query_mode === 'description'): ?>
      <div class="alert alert-error"><?= htmlspecialchars($error) ?></div>
    <?php endif; ?>

    <form method="POST" class="query-form">
      <input type="hidden" name="query_mode" value="description" />

      <div class="form-grid">
        <div class="form-group">
          <label for="color">Vehicle Color</label>
          <select id="color" name="color" class="form-input">
            <option value="">Any color</option>
            <?php foreach (['white','black','silver','grey','red','blue','green','yellow','orange','brown','maroon','beige'] as $c): ?>
              <option value="<?= $c ?>" <?= (($_POST['color'] ?? '') === $c) ? 'selected' : '' ?>><?= ucfirst($c) ?></option>
            <?php endforeach; ?>
          </select>
        </div>

        <div class="form-group">
          <label for="vehicle_type">Vehicle Type</label>
          <select id="vehicle_type" name="vehicle_type" class="form-input">
            <option value="">Any type</option>
            <?php foreach (['car','suv','truck','bus','motorcycle','van','pickup'] as $t): ?>
              <option value="<?= $t ?>" <?= (($_POST['vehicle_type'] ?? '') === $t) ? 'selected' : '' ?>><?= ucfirst($t) ?></option>
            <?php endforeach; ?>
          </select>
        </div>

        <div class="form-group">
          <label for="plate_number">License Plate</label>
          <input type="text" id="plate_number" name="plate_number"
                 value="<?= htmlspecialchars($_POST['plate_number'] ?? '') ?>"
                 placeholder="e.g. ABC-1234" class="form-input mono-input" />
        </div>

        <div class="form-group">
          <label for="camera_id">Last Known Camera</label>
          <select id="camera_id" name="camera_id" class="form-input">
            <option value="">Any camera</option>
            <?php foreach (json_decode(CAMERAS, true) as $cam): ?>
              <option value="<?= $cam ?>" <?= (($_POST['camera_id'] ?? '') === $cam) ? 'selected' : '' ?>><?= strtoupper($cam) ?></option>
            <?php endforeach; ?>
          </select>
        </div>

        <div class="form-group">
          <label for="top_k_desc">Top K Results</label>
          <input type="number" id="top_k_desc" name="top_k" value="<?= intval($_POST['top_k'] ?? 5) ?>" min="1" max="20" class="form-input" />
        </div>
      </div>

      <button type="submit" class="btn btn-primary btn-lg">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        Search Vehicle
      </button>
    </form>
  </section>

  <!-- RESULTS -->
  <?php if ($results !== null): ?>
  <section class="section-card results-section">
    <div class="section-header">
      <h2>Search Results</h2>
      <span class="section-badge"><?= count($results['matches'] ?? []) ?> Match(es)</span>
    </div>

    <?php if (!($results['success'] ?? false)): ?>
      <div class="alert alert-error">API Error: <?= htmlspecialchars($results['error'] ?? 'Unknown error') ?></div>
    <?php elseif (empty($results['matches'])): ?>
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <p>No matching vehicles found. Try processing more camera videos first.</p>
        <a href="process.php" class="btn btn-primary">Process Video</a>
      </div>
    <?php else: ?>
      <div class="result-cards">
        <?php foreach ($results['matches'] as $i => $match): ?>
        <div class="result-card <?= $i === 0 ? 'result-top' : '' ?>" onclick="window.location='tracks.php?gid=<?= $match['global_id'] ?>'">
          <div class="result-rank"><?= $i + 1 ?></div>
          <div class="result-body">
            <div class="result-header">
              <span class="gid-badge">#<?= $match['global_id'] ?></span>
              <?php
              $score = $match['similarity'] ?? $match['score'] ?? 0;
              $pct   = round($score * 100, 1);
              ?>
              <div class="similarity-bar">
                <div class="sim-fill" style="width:<?= min(100, $pct) ?>%"></div>
                <span class="sim-label"><?= $pct ?>% match</span>
              </div>
            </div>
            <div class="result-cameras">
              <?php foreach ($match['cameras'] as $c): ?>
                <?= cam_badge($c) ?>
              <?php endforeach; ?>
            </div>
            <div class="result-sightings">
              <strong><?= count($match['sightings'] ?? []) ?></strong> sightings &nbsp;|&nbsp;
              First: <code><?= fmt_time($match['first_seen'] ?? 0) ?></code> &nbsp;|&nbsp;
              Last:  <code><?= fmt_time($match['last_seen'] ?? 0) ?></code>
            </div>
          </div>
          <a href="tracks.php?gid=<?= $match['global_id'] ?>" class="btn btn-ghost" onclick="event.stopPropagation()">View Journey →</a>
        </div>
        <?php endforeach; ?>
      </div>
    <?php endif; ?>
  </section>
  <?php endif; ?>

</main>

<script src="js/app.js"></script>
<script>
function switchTab(mode) {
  document.querySelectorAll('.query-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.query-panel').forEach(p => p.style.display = 'none');
  event.currentTarget.classList.add('active');
  document.getElementById('panel-' + mode).style.display = '';
}

function previewImage(input) {
  const preview = document.getElementById('img-preview');
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = e => {
      preview.innerHTML = `<img src="${e.target.result}" alt="Preview" class="upload-img-preview" />`;
    };
    reader.readAsDataURL(input.files[0]);
  }
}

// Drag-and-drop
const dropZone = document.getElementById('drop-zone');
if (dropZone) {
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const fi = document.getElementById('img-input');
    fi.files = e.dataTransfer.files;
    previewImage(fi);
  });
}

function updateClock() { document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
setInterval(updateClock, 1000); updateClock();
</script>
</body>
</html>
