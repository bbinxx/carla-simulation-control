// ═══════════════════════════════════════════════════════════════
//  spectator.js — spectator get/set/saved locations
// ═══════════════════════════════════════════════════════════════

let serverLocations = {};

function updateSpectatorDisplay(s) {
  document.getElementById('sX').textContent     = s.x;
  document.getElementById('sY').textContent     = s.y;
  document.getElementById('sZ').textContent     = s.z;
  document.getElementById('sPitch').textContent = s.pitch;
  document.getElementById('sYaw').textContent   = s.yaw;
  document.getElementById('sRoll').textContent  = s.roll;
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
    toast(`Camera moved to (${d.x}, ${d.y}, ${d.z})`, 'ok');
    addLog(`Spectator -> (${d.x}, ${d.y}, ${d.z})`, 'ok');
  } else {
    toast('Move failed: ' + data.error, 'err');
  }
}

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
