// ═══════════════════════════════════════════════════════════════
//  CARLA CONTROL PANEL — script.js
// ═══════════════════════════════════════════════════════════════

// ── App State ──────────────────────────────────────────────────
let serverLocations = {};
let pollInterval = null;
let weatherValues = {};
let screenshotB64 = null;
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
  if (!skipSave) saveState();
}

function closeWin(id) {
  const w = document.getElementById(id);
  if (!w) return;
  w.classList.remove('open');
  w.style.display = 'none';
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
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Select --</option>' +
    Object.keys(serverLocations).map(k => `<option value="${k}">${k}</option>`).join('');
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
    setConnected(false);
    clearInterval(pollInterval);
    toast('Lost connection to CARLA', 'err');
    addLog('Connection lost', 'err');
    return;
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
        <td><button class="btn btn-danger btn-sm" onclick="destroyActor(${a.id})">X</button></td>
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
  const atSpectator = document.getElementById('emergencyAtSpectator').checked;
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
    at_spectator: document.getElementById('atSpectatorCb').checked,
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
  const radius = parseFloat(document.getElementById('npcRadius').value);
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

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildWeatherSliders();
  initWindows();
  restoreState();
  initHistory();

  // default open connect window if no saved state
  const state = loadState();
  if (!state['win-connect'] || !state['win-connect'].open) {
    openWin('win-connect', true);
  }
});

window.addEventListener('resize', saveState);