<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Camera Network — FYP Vehicle Tracking System</title>
  <meta name="description" content="View all cameras in the surveillance network and their topology connections."/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="css/style.css"/>
</head>
<body>
<?php
require_once 'config.php';
$status      = api_request('/status');
$cameras_api = api_request('/cameras');
$sel_cam     = $_GET['cam'] ?? '';
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
    <a href="cameras.php"  class="nav-item active"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>Camera Network</a>
    <a href="tracks.php"   class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Track Journeys</a>
    <a href="process.php"  class="nav-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>Process Video</a>
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
      <h1 class="page-title">Camera Network</h1>
    </div>
    <div class="topbar-right"><div class="topbar-time" id="clock"></div></div>
  </header>

  <!-- CAMERA GRID -->
  <section class="section-card">
    <div class="section-header">
      <h2>All Cameras</h2>
      <span class="section-badge"><?= count($cameras_api['cameras'] ?? []) ?> cameras</span>
    </div>
    <div class="cam-grid">
      <?php foreach ($cameras_api['cameras'] ?? [] as $cam): ?>
      <a href="cameras.php?cam=<?= $cam['id'] ?>" class="cam-card <?= ($sel_cam === $cam['id']) ? 'cam-selected' : '' ?> <?= $cam['has_video'] ? 'has-video' : 'no-video' ?>">
        <div class="cam-card-icon">
          <svg viewBox="0 0 48 48" fill="none">
            <rect x="2" y="10" width="32" height="22" rx="4" stroke="currentColor" stroke-width="2"/>
            <path d="M34 17l10 7-10 7V17z" stroke="currentColor" stroke-width="2"/>
            <?php if ($cam['has_video']): ?>
            <circle cx="18" cy="21" r="5" fill="rgba(0,212,255,.25)" stroke="#00D4FF" stroke-width="1.5"/>
            <circle cx="18" cy="21" r="2" fill="#00D4FF"/>
            <?php else: ?>
            <line x1="2" y1="10" x2="46" y2="38" stroke="rgba(255,100,100,.6)" stroke-width="2"/>
            <?php endif; ?>
          </svg>
        </div>
        <div class="cam-card-id"><?= strtoupper($cam['id']) ?></div>
        <div class="cam-card-status"><?= $cam['has_video'] ? '● Active' : '○ No video' ?></div>
        <?php if (!empty($cam['next_cameras'])): ?>
        <div class="cam-card-links">
          → <?= implode(', ', array_map('strtoupper', $cam['next_cameras'])) ?>
        </div>
        <?php endif; ?>
      </a>
      <?php endforeach; ?>
    </div>
  </section>

  <!-- SELECTED CAMERA DETAIL -->
  <?php if ($sel_cam): ?>
  <?php
    $cam_info = null;
    foreach ($cameras_api['cameras'] ?? [] as $c) {
      if ($c['id'] === $sel_cam) { $cam_info = $c; break; }
    }
    $topology = $cameras_api['topology'] ?? [];
  ?>
  <section class="section-card">
    <div class="section-header">
      <h2>Camera <?= strtoupper($sel_cam) ?> Details</h2>
      <?php if ($cam_info['has_video'] ?? false): ?>
        <span class="section-badge badge-live">LIVE</span>
      <?php endif; ?>
    </div>

    <div class="cam-detail-grid">
      <div class="cam-detail-info">
        <div class="detail-row"><span>Camera ID</span><code><?= strtoupper($sel_cam) ?></code></div>
        <div class="detail-row"><span>Video Available</span><code><?= ($cam_info['has_video'] ?? false) ? 'Yes' : 'No' ?></code></div>
        <div class="detail-row">
          <span>Next Cameras</span>
          <div><?php foreach ($cam_info['next_cameras'] ?? [] as $nc): echo cam_badge($nc); endforeach; ?></div>
        </div>
      </div>

      <div class="cam-detail-actions">
        <?php if ($cam_info['has_video'] ?? false): ?>
        <form method="POST" action="process.php">
          <input type="hidden" name="camera_id" value="<?= $sel_cam ?>" />
          <input type="hidden" name="max_frames" value="200" />
          <input type="hidden" name="process_now" value="1" />
          <button type="submit" class="btn btn-primary btn-lg">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Process This Camera
          </button>
        </form>
        <?php else: ?>
        <a href="process.php" class="btn btn-ghost">Upload Video for <?= strtoupper($sel_cam) ?></a>
        <?php endif; ?>
      </div>
    </div>

    <!-- Topology chain -->
    <div class="topo-chain">
      <h3>Route from <?= strtoupper($sel_cam) ?></h3>
      <div class="topo-chain-row">
        <?php
        function build_chain(string $cam, array $topo, int $depth = 0): void {
          if ($depth > 6) { echo '<span style="color:var(--text-muted)">...</span>'; return; }
          echo cam_badge($cam);
          $next = $topo[$cam] ?? [];
          if (!empty($next)) {
            echo '<span class="chain-arrow">→</span>';
            foreach ($next as $i => $n) {
              if ($i > 0) echo '<span style="color:var(--text-muted)"> / </span>';
              build_chain($n, $topo, $depth + 1);
            }
          }
        }
        build_chain($sel_cam, $topology);
        ?>
      </div>
    </div>
  </section>
  <?php endif; ?>

  <!-- TOPOLOGY TABLE -->
  <section class="section-card">
    <div class="section-header"><h2>Network Transition Table</h2></div>
    <div class="table-wrapper">
      <table class="data-table">
        <thead><tr><th>Camera</th><th>Connected To</th><th>Video Status</th></tr></thead>
        <tbody>
          <?php foreach ($cameras_api['cameras'] ?? [] as $cam): ?>
          <tr class="table-row <?= ($sel_cam === $cam['id']) ? 'row-selected' : '' ?>" onclick="window.location='cameras.php?cam=<?= $cam['id'] ?>'">
            <td><?= cam_badge($cam['id']) ?></td>
            <td><?php foreach ($cam['next_cameras'] as $nc): echo cam_badge($nc); endforeach; ?></td>
            <td><?= $cam['has_video'] ? '<span class="badge-live">● Has Video</span>' : '<span style="color:var(--text-muted)">No video</span>' ?></td>
          </tr>
          <?php endforeach; ?>
        </tbody>
      </table>
    </div>
  </section>
</main>

<script src="js/app.js"></script>
<script>
function updateClock(){ document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
setInterval(updateClock,1000); updateClock();
</script>
</body>
</html>
