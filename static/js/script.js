// d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\static\js\script.js
// ═══════════════════════════════════════════════════════════════
//  CARLA CONTROL PANEL — script.js
// ═══════════════════════════════════════════════════════════════

// ── App State ──────────────────────────────────────────────────
let serverLocations = {};
let pollInterval = null;
let weatherValues = {};
let screenshotB64 = null;
let lanePollInterval = null;
let camPollInterval = null;
let zTop = 200;
let fontSize = 14;   // px base

const STORAGE_KEY = 'carla_cp_state';

const weatherParams = [
  { key: 'cloudiness', label: 'Cloudiness', min: 0, max: 100 },
  { key: 'precipitation', label: 'Precipitation', min: 0, max: 100 },
  { key: 'precipitation_deposits', label: 'Precip Deposits', min: 0, max: 100 },
  { key: 'wind_intensity', label: 'Wind Intensity', min: 0, max: 100 },
  { key: 'sun_azimuth_angle', label: 'Sun Azimuth', min: 0, max: 360 },
  { key: 'sun_altitude_angle', label: 'Sun Altitude', min: -90, max: 90 },
  { key: 'fog_density', label: 'Fog Density', min: 0, max: 100 },
  { key: 'fog_distance', label: 'Fog Distance', min: 0, max: 200 },
  { key: 'wetness', label: 'Wetness', min: 0, max: 100 },
];

// ── localStorage State ─────────────────────────────────────────
function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { return {}; }
}

function saveState() {
  const state = {};
  document.querySelectorAll('.win').forEach(w => {
    const id = w.id;
    const pinned = w.classList.contains('pinned');
    const rect = w.getBoundingClientRect();
    state[id] = {
      open: w.classList.contains('open'),
      pinned,
      x: parseInt(w.style.left) || rect.left,
      y: parseInt(w.style.top) || rect.top,
      width: w.offsetWidth,
      height: w.offsetHeight,
    };
  });
  state.__fontSize = fontSize;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function restoreState() {
  const state = loadState();
  if (!state) return;

  if (state.__fontSize) {
    fontSize = state.__fontSize;
    applyFontSize();
  }

  document.querySelectorAll('.win').forEach(w => {
    const id = w.id;
    const s = state[id];
    if (!s) return;

    if (s.width) w.style.width = s.width + 'px';
    if (s.height) w.style.height = s.height + 'px';

    const vw = window.innerWidth, vh = window.innerHeight;
    const sb = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sb-width')) || 72;
    const tb = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--tb-height')) || 44;

    const maxX = vw - 60, maxY = vh - 40;
    const x = Math.max(sb, Math.min(maxX, s.x || sb + 20));
    const y = Math.max(tb, Math.min(maxY, s.y || tb + 20));

    w.style.left = x + 'px';
    w.style.top = y + 'px';

    if (s.pinned) {
      w.classList.add('pinned');
      const btn = w.querySelector('.win-pin');
      if (btn) btn.classList.add('active');
    }

    if (s.open) openWin(id, true);
  });
  updateWaybarFocus();
}

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
    const btn = document.getElementById(wbId);
    if (btn) {
      if (win.classList.contains('open')) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }
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
  updateWaybarFocus();
  saveState();
}

function bringToFront(el) {
  el.style.zIndex = ++zTop;
}

// ── Pin System ─────────────────────────────────────────────────
function togglePin(id) {
  const w = document.getElementById(id);
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
      let nx = Math.max(sb, Math.min(window.innerWidth - 60, e.clientX - ox));
      let ny = Math.max(tb, Math.min(window.innerHeight - 40, e.clientY - oy));
      win.style.left = nx + 'px';
      win.style.top = ny + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (dragging) { dragging = false; saveState(); }
    });
  });

  // Resize handles
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
      const tb = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--tb-height')) || 44;
      const maxW = window.innerWidth - win.getBoundingClientRect().left - 4;
      const maxH = window.innerHeight - win.getBoundingClientRect().top - 4;
      win.style.width = Math.max(260, Math.min(maxW, sw + e.clientX - sx)) + 'px';
      win.style.height = Math.max(120, Math.min(maxH, sh + e.clientY - sy)) + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (resizing) { resizing = false; saveState(); }
    });
  });

  // Click -> bring to front
  document.querySelectorAll('.win').forEach(w => {
    w.addEventListener('mousedown', () => bringToFront(w));
  });
}

// ── Toast ──────────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 3000) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + type;
  clearTimeout(window._tt);
  window._tt = setTimeout(() => (t.className = ''), duration);
}

// ── Log ────────────────────────────────────────────────────────
function addLog(msg, type = 'info') {
  const box = document.getElementById('logBox');
  const ts = new Date().toLocaleTimeString();
  const e = document.createElement('div');
  e.className = 'log-entry log-' + type;
  e.textContent = `[${ts}] ${msg}`;
  box.appendChild(e);
  box.scrollTop = box.scrollHeight;
  if (type === 'err') console.error('[CARLA]', msg);
  if (type === 'warn') console.warn('[CARLA]', msg);
}

function clearLog() { document.getElementById('logBox').innerHTML = ''; }

// ── API wrapper ────────────────────────────────────────────────
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

// ── History / DB ───────────────────────────────────────────────
async function initHistory() {
  try {
    const res = await api('/history', 'GET');
    if (res.success) {
      const hosts = res.hosts || [];
      const dl = document.getElementById('hostHistory');
      if (dl) dl.innerHTML = hosts.map(h => `<option value="${h.host}">`).join('');
      if (res.last_connection) {
        const hi = document.getElementById('hostInput');
        const pi = document.getElementById('portInput');
        if (hi) hi.value = res.last_connection.host;
        if (pi) pi.value = res.last_connection.port;
      }
      serverLocations = res.locations || {};
      renderSavedLocations();
      addLog(`History loaded — ${hosts.length} host(s), ${Object.keys(serverLocations).length} location(s)`, 'info');
    } else {
      addLog('Failed to load history: ' + (res.error || 'unknown'), 'warn');
    }
  } catch (e) {
    addLog('initHistory exception: ' + e.message, 'err');
  }
}

async function saveHostHistory(host, port) {
  const res = await api('/history/host', 'POST', { host, port });
  if (!res.success) addLog('Host save failed: ' + res.error, 'warn');
  initHistory();
}

function renderSavedLocations() {
  const sel = document.getElementById('savedLocations');
  const camSel = document.getElementById('camSavedLocations');
  const optStr = '<option value="">-- Select --</option>' +
    Object.keys(serverLocations).map(k => `<option value="${k}">${k}</option>`).join('');
  if (sel) sel.innerHTML = optStr;
  if (camSel) camSel.innerHTML = optStr;
}

async function saveSpectatorPosition() {
  const name = document.getElementById('locName').value.trim() ||
    'Location ' + new Date().toLocaleTimeString();
  const payload = {
    name,
    x: document.getElementById('sX').textContent,
    y: document.getElementById('sY').textContent,
    z: document.getElementById('sZ').textContent,
    pitch: document.getElementById('sPitch').textContent,
    yaw: document.getElementById('sYaw').textContent,
    roll: document.getElementById('sRoll').textContent,
  };
  toast(`Saving "${name}"...`);
  const res = await api('/history/location', 'POST', payload);
  if (res.success) {
    toast(`Saved: ${name}`, 'ok');
    addLog(`Location saved: ${name}`, 'ok');
    document.getElementById('locName').value = '';
    initHistory();
  } else {
    toast('Save failed: ' + res.error, 'err');
    addLog('Save location error: ' + res.error, 'err');
  }
}

function loadSpectatorPosition(name) {
  if (!name) return;
  const loc = serverLocations[name];
  if (!loc) { toast('Location not found: ' + name, 'err'); return; }
  document.getElementById('specX').value = loc.x;
  document.getElementById('specY').value = loc.y;
  document.getElementById('specZ').value = loc.z;
  document.getElementById('specPitch').value = loc.pitch;
  document.getElementById('specYaw').value = loc.yaw;
  document.getElementById('specRoll').value = loc.roll;
  toast('Loaded: ' + name, 'ok');
  addLog('Location loaded: ' + name, 'ok');
  moveSpectator();
  document.getElementById('savedLocations').value = '';
}

// ── Weather Sliders ────────────────────────────────────────────
function buildWeatherSliders(values = {}) {
  const wrap = document.getElementById('weatherSliders');
  if (!wrap) return;
  wrap.innerHTML = '';
  weatherParams.forEach(p => {
    const val = values[p.key] ?? weatherValues[p.key] ?? 0;
    weatherValues[p.key] = val;
    wrap.innerHTML += `
      <div class="slider-row">
        <label>${p.label}</label>
        <input type="range" min="${p.min}" max="${p.max}" value="${val}"
          oninput="weatherValues['${p.key}']=parseFloat(this.value);document.getElementById('sv_${p.key}').textContent=this.value"/>
        <span class="sv" id="sv_${p.key}">${val}</span>
      </div>`;
  });
}

// ── Color helpers ──────────────────────────────────────────────
function syncColor(el) {
  const hex = el.value;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  document.getElementById('colorText').value = `${r},${g},${b}`;
}

function syncColorText(el) {
  const p = el.value.split(',').map(Number);
  if (p.length === 3 && p.every(n => !isNaN(n)))
    document.getElementById('colorPicker').value =
      '#' + p.map(n => Math.min(255, Math.max(0, n)).toString(16).padStart(2, '0')).join('');
}

// ── Connect / Disconnect ───────────────────────────────────────
async function connect() {
  const host = document.getElementById('hostInput').value.trim();
  const port = document.getElementById('portInput').value;
  const timeout = document.getElementById('timeoutInput').value;
  if (!host) { toast('Enter a host address', 'err'); return; }

  const btn = document.getElementById('connectBtn');
  btn.disabled = true; btn.textContent = 'CONNECTING...';
  toast(`Connecting to ${host}:${port}...`);
  addLog(`Connecting to ${host}:${port}...`);

  const data = await api('/connect', 'POST', { host, port, timeout });
  btn.disabled = false; btn.textContent = 'CONNECT';

  if (data.success) {
    setConnected(true, data);
    saveHostHistory(host, port);
    toast(`Connected — ${data.map}`, 'ok');
    addLog(`Connected. Map: ${data.map} | TM port: ${data.tm_port}`, 'ok');
    loadMaps(); loadBlueprints(); loadAllBlueprints(); loadEmergencyBlueprints(); startPolling();
  } else {
    toast('Connection failed: ' + data.error, 'err', 5000);
    addLog('Connect error: ' + data.error, 'err');
  }
}

async function disconnect() {
  clearInterval(pollInterval);
  stopStream();
  toast('Disconnecting...');
  const data = await api('/disconnect', 'POST');
  setConnected(false);
  toast(data.success ? 'Disconnected' : 'Disconnect error: ' + data.error, data.success ? 'info' : 'err');
  addLog(data.success ? 'Disconnected' : 'Disconnect error: ' + data.error, data.success ? 'warn' : 'err');
}

async function toggleDebugBboxes() {
  const btn = document.getElementById('debugBoxesBtn');
  const res = await api('/debug/toggle_bboxes', 'POST');
  if (res.success) {
    btn.textContent = res.enabled ? 'HIDE DEBUG BBOXES' : 'SHOW DEBUG BBOXES';
    toast(`Debug BBoxes: ${res.enabled ? 'ON' : 'OFF'}`, 'ok');
    addLog(`Debug BBoxes: ${res.enabled ? 'ON' : 'OFF'}`);
  } else {
    toast('BBox toggle failed: ' + res.error, 'err');
  }
}

// ── Connected State ────────────────────────────────────────────
function setConnected(state, data = {}) {
  const dot = document.getElementById('statusDot');
  const connDot = document.getElementById('connDot');
  const wbStatus = document.getElementById('wb-status');
  const statusText = document.getElementById('statusText');

  dot.className = 'sdot' + (state ? ' ok' : '');
  connDot.className = 'sdot' + (state ? ' ok' : '');
  wbStatus.className = 'waybar-btn' + (state ? ' status-ok' : '');

  statusText.style.color = state ? 'var(--c-green)' : 'var(--c-red)';
  statusText.textContent = state ? `${data.host}:${data.port}` : 'DISCONNECTED';

  document.getElementById('connectBtn').style.display = state ? 'none' : 'flex';
  document.getElementById('disconnectBtn').style.display = state ? 'flex' : 'none';
  document.getElementById('disconnectedPlaceholder').style.display = state ? 'none' : 'flex';

  if (state) {
    document.getElementById('infoHost').textContent = data.host;
    document.getElementById('infoPort').textContent = data.port;
    document.getElementById('infoMap').textContent = data.map || '—';
  } else {
    document.getElementById('infoMap').textContent = '—';
  }
}

// ── Polling ────────────────────────────────────────────────────
function startPolling() {
  clearInterval(pollInterval);
  pollInterval = setInterval(refreshStatus, 3000);
  refreshStatus();
}

async function refreshStatus() {
  const data = await api('/status');
  if (!data.connected) {
    if (document.getElementById('connectBtn').style.display === 'none') {
      setConnected(false);
      clearInterval(pollInterval);
      toast('Lost connection to CARLA', 'err');
      addLog('Connection lost', 'err');
    }
    return;
  }

  // Sync UI if we find we are connected but UI says otherwise
  if (document.getElementById('connectBtn').style.display !== 'none') {
    setConnected(true, data);
  }
  document.getElementById('infoMap').textContent = data.map;
  document.getElementById('infoActors').textContent = data.actor_count;
  document.getElementById('statActors').textContent = data.actor_count;
  document.getElementById('statVehicles').textContent = data.vehicle_count;
  document.getElementById('statWalkers').textContent = data.walker_count;
  document.getElementById('statSensors').textContent = data.sensor_count;

  if (data.spectator) updateSpectatorDisplay(data.spectator);

  const tbody = document.getElementById('actorTableBody');
  if (!data.actors || data.actors.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="tbl-empty">No actors in world</td></tr>`;
  } else {
    tbody.innerHTML = data.actors.map(a => {
      let cls = 'badge-o';
      if (a.type.startsWith('vehicle')) cls = 'badge-v';
      else if (a.type.startsWith('walker')) cls = 'badge-w';
      else if (a.type.startsWith('sensor')) cls = 'badge-s';
      else if (a.type.includes('traffic')) cls = 'badge-t';
      return `<tr>
        <td>${a.id}</td>
        <td><span class="badge ${cls}">${a.type.split('.').slice(0, 2).join('.')}</span></td>
        <td>${a.x}</td><td>${a.y}</td><td>${a.z}</td>
        <td style="display:flex; gap:4px;">
          <button class="btn btn-cyan btn-xs" onclick="attachCamera(${a.id})" title="Attach Camera">CAM</button>
          <button class="btn btn-danger btn-xs" onclick="destroyActor(${a.id})">X</button>
        </td>
      </tr>`;
    }).join('');
  }
  if (data.weather) buildWeatherSliders(data.weather);
}

// ── Spectator ──────────────────────────────────────────────────
function updateSpectatorDisplay(s) {
  document.getElementById('sX').textContent = s.x;
  document.getElementById('sY').textContent = s.y;
  document.getElementById('sZ').textContent = s.z;
  document.getElementById('sPitch').textContent = s.pitch;
  document.getElementById('sYaw').textContent = s.yaw;
  document.getElementById('sRoll').textContent = s.roll;
}

async function fetchSpectator() {
  const data = await api('/spectator/get');
  if (data.success) {
    updateSpectatorDisplay(data);
    toast('Spectator updated', 'ok');
    addLog(`Spectator: X=${data.x} Y=${data.y} Z=${data.z}`);
  } else {
    toast('Spectator fetch failed: ' + data.error, 'err');
  }
}

async function moveSpectator() {
  const d = {
    x: parseFloat(document.getElementById('specX').value),
    y: parseFloat(document.getElementById('specY').value),
    z: parseFloat(document.getElementById('specZ').value),
    pitch: parseFloat(document.getElementById('specPitch').value),
    yaw: parseFloat(document.getElementById('specYaw').value),
    roll: parseFloat(document.getElementById('specRoll').value),
  };
  toast('Moving camera...');
  const data = await api('/spectator/set', 'POST', d);
  if (data.success) {
    toast(`Camera moved to (${d.x}, ${d.y}, ${d.z})`, 'ok');
    addLog(`Spectator -> (${d.x}, ${d.y}, ${d.z})`, 'ok');
  } else {
    toast('Move failed: ' + data.error, 'err');
  }
}

// ── Maps ───────────────────────────────────────────────────────
async function loadMaps() {
  const data = await api('/map/list');
  if (data.success) {
    document.getElementById('mapSelect').innerHTML =
      data.maps.map(m => `<option value="${m}">${m.split('/').pop()}</option>`).join('');
    addLog(`Maps loaded: ${data.maps.length}`);
  } else {
    addLog('Map list error: ' + data.error, 'err');
  }
}

async function loadMap() {
  const map = document.getElementById('mapSelect').value;
  if (!map) { toast('Select a map first', 'err'); return; }
  toast('Loading ' + map.split('/').pop() + '...');
  const data = await api('/map/load', 'POST', { map });
  if (data.success) {
    toast('Map loaded: ' + data.map, 'ok');
    addLog('Map loaded: ' + data.map, 'ok');
  } else {
    toast('Map load failed: ' + data.error, 'err', 5000);
    addLog('Map load error: ' + data.error, 'err');
  }
}

// ── Emergency Blueprints ───────────────────────────────────────
async function loadEmergencyBlueprints() {
  const data = await api('/blueprints/emergency');
  const sel = document.getElementById('emergencyBp');
  if (data.success && data.blueprints.length > 0) {
    sel.innerHTML = data.blueprints.map(b => `<option value="${b}">${b}</option>`).join('');
    addLog(`Emergency blueprints: ${data.blueprints.length}`);
  } else {
    sel.innerHTML = '<option value="">None found — using random</option>';
    addLog('No emergency vehicle blueprints found', 'warn');
  }
}

async function spawnEmergency() {
  const bp = document.getElementById('emergencyBp').value;
  const autopilot = document.getElementById('emergencyAutopilot').checked;
  const atSpectator = false;
  toast('Spawning ' + (bp || 'random emergency') + '...');
  const data = await api('/spawn/emergency', 'POST', { blueprint: bp, autopilot, at_spectator: atSpectator });
  if (data.success) {
    toast(`Emergency spawned: ${data.blueprint} (ID:${data.actor_id})`, 'ok');
    addLog(`Emergency ID:${data.actor_id} — ${data.blueprint}`, 'ok');
  } else {
    toast('Emergency spawn failed: ' + data.error, 'err', 5000);
  }
}

// ── Blueprints ─────────────────────────────────────────────────
async function loadBlueprints() {
  const data = await api('/blueprints?filter=vehicle.*');
  if (data.success) {
    document.getElementById('vehicleBp').innerHTML =
      data.blueprints.map(b => `<option value="${b}">${b}</option>`).join('');
    addLog(`Vehicle blueprints: ${data.blueprints.length}`);
  } else {
    addLog('Blueprint load error: ' + data.error, 'err');
  }
}

async function loadAllBlueprints() {
  const data = await api('/blueprints?filter=*');
  if (data.success)
    document.getElementById('anyBp').innerHTML =
      data.blueprints.map(b => `<option value="${b}">${b}</option>`).join('');
}

async function filterBps() {
  const filt = document.getElementById('bpFilter').value.trim() || '*';
  const data = await api('/blueprints?filter=' + encodeURIComponent(filt));
  if (data.success) {
    document.getElementById('anyBp').innerHTML =
      data.blueprints.map(b => `<option value="${b}">${b}</option>`).join('');
    toast(`${data.blueprints.length} result(s)`, 'ok');
    addLog(`Blueprint filter "${filt}": ${data.blueprints.length} results`);
  } else {
    toast('Filter error: ' + data.error, 'err');
  }
}

// ── Spawn ──────────────────────────────────────────────────────
async function spawnVehicle() {
  const bp = document.getElementById('vehicleBp').value;
  if (!bp) { toast('Select a blueprint', 'err'); return; }
  toast('Spawning ' + bp + '...');
  const data = await api('/spawn/vehicle', 'POST', {
    blueprint: bp,
    color: document.getElementById('colorText').value,
    autopilot: document.getElementById('autopilotCb').checked,
    autopilot: document.getElementById('autopilotCb').checked,
  });
  if (data.success) {
    toast(`Spawned ${data.blueprint} (ID:${data.actor_id})`, 'ok');
    addLog(`Vehicle spawned — ID:${data.actor_id}`, 'ok');
  } else {
    toast('Spawn failed: ' + data.error, 'err', 5000);
  }
}

async function spawnNPC() {
  const count = parseInt(document.getElementById('npcCount').value);
  const radius = 0.0;
  toast(`Spawning ${count} NPCs...`);
  const data = await api('/spawn/npc', 'POST', { count, radius });
  if (data.success) {
    toast(`Spawned ${data.spawned} NPC vehicle(s)`, 'ok');
    addLog(`NPCs spawned: ${data.spawned}/${count}`, 'ok');
  } else {
    toast('NPC spawn failed: ' + data.error, 'err', 5000);
  }
}

async function spawnWalkers() {
  const count = parseInt(document.getElementById('walkerCount').value);
  toast(`Spawning ${count} walkers...`);
  const data = await api('/spawn/walker', 'POST', { count });
  if (data.success) {
    toast(`Spawned ${data.spawned} walker(s)`, 'ok');
    addLog(`Walkers spawned: ${data.spawned}/${count}`, 'ok');
  } else {
    toast('Walker spawn failed: ' + data.error, 'err', 5000);
  }
}

async function spawnCamera() {
  const w = parseInt(document.getElementById('camW').value);
  const h = parseInt(document.getElementById('camH').value);
  const f = parseInt(document.getElementById('camFov').value);
  toast(`Spawning camera ${w}x${h}...`);
  const data = await api('/spawn/camera', 'POST', { width: w, height: h, fov: f });
  if (data.success) {
    toast(`Camera spawned (ID:${data.actor_id})`, 'ok');
    addLog(`Camera spawned — ID:${data.actor_id}`, 'ok');
  } else {
    toast('Camera spawn failed: ' + data.error, 'err', 5000);
  }
}

async function spawnAny() {
  const bp = document.getElementById('anyBp').value;
  if (!bp) { toast('Select a blueprint', 'err'); return; }
  const zOff = parseFloat(document.getElementById('anyZOffset').value);
  const auto = document.getElementById('anyAutopilot').checked;
  toast('Spawning ' + bp + '...');
  const data = await api('/spawn/any', 'POST', { blueprint: bp, z_offset: zOff, autopilot: auto });
  if (data.success) {
    toast(`Spawned ${data.blueprint} (ID:${data.actor_id})`, 'ok');
    addLog(`Spawned — ID:${data.actor_id}`, 'ok');
  } else {
    toast('Spawn failed: ' + data.error, 'err', 5000);
  }
}

// ── Destroy ────────────────────────────────────────────────────
async function destroyFilter(filter) {
  toast('Destroying ' + filter + '...');
  addLog('Destroying all: ' + filter, 'warn');
  const data = await api('/destroy/all', 'POST', { filter });
  if (data.success) {
    toast(`Destroyed ${data.destroyed} actor(s)`, 'ok');
    addLog(`Destroyed ${data.destroyed} (filter: ${filter})`, 'warn');
  } else {
    toast('Destroy failed: ' + data.error, 'err', 5000);
  }
}

async function destroyActor(id) {
  toast('Destroying ID:' + id + '...');
  const data = await api('/destroy/actor', 'POST', { id });
  if (data.success) {
    toast(`Actor ${id} destroyed`, 'ok');
    addLog(`Actor ${id} destroyed`, 'warn');
    refreshStatus();
  } else {
    toast('Destroy failed: ' + data.error, 'err');
  }
}

async function fixAllVehicles() {
  toast('Applying strict TM rules...');
  const data = await api('/tm/fix_all', 'POST');
  if (data.success) {
    toast(`Fixed ${data.fixed}/${data.total} vehicle(s)`, 'ok', 4000);
    addLog(`TM fix: ${data.fixed}/${data.total} vehicles`, 'ok');
  } else {
    toast('Fix failed: ' + data.error, 'err', 5000);
  }
}

// ── Weather ────────────────────────────────────────────────────
async function weatherPreset(preset) {
  toast('Applying preset: ' + preset + '...');
  const data = await api('/weather/preset', 'POST', { preset });
  if (data.success) {
    toast('Weather: ' + preset, 'ok');
    addLog('Weather preset: ' + preset, 'ok');
    if (data.values) buildWeatherSliders(data.values);
  } else {
    toast('Preset failed: ' + data.error, 'err', 5000);
  }
}

async function applyWeather() {
  toast('Applying weather...');
  const data = await api('/weather', 'POST', weatherValues);
  if (data.success) {
    toast('Weather applied', 'ok');
    addLog('Custom weather applied', 'ok');
  } else {
    toast('Weather error: ' + data.error, 'err', 5000);
  }
}

// ── Traffic Lights ─────────────────────────────────────────────
async function loadTrafficLights() {
  const radius = document.getElementById('tlRadius').value;
  const data = await api('/traffic_lights?radius=' + radius);
  const tbody = document.getElementById('tlTableBody');
  if (!data.success) {
    tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty tbl-err">${data.error}</td></tr>`;
    return;
  }
  if (data.lights.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty">No lights within ${radius}m</td></tr>`;
    return;
  }
  tbody.innerHTML = data.lights.map(tl => {
    const s = tl.state.toLowerCase();
    const cls = s === 'red' ? 'tl-r' : s === 'green' ? 'tl-g' : s === 'yellow' ? 'tl-y' : 'tl-o';
    return `<tr>
      <td>${tl.id}</td>
      <td><span class="${cls}">${tl.state}</span></td>
      <td>${tl.distance}</td>
      <td>
        <div class="tl-btns">
          <button class="btn btn-danger btn-xs"  onclick="setTL(${tl.id},'red')">R</button>
          <button class="btn btn-success btn-xs" onclick="setTL(${tl.id},'green')">G</button>
          <button class="btn btn-warn btn-xs"    onclick="setTL(${tl.id},'yellow')">Y</button>
        </div>
      </td>
      <td><button class="btn btn-cyan btn-xs" onclick="freezeTL(${tl.id})">FRZ</button></td>
    </tr>`;
  }).join('');
  toast(`${data.lights.length} light(s)`, 'ok');
  addLog(`Traffic lights: ${data.lights.length} within ${radius}m`, 'ok');
}

async function setTL(id, state) {
  const data = await api('/traffic_light/set', 'POST', { id, state, freeze: true });
  if (data.success) { toast(`TL ${id} -> ${state}`, 'ok'); setTimeout(loadTrafficLights, 300); }
  else toast('TL set failed: ' + data.error, 'err');
}

async function freezeTL(id) {
  const data = await api('/traffic_light/set', 'POST', { id, freeze: true });
  if (data.success) toast(`TL ${id} frozen`, 'ok');
  else toast('Freeze failed: ' + data.error, 'err');
}

async function freezeAll(state) {
  toast('All lights -> ' + state + '...');
  const data = await api('/traffic_light/freeze_all', 'POST', { freeze: true, state });
  if (data.success) { toast('All lights -> ' + state, 'ok'); setTimeout(loadTrafficLights, 400); }
  else toast('Freeze-all failed: ' + data.error, 'err');
}

async function unfreezeAll() {
  const data = await api('/traffic_light/freeze_all', 'POST', { freeze: false });
  if (data.success) { toast('Traffic lights resumed', 'ok'); setTimeout(loadTrafficLights, 400); }
  else toast('Unfreeze failed: ' + data.error, 'err');
}

// ── Environment ────────────────────────────────────────────────
async function toggleEnvObject(enable) {
  const label = document.getElementById('envObjectSelect').value;
  toast((enable ? 'Showing' : 'Hiding') + ' ' + label + '...');
  const data = await api('/env_objects/toggle', 'POST', { label, enable });
  if (data.success) {
    toast(`${enable ? 'Shown' : 'Hidden'}: ${label} (${data.count} objects)`, 'ok');
    addLog(`${enable ? 'Shown' : 'Hidden'}: ${label} — ${data.count}`, 'ok');
  } else {
    toast('Env toggle failed: ' + data.error, 'err', 5000);
  }
}

// ── Screenshot ─────────────────────────────────────────────────
async function takeScreenshot() {
  const btn = document.getElementById('ssBtn');
  btn.disabled = true; btn.textContent = 'CAPTURING...';
  document.getElementById('ssStatus').textContent = 'Capturing frame...';
  toast('Capturing screenshot...');

  const data = await api('/screenshot', 'POST', {
    width: parseInt(document.getElementById('ssW').value),
    height: parseInt(document.getElementById('ssH').value),
    fov: parseInt(document.getElementById('ssFov').value),
  });
  btn.disabled = false; btn.textContent = 'CAPTURE';

  if (data.success) {
    screenshotB64 = data.image;
    const img = document.getElementById('screenshotImg');
    img.src = 'data:image/png;base64,' + data.image;
    img.style.display = 'block';
    document.getElementById('ssDownloadBtn').style.display = 'inline-flex';
    document.getElementById('ssStatus').textContent = `Captured ${data.width}x${data.height}`;
    toast(`Screenshot ${data.width}x${data.height}`, 'ok');
  } else {
    document.getElementById('ssStatus').textContent = 'Error: ' + data.error;
    toast('Screenshot failed: ' + data.error, 'err', 6000);
  }
}

function downloadScreenshot() {
  if (!screenshotB64) { toast('No screenshot to download', 'err'); return; }
  const a = document.createElement('a');
  a.href = 'data:image/png;base64,' + screenshotB64;
  a.download = 'carla_' + Date.now() + '.png';
  a.click();
  toast('Downloading...', 'ok');
}

// ── Live Stream ────────────────────────────────────────────────
function startStream() {
  const img = document.getElementById('liveStream');
  img.src = '/video_feed?' + Date.now();
  img.style.display = 'block';
  img.onerror = () => { toast('Stream failed', 'err', 6000); stopStream(); };
  document.getElementById('liveStreamStatus').style.display = 'none';
  document.getElementById('streamBtn').style.display = 'none';
  document.getElementById('streamStopBtn').style.display = 'flex';
  toast('Live stream started', 'ok');
  addLog('Live stream started');
}

function stopStream() {
  const img = document.getElementById('liveStream');
  img.src = ''; img.style.display = 'none'; img.onerror = null;
  document.getElementById('liveStreamStatus').style.display = 'block';
  document.getElementById('streamBtn').style.display = 'flex';
  document.getElementById('streamStopBtn').style.display = 'none';
  toast('Stream stopped');
  addLog('Live stream stopped');
}

// ── Lane Info ──────────────────────────────────────────────────
async function fetchLaneInfo() {
  const res = await api('/lane/current', 'GET');
  if (!res.success) {
    document.getElementById('laneRoad').innerText = '--';
    document.getElementById('laneSection').innerText = '--';
    document.getElementById('laneJunc').innerText = '--';
    document.getElementById('laneS').innerText = '--';
    document.getElementById('laneSchematic').innerHTML = `<div style="color:var(--c-red);font-size:0.7rem;text-align:center;">${res.error}</div>`;
    document.getElementById('laneVehicleList').innerHTML = '';
    return;
  }

  document.getElementById('laneRoad').innerText = res.road_id;
  document.getElementById('laneSection').innerText = res.section_id;
  document.getElementById('laneJunc').innerText = res.is_junction ? `YES (${res.junction_id})` : 'NO';
  document.getElementById('laneS').innerText = res.s.toFixed(1) + 'm';

  // Render Lane Schematic
  const schematic = document.getElementById('laneSchematic');
  schematic.innerHTML = res.lanes.map(l => {
    const isCurrent = l.is_current;
    const type = l.type.toUpperCase();

    let bg = 'rgba(255,255,255,0.02)';
    let accent = 'var(--c-dim)';

    if (type === 'DRIVING') {
      accent = isCurrent ? 'var(--c-accent)' : 'var(--c-dim)';
      bg = isCurrent ? 'rgba(0, 212, 245, 0.12)' : 'rgba(255,255,255,0.05)';
    } else if (type === 'SIDEWALK') {
      accent = 'var(--c-muted)';
      bg = 'rgba(29, 37, 53, 0.6)';
    } else if (type === 'SHOULDER' || type === 'PARKING') {
      accent = 'var(--c-muted)';
      bg = 'rgba(29, 37, 53, 0.3)';
    }

    return `
      <div style="display:flex; align-items:center; gap:8px; padding:4px 10px; background:${bg}; border:1px solid ${isCurrent ? 'var(--c-accent)' : 'rgba(255,255,255,0.05)'}; position:relative; overflow:hidden;">
        ${isCurrent ? '<div style="position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--c-accent);"></div>' : ''}
        <span style="font-family:'Share Tech Mono'; font-size:0.75rem; color:${accent}; width:35px; text-align:right;">${l.lane_id}</span>
        <div style="flex:1; display:flex; flex-direction:column; gap:1px;">
            <div style="font-size:0.55rem; color:${accent}; font-weight:700; letter-spacing:0.05em;">${type}</div>
            <div style="height:2px; background:${accent}; opacity:0.15;"></div>
        </div>
        <span style="font-family:'Share Tech Mono'; font-size:0.6rem; color:var(--c-muted); opacity:0.8;">${l.width.toFixed(1)}m</span>
      </div>
    `;
  }).join('');

  const list = document.getElementById('laneVehicleList');
  if (res.vehicles.length === 0) {
    list.innerHTML = '<div style="color:var(--c-dim);font-size:0.8rem;text-align:center;">Road empty</div>';
  } else {
    list.innerHTML = res.vehicles.map(v => `
      <div class="actor-card" style="margin-bottom:6px; padding:6px 10px; font-size:0.85rem; background:rgba(255,255,255,0.03); border-radius:2px; border:1px solid var(--border);">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div style="display:grid;">
            <div style="display:flex; gap:6px; align-items:center;">
              <span style="color:var(--c-cyan); font-weight:700; font-family:'Share Tech Mono';">#${v.id}</span>
              <span style="background:var(--border-hi); color:var(--c-bright); font-size:0.6rem; padding:1px 4px; font-family:'Share Tech Mono';">LANE ${v.lane_id}</span>
            </div>
            <span style="color:var(--c-dim); font-size:0.7rem; text-transform:uppercase;">${v.type_id.split('.').pop().replace(/_/g, ' ')}</span>
          </div>
          <div style="text-align:right;">
            <span style="color:var(--c-green); font-weight:600;">${v.speed} <small>km/h</small></span>
          </div>
        </div>
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:4px; margin-top:6px;">
          <button class="btn btn-primary btn-xs" style="padding:2px; font-size:0.65rem;" onclick="changeLane(${v.id}, 'left')">← LNE</button>
          <button class="btn btn-primary btn-xs" style="padding:2px; font-size:0.65rem;" onclick="changeLane(${v.id}, 'right')">RGT →</button>
          <button class="btn btn-danger btn-xs" style="padding:2px; font-size:0.65rem;" onclick="destroyActor(${v.id})">DESTROY</button>
        </div>
      </div>
    `).join('');
  }
}

async function changeLane(actorId, direction) {
  const res = await api('/lane/change_lane', 'POST', { id: actorId, direction: direction });
  if (res.success) {
    toast(`Commanded #${actorId} ${direction}`, 'ok');
    setTimeout(fetchLaneInfo, 500);
  } else {
    toast(res.error, 'err');
  }
}

async function spawnInLane(isEmergency = false) {
  toast('Spawning in lane...', 'ok');
  const res = await api('/lane/spawn', 'POST', {
    blueprint: isEmergency ? '' : 'vehicle.tesla.model3',
    emergency: isEmergency,
    autopilot: true,
    distance: 8.0
  });
  if (res.success) {
    toast(`Spawned ${res.type} (#${res.id})`, 'ok');
    fetchLaneInfo();
  } else {
    toast(res.error, 'err');
  }
}

async function clearLaneVehicles() {
  if (!confirm('Destroy ALL vehicles in this lane?')) return;
  const res = await api('/lane/clear', 'POST');
  if (res.success) {
    toast(`Cleared ${res.cleared} vehicles`, 'ok');
    fetchLaneInfo();
  } else {
    toast(res.error, 'err');
  }
}

// ── Camera Manager ─────────────────────────────────────────────
async function attachCamera(id) {
  toast('Attaching camera to actor ' + id + '...');
  const res = await api('/camera/attach', 'POST', { parent_id: id });
  if (res.success) {
    toast(`Camera ${res.actor_id} attached! Loading preview...`, 'ok');
    addLog(`Camera ID:${res.actor_id} attached to parent ID:${id}`, 'ok');

    // Auto-select this camera for stream
    await api('/camera/set_stream_source', 'POST', { id: res.actor_id });

    // Refresh the camera list and open preview window if not open
    refreshCameras();
    openWin('win-cameras');
  } else {
    toast('Attach failed: ' + res.error, 'err');
  }
}

async function refreshCameras() {
  const container = document.getElementById('cameraListContainer');
  if (!container) return;
  const data = await api('/camera/list');
  if (!data.success) {
    container.innerHTML = `<div style="color:var(--c-red); font-size:0.7rem; padding:10px;">Error: ${data.error}</div>`;
    return;
  }
  if (data.cameras.length === 0) {
    container.innerHTML = `<div style="color:var(--c-dim); font-size:0.7rem; padding:10px; font-family:'Share Tech Mono'; text-align:center;">NO SENSORS FOUND</div>`;
    return;
  }

  container.innerHTML = data.cameras.map(c => {
    const isStreaming = c.is_streaming;
    const typeShort = c.type.split('.').pop().toUpperCase();
    return `
      <div class="actor-card cam-card ${isStreaming ? 'selected' : ''}" data-id="${c.id}" onclick='selectCamera(${JSON.stringify(c).replace(/'/g, "\\'")})' 
           style="cursor:pointer; display:flex; flex-direction:column; gap:2px;">
        <div style="display:flex; justify-content:space-between; align-items:center; pointer-events:none;">
          <span style="font-size:0.75rem; color:var(--c-bright);">#${c.id}</span>
          <span class="badge ${isStreaming ? 'badge-v' : 'badge-o'}">${typeShort}</span>
        </div>
      </div>
    `;
  }).join('');

  // Auto-update inputs if camera is selected, window is active, and NOT focused
  const badgeId = document.getElementById('camBadgeId');
  const selectedId = badgeId ? badgeId.textContent : null;
  const followCheck = document.getElementById('camFollowSync');
  const isSyncEnabled = followCheck ? followCheck.checked : true;

  if (selectedId && selectedId !== '--' && isSyncEnabled) {
    const cam = data.cameras.find(c => c.id == selectedId);
    if (cam) {
      // If ANY of the inputs is focused, don't update ANY of them to avoid jumping
      const inputs = ['camX', 'camY', 'camZ', 'camPitch', 'camYaw', 'camRoll'];
      const hasFocus = inputs.some(id => document.activeElement === document.getElementById(id));

      if (!hasFocus) {
        updateInputIfNoFocus('camX', cam.x.toFixed(2));
        updateInputIfNoFocus('camY', cam.y.toFixed(2));
        updateInputIfNoFocus('camZ', cam.z.toFixed(2));
        updateInputIfNoFocus('camPitch', Math.round(cam.pitch));
        updateInputIfNoFocus('camYaw', Math.round(cam.yaw));
        updateInputIfNoFocus('camRoll', Math.round(cam.roll));
      }
    }
  }
}

function updateInputIfNoFocus(id, val) {
  const el = document.getElementById(id);
  if (el && document.activeElement !== el) {
    el.value = val;
  }
}

async function selectCamera(c) {
  const panel = document.getElementById('camControlPanel');
  panel.style.opacity = '1';
  panel.style.pointerEvents = 'all';

  document.getElementById('camX').value = c.x.toFixed(2);
  document.getElementById('camY').value = c.y.toFixed(2);
  document.getElementById('camZ').value = c.z.toFixed(2);
  document.getElementById('camPitch').value = Math.round(c.pitch);
  document.getElementById('camYaw').value = Math.round(c.yaw);
  document.getElementById('camRoll').value = Math.round(c.roll);

  const badgeId = document.getElementById('camBadgeId');
  const badge = document.getElementById('camBadge');
  if (badgeId) badgeId.textContent = c.id;
  if (badge) badge.style.display = 'flex';

  const dBtn = document.getElementById('camDestroyBtn');
  if (dBtn) {
    dBtn.onclick = async () => {
      if (!confirm(`Permanently destroy sensor #${c.id}?`)) return;
      toast(`Destroying sensor #${c.id}...`);
      const res = await api('/camera/delete', 'POST', { id: c.id });
      if (res.success) {
        toast(`Sensor #${c.id} destroyed`, 'ok');
        refreshCameras();
        stopCamPreview();
        panel.style.opacity = '0.4';
        panel.style.pointerEvents = 'none';
        if (badgeId) badgeId.textContent = '--';
        if (badge) badge.style.display = 'none';
      } else {
        toast(res.error, 'err');
      }
    };
  }

  await setCameraAsSource(c.id);
  startCamPreview(c.id);

  document.querySelectorAll('.cam-card').forEach(card => {
    card.classList.toggle('selected', card.getAttribute('data-id') == c.id);
  });
}

function startCamPreview(id) {
  const img = document.getElementById('camPreviewImg');
  const ovr = document.getElementById('camPreviewOverlay');
  const ph = document.getElementById('camPreviewPlaceholder');
  if (!img) return;
  // MJPEG stream – set once, browser streams automatically
  img.src = id ? `/video_feed?id=${id}` : `/video_feed`;
  img.style.display = 'block';
  if (ovr) ovr.style.display = 'block';
  if (ph) ph.style.display = 'none';
}


function stopCamPreview() {
  const img = document.getElementById('camPreviewImg');
  const ovr = document.getElementById('camPreviewOverlay');
  const ph = document.getElementById('camPreviewPlaceholder');
  if (!img) return;
  img.src = '';
  img.style.display = 'none';
  if (ovr) ovr.style.display = 'none';
  if (ph) ph.style.display = 'flex';
}

function copyCamLink() {
  const idEl = document.getElementById('camBadgeId');
  const id = idEl ? idEl.textContent : null;
  const baseUrl = window.location.origin + '/video_feed';
  const url = (id && id !== '--') ? `${baseUrl}?id=${id}` : baseUrl;

  navigator.clipboard.writeText(url).then(() => {
    toast('Live link copied to clipboard!', 'ok');
  }).catch(err => {
    toast('Failed to copy link', 'err');
  });
}

async function setCameraAsSource(id) {
  const res = await api('/camera/set_stream_source', 'POST', { id });
  if (!res.success) toast(res.error, 'err');
}

async function updateCameraPosition() {
  const idEl = document.getElementById('camBadgeId');
  const id = idEl ? idEl.textContent : null;
  if (!id || id === '--') return;
  const d = {
    id: parseInt(id),
    x: parseFloat(document.getElementById('camX').value),
    y: parseFloat(document.getElementById('camY').value),
    z: parseFloat(document.getElementById('camZ').value),
    pitch: parseFloat(document.getElementById('camPitch').value),
    yaw: parseFloat(document.getElementById('camYaw').value),
    roll: parseFloat(document.getElementById('camRoll').value),
  };
  const res = await api('/camera/update', 'POST', d);
  if (res.success) {
    toast(`Cam #${id} updated`, 'ok');
    refreshCameras();
  } else toast(res.error, 'err');
}

async function spawnType(type) {
  const bps = { 'rgb': 'sensor.camera.rgb', 'depth': 'sensor.camera.depth', 'sem': 'sensor.camera.semantic_segmentation', 'dvs': 'sensor.camera.dvs' };
  const d = { blueprint: bps[type] || bps['rgb'], width: 640, height: 360, fov: 90 };
  const res = await api('/camera/spawn', 'POST', d);
  if (res.success) {
    toast(`Spawned ${type.toUpperCase()} (#${res.actor_id})`, 'ok');
    refreshCameras();
  } else toast(res.error, 'err');
}
function camSetToSpectator() {
  document.getElementById('camX').value = document.getElementById('sX').textContent;
  document.getElementById('camY').value = document.getElementById('sY').textContent;
  document.getElementById('camZ').value = document.getElementById('sZ').textContent;
  document.getElementById('camPitch').value = document.getElementById('sPitch').textContent;
  document.getElementById('camYaw').value = document.getElementById('sYaw').textContent;
  document.getElementById('camRoll').value = document.getElementById('sRoll').textContent;
  toast('Matched spectator', 'info');
}

function camLoadPosition(name) {
  if (!name) return;
  const loc = serverLocations[name];
  if (!loc) { toast('Location not found: ' + name, 'err'); return; }
  document.getElementById('camX').value = parseFloat(loc.x).toFixed(2);
  document.getElementById('camY').value = parseFloat(loc.y).toFixed(2);
  document.getElementById('camZ').value = parseFloat(loc.z).toFixed(2);
  document.getElementById('camPitch').value = Math.round(parseFloat(loc.pitch));
  document.getElementById('camYaw').value = Math.round(parseFloat(loc.yaw));
  document.getElementById('camRoll').value = Math.round(parseFloat(loc.roll));
  toast('Preset loaded: ' + name, 'info');
  updateCameraPosition();
}

async function camSavePosition() {
  const idEl = document.getElementById('camBadgeId');
  const id = idEl ? idEl.textContent : 'Unknown';
  const name = prompt('Enter name for this location:', `Cam #${id} Loc ` + new Date().toLocaleTimeString());
  if (!name) return;
  const payload = {
    name,
    x: document.getElementById('camX').value,
    y: document.getElementById('camY').value,
    z: document.getElementById('camZ').value,
    pitch: document.getElementById('camPitch').value,
    yaw: document.getElementById('camYaw').value,
    roll: document.getElementById('camRoll').value,
  };
  toast(`Saving "${name}"...`);
  const res = await api('/history/location', 'POST', payload);
  if (res.success) {
    toast(`Saved: ${name}`, 'ok');
    initHistory();
  } else toast(res.error, 'err');
}

async function spawnNewCamera() {
  // Deprecated in favor of spawnType, but kept for compatibility if needed.
  spawnType('rgb');
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildWeatherSliders();
  initWindows();
  restoreState();
  initHistory();

  // Start polling to check if already connected on server
  startPolling();

  if (!state['win-connect'] || !state['win-connect'].open) {
    openWin('win-connect', true);
  }
});

window.addEventListener('resize', saveState);