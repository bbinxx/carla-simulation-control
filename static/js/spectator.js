// ═══════════════════════════════════════════════════════════════
//  spectator.js — spectator get/set/saved locations
// ═══════════════════════════════════════════════════════════════

let serverLocations = {};
let currentSpectator = null;
let joystickActive = false;
let joystickVector = { x: 0, y: 0 };
let joystickInterval = null;
const joystickMaxRadius = 44;

let _lastDisp = { x: 0, y: 0, z: 0, p: 0, ya: 0, r: 0 };

function updateSpectatorDisplay(s) {
  currentSpectator = { ...s };
  
  // Throttle DOM updates: only update if delta is significant
  const dx = Math.abs(s.x - _lastDisp.x);
  const dy = Math.abs(s.y - _lastDisp.y);
  const dz = Math.abs(s.z - _lastDisp.z);
  const dp = Math.abs(s.pitch - _lastDisp.p);
  const dya = Math.abs(s.yaw - _lastDisp.ya);
  const dr = Math.abs(s.roll - _lastDisp.r);

  if (dx > 0.01 || dy > 0.01 || dz > 0.01 || dp > 0.1 || dya > 0.1 || dr > 0.1) {
      document.getElementById('sX').textContent     = Number(s.x).toFixed(2);
      document.getElementById('sY').textContent     = Number(s.y).toFixed(2);
      document.getElementById('sZ').textContent     = Number(s.z).toFixed(2);
      document.getElementById('sPitch').textContent = Math.round(s.pitch);
      document.getElementById('sYaw').textContent   = Math.round(s.yaw);
      document.getElementById('sRoll').textContent  = Math.round(s.roll);
      
      _lastDisp = { x: s.x, y: s.y, z: s.z, p: s.pitch, ya: s.yaw, r: s.roll };
  }
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
    x:     parseFloat(document.getElementById('specX').value),
    y:     parseFloat(document.getElementById('specY').value),
    z:     parseFloat(document.getElementById('specZ').value),
    pitch: parseFloat(document.getElementById('specPitch').value),
    yaw:   parseFloat(document.getElementById('specYaw').value),
    roll:  parseFloat(document.getElementById('specRoll').value),
  };
  toast('Moving camera...');
  const data = await api('/spectator/set', 'POST', d);
  if (data.success) {
    currentSpectator = d;
    syncSpectatorInputs(d);
    toast(`Camera moved to (${d.x}, ${d.y}, ${d.z})`, 'ok');
    addLog(`Spectator -> (${d.x}, ${d.y}, ${d.z})`, 'ok');
  } else {
    toast('Move failed: ' + data.error, 'err');
  }
}

async function moveSpectatorRelative(delta = {}) {
  let data = currentSpectator;
  if (!data) {
    const res = await api('/spectator/get');
    if (!res.success) {
      toast('Unable to read spectator position: ' + res.error, 'err');
      return;
    }
    data = res;
  }

  const next = {
    x:     Number(data.x) + (delta.dx || 0),
    y:     Number(data.y) + (delta.dy || 0),
    z:     Number(data.z) + (delta.dz || 0),
    pitch: Number(data.pitch) + (delta.dp || 0),
    yaw:   Number(data.yaw) + (delta.dyaw || 0),
    roll:  Number(data.roll) + (delta.dr || 0),
  };

  const res = await api('/spectator/set', 'POST', next);
  if (res.success) {
    currentSpectator = next;
    updateSpectatorDisplay(next);
    syncSpectatorInputs(next);
  } else {
    toast('Spectator move failed: ' + res.error, 'err');
  }
}

function syncSpectatorInputs(s) {
  if (!s) return;
  const mapping = {
    specX: s.x,
    specY: s.y,
    specZ: s.z,
    specPitch: s.pitch,
    specYaw: s.yaw,
    specRoll: s.roll,
  };

  Object.entries(mapping).forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (el) el.value = Number(value).toFixed(2);
  });
}

function spectatorKeyboardControl(event) {
  if (!event.key || ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target?.tagName)) {
    return;
  }

  const key = event.key.toLowerCase();
  const isPageUp = event.key === 'PageUp';
  const isPageDown = event.key === 'PageDown';
  const step = event.shiftKey ? 5 : 2;
  const zStep = event.shiftKey ? 2 : 1;
  const rotStep = event.shiftKey ? 15 : 10;

  let delta = null;

  switch (key) {
    case 'arrowup':
    case 'w':
      delta = { dy: step };
      break;
    case 'arrowdown':
    case 's':
      delta = { dy: -step };
      break;
    case 'arrowleft':
    case 'a':
      delta = { dx: -step };
      break;
    case 'arrowright':
    case 'd':
      delta = { dx: step };
      break;
    case 'q':
      delta = { dyaw: -rotStep };
      break;
    case 'e':
      delta = { dyaw: rotStep };
      break;
    case 'i':
      delta = { dp: -rotStep };
      break;
    case 'k':
      delta = { dp: rotStep };
      break;
    case 'r':
      fetchSpectator();
      return;
    default:
      break;
  }

  if (isPageUp) {
    delta = { dz: zStep };
  }
  if (isPageDown) {
    delta = { dz: -zStep };
  }

  if (delta) {
    event.preventDefault();
    moveSpectatorRelative(delta);
  }
}

function initSpectatorJoystick() {
  const base = document.getElementById('joystickBase');
  const thumb = document.getElementById('joystickThumb');
  const status = document.getElementById('joystickState');
  if (!base || !thumb || !status) return;

  const updateStatus = () => {
    const x = joystickVector.x.toFixed(2);
    const y = joystickVector.y.toFixed(2);
    status.textContent = joystickActive ? `Pan ${x}, ${y}` : 'Drag to pan';
  };

  const resetJoystick = () => {
    joystickActive = false;
    joystickVector = { x: 0, y: 0 };
    thumb.style.transform = 'translate(-50%, -50%)';
    if (status) status.textContent = 'Drag to pan';
    if (joystickInterval) {
      clearInterval(joystickInterval);
      joystickInterval = null;
    }
  };

  const applyJoystickMove = () => {
    if (!joystickActive) return;
    const magnitude = Math.hypot(joystickVector.x, joystickVector.y);
    if (magnitude < 0.15) return;
    const scale = 2.5 * magnitude;
    moveSpectatorRelative({
      dx: joystickVector.x * scale,
      dy: -joystickVector.y * scale,
    });
  };

  const handlePointer = event => {
    if (!joystickActive && event.type !== 'pointerdown') return;
    if (event.type === 'pointerdown') {
      event.preventDefault();
      base.setPointerCapture(event.pointerId);
      joystickActive = true;
      updateStatus();
      joystickInterval = setInterval(applyJoystickMove, 120);
    }

    if (event.type === 'pointermove' && joystickActive) {
      const rect = base.getBoundingClientRect();
      const x = event.clientX - (rect.left + rect.width / 2);
      const y = event.clientY - (rect.top + rect.height / 2);
      const clampedX = Math.max(-joystickMaxRadius, Math.min(joystickMaxRadius, x));
      const clampedY = Math.max(-joystickMaxRadius, Math.min(joystickMaxRadius, y));
      joystickVector.x = clampedX / joystickMaxRadius;
      joystickVector.y = clampedY / joystickMaxRadius;
      thumb.style.transform = `translate(${clampedX}px, ${clampedY}px)`;
      updateStatus();
    }

    if (event.type === 'pointerup' || event.type === 'pointercancel' || event.type === 'pointerleave') {
      resetJoystick();
    }
  };

  base.addEventListener('pointerdown', handlePointer);
  base.addEventListener('pointermove', handlePointer);
  base.addEventListener('pointerup', handlePointer);
  base.addEventListener('pointercancel', handlePointer);
  base.addEventListener('pointerleave', handlePointer);
}

document.addEventListener('keydown', spectatorKeyboardControl);
initSpectatorJoystick();

// ── History / saved locations ──────────────────────────────────

async function initHistory() {
  try {
    const res = await api('/history', 'GET');
    if (res.success) {
      const hosts = res.hosts || [];
      const dl    = document.getElementById('hostHistory');
      if (dl) dl.innerHTML = hosts.map(h => `<option value="${h.host}">`).join('');
      if (res.last_connection) {
        const hi = document.getElementById('hostInput');
        const pi = document.getElementById('portInput');
        if (hi) hi.value = res.last_connection.host;
        if (pi) pi.value = res.last_connection.port;
      }
      serverLocations = res.locations || {};
      renderSavedLocations();
      if (res.camera_setups) renderSavedSetups(res.camera_setups);
      addLog(`History loaded — ${hosts.length} host(s), ${Object.keys(serverLocations).length} location(s)`, 'info');
    } else {
      addLog('Failed to load history: ' + (res.error || 'unknown'), 'warn');
    }
  } catch (e) {
    addLog('initHistory exception: ' + e.message, 'err');
  }
}

function renderSavedLocations() {
  const sel    = document.getElementById('savedLocations');
  const camSel = document.getElementById('camSavedLocations');
  const optStr = '<option value="">-- Select --</option>' +
    Object.keys(serverLocations).map(k => `<option value="${k}">${k}</option>`).join('');
  if (sel)    sel.innerHTML    = optStr;
  if (camSel) camSel.innerHTML = optStr;
}

function renderSavedSetups(setups) {
  const sel = document.getElementById('camSavedSetups');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Load Camera Setup --</option>' +
    setups.map(s => `<option value="${s.name}">${s.name} (${s.config.length} cams)</option>`).join('');
}

async function saveSpectatorPosition() {
  const name = document.getElementById('locName').value.trim() ||
               'Location ' + new Date().toLocaleTimeString();
  const payload = {
    name,
    x:     document.getElementById('sX').textContent,
    y:     document.getElementById('sY').textContent,
    z:     document.getElementById('sZ').textContent,
    pitch: document.getElementById('sPitch').textContent,
    yaw:   document.getElementById('sYaw').textContent,
    roll:  document.getElementById('sRoll').textContent,
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
  document.getElementById('specX').value     = loc.x;
  document.getElementById('specY').value     = loc.y;
  document.getElementById('specZ').value     = loc.z;
  document.getElementById('specPitch').value = loc.pitch;
  document.getElementById('specYaw').value   = loc.yaw;
  document.getElementById('specRoll').value  = loc.roll;
  toast('Loaded: ' + name, 'ok');
  addLog('Location loaded: ' + name, 'ok');
  moveSpectator();
  document.getElementById('savedLocations').value = '';
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
