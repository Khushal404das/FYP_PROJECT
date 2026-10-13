<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Vehicle Journey — FYP Vehicle Tracking System</title>
  <meta name="description" content="View the complete cross-camera journey of a tracked vehicle." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="css/style.css" />
</head>
<body>

<?php
require_once 'config.php';

$gid     = intval($_GET['gid'] ?? 0);
$journey = null;
$summary = api_request('/summary');
$status  = api_request('/status');

if ($gid > 0) {
    $journey = api_request("/journey/{$gid}");
}
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
    <a href="tracks.php"   class="nav-item active"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Track Journeys</a>
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
      <h1 class="page-title">Track Journeys</h1>
    </div>
    <div class="topbar-right">
      <div class="topbar-time" id="clock"></div>
      <a href="query.php" class="btn btn-primary">Search Vehicle</a>
    </div>
  </header>

  <!-- VEHICLE SELECTOR -->
  <section class="section-card" style="padding: 1.5rem 2rem;">
    <form method="GET" class="inline-form">
      <label for="gid-select" style="font-weight:600;margin-right:.75rem;">Select Vehicle Global ID:</label>
      <select id="gid-select" name="gid" class="form-input" style="width:200px;display:inline-block" onchange="this.form.submit()">
        <option value="0">— choose vehicle —</option>
        <?php foreach ($summary['tracks'] ?? [] as $t): ?>
          <option value="<?= $t['global_id'] ?>" <?= ($gid === $t['global_id']) ? 'selected' : '' ?>>
            #<?= $t['global_id'] ?> (<?= implode(', ', array_map('strtoupper', $t['cameras'])) ?>)
          </option>
        <?php endforeach; ?>
      </select>
      <button type="submit" class="btn btn-ghost" style="margin-left:.5rem;">View Journey</button>
    </form>
  </section>

  <?php if ($gid > 0 && $journey !== null): ?>

    <?php if (!($journey['success'] ?? false)): ?>
      <div class="alert alert-error"><?= htmlspecialchars($journey['error'] ?? 'Not found') ?></div>
    <?php else: ?>

    <!-- JOURNEY HEADER -->
    <section class="section-card journey-hero">
      <div class="journey-hero-left">
        <div class="journey-id">Vehicle #<?= $journey['global_id'] ?></div>
        <div class="journey-cameras">
          <?php foreach ($journey['cameras'] as $c): echo cam_badge($c); endforeach; ?>
        </div>
        <div class="journey-meta">
          <span>🕐 First seen: <code><?= fmt_time($journey['first_seen'] ?? 0) ?></code></span>
          <span>🕑 Last seen: <code><?= fmt_time($journey['last_seen'] ?? 0) ?></code></span>
          <span>👁 Total sightings: <code><?= $journey['total_sightings'] ?></code></span>
        </div>
      </div>
      <div class="journey-hero-right">
        <div class="journey-route-count"><?= count($journey['cameras']) ?></div>
        <div style="font-size:.85rem;color:var(--text-muted)">Cameras traversed</div>
      </div>
    </section>

    <!-- TIMELINE -->
    <section class="section-card">
      <div class="section-header">
        <h2>Camera Journey Timeline</h2>
        <span class="section-badge"><?= count($journey['route'] ?? []) ?> steps</span>
      </div>
      <div class="journey-timeline">
        <?php foreach ($journey['route'] ?? [] as $i => $step): ?>
        <div class="timeline-step <?= $i === 0 ? 'first' : '' ?> <?= $i === count($journey['route']) - 1 ? 'last' : '' ?>">
          <div class="tl-connector">
            <div class="tl-dot"></div>
            <?php if ($i < count($journey['route']) - 1): ?>
            <div class="tl-line"></div>
            <?php endif; ?>
          </div>
          <div class="tl-card">
            <div class="tl-cam"><?= cam_badge($step['camera']) ?></div>
            <div class="tl-time">⏱ <?= fmt_time($step['timestamp'] ?? 0) ?></div>
            <?php if (!empty($step['bbox'])): ?>
            <div class="tl-bbox mono">
              BBox: [<?= implode(', ', array_map('intval', $step['bbox'])) ?>]
            </div>
            <?php endif; ?>
            <?php if (!empty($step['next_cameras'])): ?>
            <div class="tl-next">
              → Next: <?php foreach ($step['next_cameras'] as $nc): echo cam_badge($nc); endforeach; ?>
            </div>
            <?php endif; ?>
          </div>
        </div>
        <?php endforeach; ?>
      </div>
    </section>

    <!-- ALL SIGHTINGS TABLE -->
    <section class="section-card">
      <div class="section-header">
        <h2>All Sightings</h2>
      </div>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr><th>#</th><th>Camera</th><th>Timestamp</th><th>Bounding Box</th></tr>
          </thead>
          <tbody>
            <?php foreach ($journey['route'] ?? [] as $i => $step): ?>
            <tr>
              <td><?= $step['step'] ?></td>
              <td><?= cam_badge($step['camera']) ?></td>
              <td class="mono"><?= fmt_time($step['timestamp'] ?? 0) ?></td>
              <td class="mono"><?= !empty($step['bbox']) ? '[' . implode(', ', array_map('intval', $step['bbox'])) . ']' : '—' ?></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </section>

    <?php endif; ?>

  <?php elseif (!empty($summary['tracks'])): ?>

  <!-- ALL TRACKS TABLE (no vehicle selected) -->
  <section class="section-card">
    <div class="section-header">
      <h2>All Tracked Vehicles</h2>
      <span class="section-badge"><?= $summary['total'] ?? 0 ?> total</span>
    </div>
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr><th>ID</th><th>Cameras</th><th>Sightings</th><th>First Seen</th><th>Last Seen</th><th></th></tr>
        </thead>
        <tbody>
          <?php foreach ($summary['tracks'] as $t): ?>
          <tr class="table-row" onclick="window.location='tracks.php?gid=<?= $t['global_id'] ?>'">
            <td><span class="gid-badge">#<?= $t['global_id'] ?></span></td>
            <td><?php foreach ($t['cameras'] as $c): echo cam_badge($c); endforeach; ?></td>
            <td><?= $t['sightings'] ?></td>
            <td class="mono"><?= fmt_time($t['first_seen']) ?></td>
            <td class="mono"><?= fmt_time($t['last_seen']) ?></td>
            <td><a href="tracks.php?gid=<?= $t['global_id'] ?>" class="btn btn-ghost btn-sm" onclick="event.stopPropagation()">Journey →</a></td>
          </tr>
          <?php endforeach; ?>
        </tbody>
      </table>
    </div>
  </section>

  <?php else: ?>
  <div class="empty-state">
    <div class="empty-icon">🚗</div>
    <p>No tracked vehicles yet. Process a camera video to start tracking.</p>
    <a href="process.php" class="btn btn-primary">Process Video</a>
  </div>
  <?php endif; ?>

</main>

<script src="js/app.js"></script>
<script>
function updateClock(){ document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
setInterval(updateClock,1000); updateClock();
</script>
</body>
</html>
