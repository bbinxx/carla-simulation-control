// ═══════════════════════════════════════════════════════════════
//  api.js — shared utilities: fetch wrapper, toast, log
// ═══════════════════════════════════════════════════════════════

// ── Toast ──────────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 3000) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + type;
  clearTimeout(window._tt);
  window._tt = setTimeout(() => (t.className = ''), duration);
}

// ── Activity Log ───────────────────────────────────────────────
function addLog(msg, type = 'info') {
  const box = document.getElementById('logBox');
  if (!box) return;
  const ts = new Date().toLocaleTimeString();
  const e  = document.createElement('div');
  e.className  = 'log-entry log-' + type;
  e.textContent = `[${ts}] ${msg}`;
  box.appendChild(e);
  box.scrollTop = box.scrollHeight;
  if (type === 'err')  console.error('[CARLA]', msg);
  if (type === 'warn') console.warn('[CARLA]',  msg);
}

function clearLog() {
  const box = document.getElementById('logBox');
  if (box) box.innerHTML = '';
}

// ── Core fetch wrapper ─────────────────────────────────────────
async function api(path, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    if (!res.ok) {
      const txt = await res.text();
      const msg = `HTTP ${res.status} on ${method} ${path}: ${txt.slice(0, 200)}`;
      addLog(msg, 'err');
      return { success: false, error: msg };
    }
    return await res.json();
  } catch (err) {
    const msg = `Network error on ${method} ${path}: ${err.message}`;
    addLog(msg, 'err');
    return { success: false, error: msg };
  }
}

// ── localStorage state ─────────────────────────────────────────
const STORAGE_KEY = 'carla_cp_state';

function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { return {}; }
}

function saveState() {
  const state = {};
  document.querySelectorAll('.win').forEach(w => {
    const id     = w.id;
    const pinned = w.classList.contains('pinned');
    const rect   = w.getBoundingClientRect();
    state[id] = {
      open:   w.classList.contains('open'),
      pinned,
      x:      parseInt(w.style.left) || rect.left,
      y:      parseInt(w.style.top)  || rect.top,
      width:  w.offsetWidth,
      height: w.offsetHeight,
    };
  });
  state.__fontSize = fontSize;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}
