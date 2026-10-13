/**
 * stream.js — Live Streaming Dashboard Logic
 * ===========================================
 * Handles:
 *  - Live clock for stream page
 *  - Camera switching (manual click + auto-follow)
 *  - Roster polling (every 3 s) + rendering
 *  - Activity log polling (every 2 s)
 *  - Camera status polling (every 4 s) — live indicator, vehicle count pill
 *  - API health dot
 *  - Stream error / reconnect handling
 *  - Fullscreen toggle
 */

'use strict';

const API = 'http://127.0.0.1:5000/api';

/* ── State ─────────────────────────────────────────────────────────────── */
let activeCam      = 'c11';
let followedGid    = null;
let streamErrorCnt = 0;
let knownLogLen    = 0;
let rosterCache    = [];

// Zones map
const ZONES = {
  c11:1,c12:1, c21:2,c22:2,c23:2,c24:2,
  c31:3,c32:3, c41:4,c42:4,c43:4,
  c51:5,c52:5, c61:6,c62:6,c63:6,c64:6,c65:6,
};

/* ── Init ──────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  startClock();
  pollApiStatus();
  pollCameraStatus();
  pollRoster();
  pollLog();
  setInterval(pollApiStatus,    8000);
  setInterval(pollCameraStatus, 4000);
  setInterval(pollRoster,       3000);
  setInterval(pollLog,          2000);
  updateTimestamp();
  setInterval(updateTimestamp, 1000);
  logLocal('Stream dashboard loaded.', 'new');
});

/* ── Live Clock ──────────────────────────────────────────────────────────*/
function startClock() {
  const el = document.getElementById('stream-clock');
  if (!el) return;
  function tick() {
    const now = new Date();
    el.textContent = now.toLocaleDateString('en-US', {
      month:'2-digit', day:'2-digit', year:'numeric'
    }) + '  ' + now.toLocaleTimeString();
  }
  tick(); setInterval(tick, 1000);
}

function updateTimestamp() {
  const el = document.getElementById('mv-timestamp');
  if (el) {
    el.textContent = new Date().toLocaleString('en-US',{
      month:'2-digit', day:'2-digit', year:'numeric',
      hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false
    });
  }
}

/* ── API Status ─────────────────────────────────────────────────────────*/
async function pollApiStatus() {
  const dot = document.getElementById('api-dot');
  if (!dot) return;
  try {
    const r = await fetch(API + '/status', { signal: AbortSignal.timeout(3000) });
    const d = await r.json();
    if (d.success) {
      dot.className = 'api-dot online';
      dot.title     = `API Online — ${d.tracked_vehicles} vehicles tracked`;
    } else {
      dot.className = 'api-dot offline';
    }
  } catch {
    dot.className = 'api-dot offline';
    dot.title     = 'API Offline';
  }
}

/* ── Camera Switching ───────────────────────────────────────────────────*/
function switchMainCamera(camId) {
  if (camId === activeCam) return;

  activeCam   = camId;
  followedGid = null;

  // Update main MJPEG src
  const feed = document.getElementById('main-feed');
  if (feed) {
    feed.src = `${API}/stream/${camId}?w=960&h=540&fps=25&t=${Date.now()}`;
  }

  // Update overlays
  updateMainOverlay(camId);

  // Quick buttons
  document.querySelectorAll('.cam-quick-btn').forEach(btn => btn.classList.remove('active-cam'));
  const qb = document.getElementById(`qbtn-${camId}`);
  if (qb) qb.classList.add('active-cam');

  // Thumb grid selected
  document.querySelectorAll('.cam-thumb-card').forEach(c => c.classList.remove('selected'));
  const card = document.getElementById(`card-${camId}`);
  if (card) card.classList.add('selected');

  // Show/hide LIVE badge on thumbs
  document.querySelectorAll('.thumb-live-badge').forEach(b => b.style.display = 'none');
  const lb = document.getElementById(`live-${camId}`);
  if (lb) lb.style.display = 'block';

  // Tell API to set active camera (optional server-side state)
  fetch(API + '/set_active_camera', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ camera_id: camId }),
  }).catch(() => {});

  logLocal(`Switched to camera ${camId.toUpperCase()}`, 'switch');
  updateFollowLabel(null);
}

function updateMainOverlay(camId) {
  const zone   = ZONES[camId] || '?';
  const el_cam = document.getElementById('mv-cam-id');
  const el_zon = document.getElementById('mv-zone-label');
  const el_lbl = document.getElementById('mv-cam-label');

  if (el_cam) el_cam.textContent = `CAM ${camId.toUpperCase()}`;
  if (el_zon) el_zon.textContent = `ZONE ${zone}`;
  if (el_lbl) el_lbl.textContent = `CAMERA ${camId.toUpperCase()} (ZONE ${zone} PERIMETER)`;
}

function updateFollowLabel(gid) {
  followedGid = gid;
  const el = document.getElementById('mv-follow-label');
  if (!el) return;
  if (gid !== null) {
    el.textContent = `FOLLOWING  VH-${String(gid).padStart(3,'0')}`;
    el.style.display = 'block';
  } else {
    el.textContent = '';
    el.style.display = 'none';
  }
}

/* ── Follow a vehicle (auto-switch) ────────────────────────────────────*/
async function followVehicle(gid, preferredCam) {
  try {
    const r = await fetch(`${API}/follow/${gid}`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ camera_id: preferredCam || '' }),
    });
    const d = await r.json();
    if (d.success) {
      const newCam = d.camera;
      switchMainCamera(newCam);
      updateFollowLabel(gid);
      logLocal(`Now following VH-${String(gid).padStart(3,'0')} on ${newCam.toUpperCase()}`, 'detect');

      // Update active stream to server-side "active" (follows the vehicle)
      const feed = document.getElementById('main-feed');
      if (feed) {
        feed.src = `${API}/stream/active?w=960&h=540&fps=25&t=${Date.now()}`;
      }
    }
  } catch (e) {
    logLocal(`Error following VH-${gid}: ${e.message}`, 'warn');
  }
}

/* ── Camera Status Polling ──────────────────────────────────────────────*/
async function pollCameraStatus() {
  try {
    const r = await fetch(API + '/camera_status', { signal: AbortSignal.timeout(4000) });
    const d = await r.json();
    if (!d.success) return;

    const serverActive = d.active_camera;
    const serverGid    = d.followed_gid;

    // Auto-switch if server says camera changed (vehicle followed on server)
    if (serverActive && serverActive !== activeCam && serverGid !== null) {
      const feed = document.getElementById('main-feed');
      if (feed) {
        feed.src = `${API}/stream/active?w=960&h=540&fps=25&t=${Date.now()}`;
      }
      // Update overlays without changing our local activeCam (stream is "active")
      updateMainOverlay(serverActive);
      updateFollowLabel(serverGid);

      document.querySelectorAll('.cam-quick-btn').forEach(b => b.classList.remove('active-cam'));
      document.querySelectorAll('.cam-thumb-card').forEach(c => c.classList.remove('selected'));
      document.querySelectorAll('.thumb-live-badge').forEach(b => b.style.display='none');
      const qb = document.getElementById(`qbtn-${serverActive}`);
      if (qb) qb.classList.add('active-cam');
      const card = document.getElementById(`card-${serverActive}`);
      if (card) card.classList.add('selected');
      const lb = document.getElementById(`live-${serverActive}`);
      if (lb) lb.style.display = 'block';
      activeCam = serverActive;
    }

    // Update vehicle count pills on thumb cards
    d.cameras.forEach(cam => {
      const card = document.getElementById(`card-${cam.id}`);
      const pill = document.getElementById(`vehpill-${cam.id}`);
      if (!card || !pill) return;

      const cnt = cam.vehicles ? cam.vehicles.length : 0;
      if (cnt > 0) {
        card.classList.add('has-vehicle');
        pill.textContent = `VH:${cnt}`;
        pill.style.display = 'block';
      } else {
        card.classList.remove('has-vehicle');
        pill.style.display = 'none';
      }
    });

  } catch { /* ignore */ }
}

/* ── Roster Polling ─────────────────────────────────────────────────────*/
async function pollRoster() {
  try {
    const r = await fetch(API + '/roster', { signal: AbortSignal.timeout(4000) });
    const d = await r.json();
    if (!d.success) return;

    renderRoster(d.roster || []);
  } catch { /* ignore */ }
}

function renderRoster(roster) {
  const list  = document.getElementById('roster-list');
  const count = document.getElementById('roster-count');
  if (!list) return;

  if (roster.length === 0) {
    list.innerHTML = '<div class="roster-empty">No vehicles tracked. Process a video first.</div>';
    if (count) count.textContent = '0 Active';
    return;
  }

  if (count) count.textContent = `${roster.length} Active`;

  // Type → badge class
  const typeCls = t => {
    const m = {'car':'ri-type-car','truck':'ri-type-truck','suv':'ri-type-suv',
               'bus':'ri-type-bus','van':'ri-type-van','motorcycle':'ri-type-motorcycle',
               'pickup':'ri-type-truck'};
    return m[t] || 'ri-type-car';
  };

  list.innerHTML = roster.map(vh => `
    <div class="roster-item ${followedGid === vh.global_id ? 'following' : ''}"
         id="ri-${vh.global_id}">
      <span class="ri-id">${vh.label}</span>
      <span class="ri-type-badge ${typeCls(vh.vehicle_type)}">${vh.vehicle_type.toUpperCase()}</span>
      <span class="ri-plate">${vh.plate || '—'}</span>
      <span class="ri-cam">${(vh.last_camera||'—').toUpperCase()}</span>
      <button class="ri-follow-btn"
              onclick="followVehicle(${vh.global_id},'${vh.last_camera||''}');event.stopPropagation()">
        FOLLOW
      </button>
      <button class="ri-compile-btn"
              onclick="window.open('tracks.php?gid=${vh.global_id}','_blank');event.stopPropagation()">
        COMPILE
      </button>
    </div>
  `).join('');
}

/* ── Activity Log Polling ───────────────────────────────────────────────*/
async function pollLog() {
  try {
    const r = await fetch(API + '/log', { signal: AbortSignal.timeout(3000) });
    const d = await r.json();
    if (!d.success) return;

    const entries = d.log || [];
    if (entries.length === knownLogLen) return;
    knownLogLen = entries.length;

    renderLog(entries);
  } catch { /* ignore */ }
}

function renderLog(entries) {
  const list = document.getElementById('log-list');
  if (!list) return;

  const cls = msg => {
    if (msg.includes('switch') || msg.includes('Switch')) return 'switch';
    if (msg.includes('VH-') || msg.includes('vehicle'))   return 'detect';
    if (msg.includes('warn') || msg.includes('Error'))     return 'warn';
    return 'new';
  };

  list.innerHTML = entries.slice(0, 20).map((e, i) =>
    `<div class="log-entry ${i === 0 ? cls(e) : ''}">${escapeHtml(e)}</div>`
  ).join('');
}

function logLocal(msg, type = 'new') {
  const list = document.getElementById('log-list');
  if (!list) return;
  const ts  = new Date().toLocaleTimeString('en-US', {hour12:false});
  const div = document.createElement('div');
  div.className = `log-entry ${type}`;
  div.textContent = `[${ts}] ${msg}`;
  list.insertBefore(div, list.firstChild);
  // Trim to 30 entries
  while (list.children.length > 30) list.removeChild(list.lastChild);
}

function clearLog() {
  const list = document.getElementById('log-list');
  if (list) list.innerHTML = '<div class="log-entry">Log cleared.</div>';
  knownLogLen = 0;
}

/* ── Stream Error Handling ──────────────────────────────────────────────*/
function handleStreamError(img) {
  streamErrorCnt++;
  const overlay = document.getElementById('no-signal');
  if (streamErrorCnt >= 2 && overlay) overlay.style.display = 'flex';

  // Retry after 3 s
  setTimeout(() => {
    const src = img.src.split('?')[0];
    img.src   = src + `?w=960&h=540&fps=25&t=${Date.now()}`;
    if (overlay) overlay.style.display = 'none';
    streamErrorCnt = 0;
  }, 3000);
}

/* ── Fullscreen ─────────────────────────────────────────────────────────*/
function toggleFullscreen() {
  const wrap = document.getElementById('main-video-wrap');
  if (!document.fullscreenElement) {
    wrap.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

/* ── Helpers ─────────────────────────────────────────────────────────── */
function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
