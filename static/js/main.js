// ═══════════════════════════════════════════════════════════════
//  main.js — window management, font size, DOMContentLoaded
// ═══════════════════════════════════════════════════════════════

let zTop     = 200;
let fontSize = 14;   // px base

// ── Font Size ──────────────────────────────────────────────────
function applyFontSize() {
  document.documentElement.style.setProperty('--fs-base', fontSize + 'px');
  const el = document.getElementById('fontSizeVal');
  if (el) el.textContent = fontSize + 'px';
  saveState();
}

function changeFontSize(delta) {
  fontSize = Math.max(10, Math.min(22, fontSize + delta));
  applyFontSize();
}

// ── Waybar Focus ────────────────────────────────────────────────
function updateWaybarFocus() {
  document.querySelectorAll('.win').forEach(win => {
    const wbId = 'wb-' + win.id.replace('win-', '');
    const btn  = document.getElementById(wbId);
    if (btn) btn.classList.toggle('active', win.classList.contains('open'));
  });
}

// ── Window Management ──────────────────────────────────────────
function toggleWin(id) {
  const w = document.getElementById(id);
  if (!w) return;
  w.classList.contains('open') ? closeWin(id) : openWin(id);
}

function openWin(id, skipSave) {
  const w = document.getElementById(id);
  if (!w) return;
  w.classList.add('open');
  w.style.display = 'flex';
  bringToFront(w);

  if (id === 'win-lane') {
    fetchLaneInfo();
    clearInterval(lanePollInterval);
    lanePollInterval = setInterval(fetchLaneInfo, 2000);
  }
  if (id === 'win-cameras') {
    refreshCameras();
    clearInterval(camPollInterval);
    camPollInterval = setInterval(refreshCameras, 1000);
  }
  // Notify connection module when actors tab is opened via window
  if (id === 'win-actors') setActorsTabOpen(true);

  updateWaybarFocus();
  if (!skipSave) saveState();
}

function closeWin(id) {
  const w = document.getElementById(id);
  if (!w) return;
  w.classList.remove('open');
  w.style.display = 'none';

  if (id === 'win-lane') {
    clearInterval(lanePollInterval);
    lanePollInterval = null;
  }
  if (id === 'win-cameras') {
    stopCamPreview();
    clearInterval(camPollInterval);
    camPollInterval = null;
  }
  if (id === 'win-actors') setActorsTabOpen(false);

  updateWaybarFocus();
  saveState();
}

function bringToFront(el) {
  el.style.zIndex = ++zTop;
}

// ── Pin System ─────────────────────────────────────────────────
function togglePin(id) {
  const w   = document.getElementById(id);
  const btn = w.querySelector('.win-pin');
  if (w.classList.contains('pinned')) {
    w.classList.remove('pinned');
    btn.classList.remove('active');
    btn.title = 'Pin window';
  } else {
    w.classList.add('pinned');
    btn.classList.add('active');
    btn.title = 'Unpin window';
    bringToFront(w);
  }
  saveState();
}

// ── Draggable + Resizable Windows ─────────────────────────────
function initWindows() {
  document.querySelectorAll('.win-titlebar').forEach(bar => {
    let dragging = false, ox = 0, oy = 0;
    const win = bar.closest('.win');

    bar.addEventListener('mousedown', e => {
      if (win.classList.contains('pinned')) return;
      const tag = e.target.tagName;
      if (tag === 'BUTTON' || tag === 'INPUT' || tag === 'SELECT') return;
      if (e.target.closest('button')) return;
      dragging = true;
      const rect = win.getBoundingClientRect();
      ox = e.clientX - rect.left;
      oy = e.clientY - rect.top;
      bringToFront(win);
      e.preventDefault();
    });

    document.addEventListener('mousemove', e => {
      if (!dragging) return;
      const sb = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sb-width')) || 72;
      const tb = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--tb-height')) || 44;
      win.style.left = Math.max(sb, Math.min(window.innerWidth  - 60, e.clientX - ox)) + 'px';
      win.style.top  = Math.max(tb, Math.min(window.innerHeight - 40, e.clientY - oy)) + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (dragging) { dragging = false; saveState(); }
    });
  });

  document.querySelectorAll('.win-resize').forEach(handle => {
    let resizing = false, sx = 0, sy = 0, sw = 0, sh = 0;
    const win = handle.closest('.win');

    handle.addEventListener('mousedown', e => {
      resizing = true;
      sx = e.clientX; sy = e.clientY;
      sw = win.offsetWidth; sh = win.offsetHeight;
      bringToFront(win);
      e.preventDefault(); e.stopPropagation();
    });

    document.addEventListener('mousemove', e => {
      if (!resizing) return;
      const maxW = window.innerWidth  - win.getBoundingClientRect().left - 4;
      const maxH = window.innerHeight - win.getBoundingClientRect().top  - 4;
      win.style.width  = Math.max(260, Math.min(maxW, sw + e.clientX - sx)) + 'px';
      win.style.height = Math.max(120, Math.min(maxH, sh + e.clientY - sy)) + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (resizing) { resizing = false; saveState(); }
    });
  });

  document.querySelectorAll('.win').forEach(w => {
    w.addEventListener('mousedown', () => bringToFront(w));
  });
}

// ── Restore saved state ────────────────────────────────────────
function restoreState() {
  const state = loadState();
  if (!state) return;

  if (state.__fontSize) {
    fontSize = state.__fontSize;
    applyFontSize();
  }

  document.querySelectorAll('.win').forEach(w => {
    const id = w.id;
    const s  = state[id];
    if (!s) return;

    if (s.width)  w.style.width  = s.width  + 'px';
    if (s.height) w.style.height = s.height + 'px';

    const vw = window.innerWidth, vh = window.innerHeight;
    const sb = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sb-width'))  || 72;
    const tb = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--tb-height')) || 44;

    const x = Math.max(sb, Math.min(vw - 60, s.x || sb + 20));
    const y = Math.max(tb, Math.min(vh - 40, s.y || tb + 20));
    w.style.left = x + 'px';
    w.style.top  = y + 'px';

    if (s.pinned) {
      w.classList.add('pinned');
      const btn = w.querySelector('.win-pin');
      if (btn) btn.classList.add('active');
    }
    if (s.open) openWin(id, true);
  });
  updateWaybarFocus();
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildWeatherSliders();
  initWindows();
  restoreState();
  initHistory();

  // Start polling — will detect if server is already connected
  startPolling();

  // Ensure connect window is open on first load
  const state = loadState();
  if (!state['win-connect'] || !state['win-connect'].open) {
    openWin('win-connect', true);
  }
});

window.addEventListener('resize', saveState);
