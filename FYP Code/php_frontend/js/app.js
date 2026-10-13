/**
 * FYP Vehicle Tracking System — Frontend JavaScript
 * ==================================================
 * Handles:
 *  - Live clock & animations
 *  - Sidebar toggle
 *  - AJAX API interactions
 *  - Journey timeline rendering
 *  - Camera topology interactive map
 *  - Toast notifications
 */

'use strict';

/* ── DOM Ready ────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initSidebar();
  initAnimations();
  initTooltips();
  highlightActiveNav();
  animateStats();
});

/* ══════════════════════════════════════════════════════════════════════════
   CLOCK
   ══════════════════════════════════════════════════════════════════════════ */
function initClock() {
  const el = document.getElementById('clock');
  if (!el) return;
  function tick() {
    const now = new Date();
    el.textContent = now.toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  }
  tick();
  setInterval(tick, 1000);
}

/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR
   ══════════════════════════════════════════════════════════════════════════ */
function initSidebar() {
  const btn     = document.querySelector('.sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  if (!btn || !sidebar) return;

  btn.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebar_collapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
  });

  // Restore preference
  if (localStorage.getItem('sidebar_collapsed') === '1') {
    sidebar.classList.add('collapsed');
  }

  // Close on mobile overlay click
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
      if (!sidebar.contains(e.target) && !btn.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    }
  });
}

function highlightActiveNav() {
  const path = window.location.pathname.split('/').pop() || 'dashboard.php';
  document.querySelectorAll('.nav-item').forEach(link => {
    const href = link.getAttribute('href') || '';
    if (href === path || (path === '' && href === 'dashboard.php')) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   ENTRANCE ANIMATIONS
   ══════════════════════════════════════════════════════════════════════════ */
function initAnimations() {
  // Stagger fade-in for cards
  const cards = document.querySelectorAll('.stat-card, .section-card, .result-card, .cam-card');
  cards.forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(16px)';
    card.style.transition = `opacity 0.4s ease ${i * 0.06}s, transform 0.4s ease ${i * 0.06}s`;
    requestAnimationFrame(() => {
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    });
  });

  // Animate similarity bars
  document.querySelectorAll('.sim-fill').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0';
    setTimeout(() => { bar.style.width = target; }, 200);
  });

  // Animate timeline dots
  document.querySelectorAll('.tl-dot').forEach((dot, i) => {
    dot.style.opacity = '0';
    dot.style.transform = 'scale(0)';
    setTimeout(() => {
      dot.style.transition = 'all 0.3s ease';
      dot.style.opacity = '1';
      dot.style.transform = 'scale(1)';
    }, 100 + i * 120);
  });
}

function animateStats() {
  document.querySelectorAll('.stat-value').forEach(el => {
    const text = el.textContent.trim();
    const num  = parseInt(text, 10);
    if (isNaN(num) || num === 0) return;

    let start = 0;
    const step = Math.ceil(num / 30);
    const timer = setInterval(() => {
      start += step;
      if (start >= num) { el.textContent = num; clearInterval(timer); }
      else { el.textContent = start; }
    }, 30);
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   TOOLTIPS
   ══════════════════════════════════════════════════════════════════════════ */
function initTooltips() {
  document.querySelectorAll('[title]').forEach(el => {
    el.addEventListener('mouseenter', (e) => {
      const tip = document.createElement('div');
      tip.className = 'tooltip';
      tip.textContent = el.getAttribute('title');
      document.body.appendChild(tip);

      const r = el.getBoundingClientRect();
      tip.style.cssText = `
        position:fixed;
        top:${r.bottom + 6}px;
        left:${r.left + r.width/2}px;
        transform:translateX(-50%);
        background:#1e2237;
        border:1px solid rgba(108,99,255,.3);
        color:#e8eaf0;
        font-size:.75rem;
        padding:.35rem .65rem;
        border-radius:6px;
        z-index:9999;
        pointer-events:none;
        white-space:nowrap;
        box-shadow:0 4px 12px rgba(0,0,0,.4);
        animation:fadeIn .15s ease;
      `;
      el._tip = tip;
    });

    el.addEventListener('mouseleave', () => {
      if (el._tip) { el._tip.remove(); el._tip = null; }
    });
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
   ══════════════════════════════════════════════════════════════════════════ */
const toastContainer = (() => {
  let el = document.getElementById('toast-container');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast-container';
    el.style.cssText = `
      position:fixed;bottom:1.5rem;right:1.5rem;
      z-index:9999;display:flex;flex-direction:column;gap:.5rem;
      pointer-events:none;
    `;
    document.body.appendChild(el);
  }
  return el;
})();

function showToast(message, type = 'info', duration = 3500) {
  const colors = {
    info:    { bg: 'rgba(108,99,255,.15)', border: 'rgba(108,99,255,.4)', icon: 'ℹ️' },
    success: { bg: 'rgba(46,204,113,.15)', border: 'rgba(46,204,113,.4)',  icon: '✅' },
    error:   { bg: 'rgba(255,71,87,.15)',  border: 'rgba(255,71,87,.4)',   icon: '❌' },
    warning: { bg: 'rgba(255,140,66,.15)', border: 'rgba(255,140,66,.4)',  icon: '⚠️' },
  };
  const c   = colors[type] || colors.info;
  const div = document.createElement('div');
  div.style.cssText = `
    background:${c.bg};border:1px solid ${c.border};
    color:#e8eaf0;border-radius:10px;
    padding:.75rem 1.1rem;font-size:.85rem;
    display:flex;align-items:center;gap:.65rem;
    backdrop-filter:blur(8px);
    pointer-events:auto;cursor:pointer;
    animation:slideIn .2s ease;
    min-width:240px;max-width:360px;
    box-shadow:0 8px 24px rgba(0,0,0,.4);
  `;
  div.innerHTML = `<span>${c.icon}</span><span style="flex:1">${message}</span>`;
  div.addEventListener('click', () => div.remove());
  toastContainer.appendChild(div);
  setTimeout(() => { div.style.opacity = '0'; div.style.transition = 'opacity .3s'; setTimeout(() => div.remove(), 300); }, duration);
  return div;
}

/* ══════════════════════════════════════════════════════════════════════════
   AJAX API HELPERS
   ══════════════════════════════════════════════════════════════════════════ */
const API_BASE = 'http://127.0.0.1:5000/api';

async function apiGet(endpoint) {
  try {
    const res  = await fetch(API_BASE + endpoint);
    const data = await res.json();
    return data;
  } catch (e) {
    console.error('API GET error:', e);
    return { success: false, error: e.message };
  }
}

async function apiPost(endpoint, body) {
  try {
    const res  = await fetch(API_BASE + endpoint, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const data = await res.json();
    return data;
  } catch (e) {
    console.error('API POST error:', e);
    return { success: false, error: e.message };
  }
}

async function apiPostForm(endpoint, formData) {
  try {
    const res  = await fetch(API_BASE + endpoint, { method: 'POST', body: formData });
    const data = await res.json();
    return data;
  } catch (e) {
    console.error('API POST form error:', e);
    return { success: false, error: e.message };
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   LIVE STATUS POLLING
   ══════════════════════════════════════════════════════════════════════════ */
async function pollStatus() {
  const dot  = document.querySelector('.status-dot');
  const span = dot ? dot.nextElementSibling : null;
  if (!dot) return;

  try {
    const res = await apiGet('/status');
    if (res.success) {
      dot.className  = 'status-dot online';
      if (span) span.textContent = 'API Online';
    } else {
      dot.className  = 'status-dot offline';
      if (span) span.textContent = 'API Offline';
    }
  } catch {
    dot.className = 'status-dot offline';
    if (span) span.textContent = 'API Offline';
  }
}
setInterval(pollStatus, 15000);

/* ══════════════════════════════════════════════════════════════════════════
   INTERACTIVE TOPOLOGY MAP (Dashboard)
   ══════════════════════════════════════════════════════════════════════════ */
function initTopologyMap() {
  const nodes = document.querySelectorAll('.topo-node');
  nodes.forEach(node => {
    node.addEventListener('mouseenter', () => {
      const cam  = node.dataset.cam;
      // Highlight connected nodes (stored in CAMERA_TOPOLOGY injected as window var)
      const next = (window.CAMERA_TOPOLOGY || {})[cam] || [];
      nodes.forEach(n => {
        if (next.includes(n.dataset.cam)) {
          n.style.borderColor = 'rgba(255,107,157,.6)';
          n.style.background  = 'rgba(255,107,157,.08)';
        }
      });
    });
    node.addEventListener('mouseleave', () => {
      nodes.forEach(n => {
        n.style.borderColor = '';
        n.style.background  = '';
      });
    });
  });
}
document.addEventListener('DOMContentLoaded', initTopologyMap);

/* ══════════════════════════════════════════════════════════════════════════
   LIVE VEHICLE SEARCH (AJAX – bypasses PHP form submit for quick preview)
   ══════════════════════════════════════════════════════════════════════════ */
function initLiveSearch() {
  const plate = document.getElementById('plate_number');
  if (!plate) return;

  let timer;
  plate.addEventListener('input', () => {
    clearTimeout(timer);
    const val = plate.value.trim();
    if (val.length < 2) return;
    timer = setTimeout(async () => {
      const res = await apiPost('/query_description', {
        plate_number: val, top_k: 3
      });
      if (res.success && res.matches && res.matches.length > 0) {
        showToast(`Found ${res.matches.length} vehicle(s) matching plate "${val}"`, 'info');
      }
    }, 600);
  });
}
document.addEventListener('DOMContentLoaded', initLiveSearch);

/* ══════════════════════════════════════════════════════════════════════════
   PROCESS VIDEO — live progress polling
   ══════════════════════════════════════════════════════════════════════════ */
function showProcessing() {
  const btn = document.getElementById('btn-process');
  const ind = document.getElementById('processing-indicator');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin-right:.5rem"></span>Processing…'; }
  if (ind) ind.style.display = 'flex';
  showToast('Processing started. This may take a minute…', 'info', 5000);
}

/* ══════════════════════════════════════════════════════════════════════════
   KEYBOARD SHORTCUTS
   ══════════════════════════════════════════════════════════════════════════ */
document.addEventListener('keydown', (e) => {
  // Alt+Q → Query page
  if (e.altKey && e.key === 'q') window.location = 'query.php';
  // Alt+D → Dashboard
  if (e.altKey && e.key === 'd') window.location = 'dashboard.php';
  // Alt+T → Tracks
  if (e.altKey && e.key === 't') window.location = 'tracks.php';
  // Escape → close modals
  if (e.key === 'Escape') document.querySelectorAll('.modal').forEach(m => m.remove());
});

/* ══════════════════════════════════════════════════════════════════════════
   COPY TO CLIPBOARD helper
   ══════════════════════════════════════════════════════════════════════════ */
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard!', 'success', 2000);
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   GLOBAL CSS INJECT (for fadeIn / slideIn keyframes)
   ══════════════════════════════════════════════════════════════════════════ */
const _styleSheet = document.createElement('style');
_styleSheet.textContent = `
@keyframes fadeIn   { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
@keyframes slideIn  { from { opacity:0; transform:translateX(20px); } to { opacity:1; transform:translateX(0); } }
`;
document.head.appendChild(_styleSheet);
