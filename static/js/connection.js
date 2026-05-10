// ═══════════════════════════════════════════════════════════════
//  connection.js — connect/disconnect/status polling
// ═══════════════════════════════════════════════════════════════

let pollInterval    = null;
let _actorsTabOpen  = false;   // true when the Actors tab is visible
let _trafficTabOpen = false;   // true when the Traffic tab is visible

// ── Socket.IO Status Sync ──────────────────────────────────────
socket.on('connect', () => {
  console.log('Socket.IO connected');
  // Join spectator room for high-freq updates
  socket.emit('join_room', { room: 'spectator' });
});

socket.on('status_update', (data) => {
    if (!data.connected) {
      if (document.getElementById('connectBtn').style.display === 'none') {
        setConnected(false);
        toast('Lost connection to CARLA (Socket)', 'err');
        addLog('Connection lost (Socket reported)', 'err');
      }
      return;
    }

    // Sync UI if server reports connected but UI shows disconnected
    if (document.getElementById('connectBtn').style.display !== 'none') {
      setConnected(true, data);
    }

    // Update global stats
    document.getElementById('infoMap').textContent      = data.map;
    document.getElementById('infoActors').textContent   = data.actor_count;
    document.getElementById('statActors').textContent   = data.actor_count;
    document.getElementById('statVehicles').textContent = data.vehicle_count;
    document.getElementById('statWalkers').textContent  = data.walker_count;
    document.getElementById('statSensors').textContent  = data.sensor_count;

    if (data.spectator) updateSpectatorDisplay(data.spectator);
    if (data.weather && typeof buildWeatherSliders === 'function') {
      buildWeatherSliders(data.weather);
    }

    // Update Health Stats
    if (data.health) {
        const cpu = document.getElementById('statCPU');
        const ram = document.getElementById('statRAM');
        if (cpu) {
            cpu.textContent = `${data.health.cpu}%`;
            if (data.health.cpu > 80) cpu.style.color = 'var(--c-red)';
            else if (data.health.cpu > 50) cpu.style.color = 'var(--c-yellow)';
            else cpu.style.color = 'var(--c-accent)';
        }
        if (ram) ram.textContent = `${data.health.ram}MB`;
    }

    // Heavy actor table — only when the actors tab is open
    if (_actorsTabOpen) {
      api('/api/status/actors').then(full => {
        renderActorTable((full && full.actors) || []);
      });
    }

    // Traffic light table — only when the traffic tab is open
    if (_trafficTabOpen && data.traffic_lights) {
      renderTrafficLights(data.traffic_lights);
    }
  });

  // High-frequency spectator updates (~10Hz)
  socket.on('spectator_update', (data) => {
    if (typeof updateSpectatorDisplay === 'function') {
        updateSpectatorDisplay(data);
    }
  });

// ── Connected state UI ─────────────────────────────────────────
function setConnected(state, data = {}) {
  const dot      = document.getElementById('statusDot');
  const connDot  = document.getElementById('connDot');
  const wbStatus = document.getElementById('wb-status');
  const stText   = document.getElementById('statusText');

  dot.className      = 'sdot' + (state ? ' ok' : '');
  connDot.className  = 'sdot' + (state ? ' ok' : '');
  wbStatus.className = 'waybar-btn' + (state ? ' status-ok' : '');
  stText.style.color = state ? 'var(--c-green)' : 'var(--c-red)';
  stText.textContent = state ? `${data.host}:${data.port}` : 'DISCONNECTED';

  document.getElementById('connectBtn').style.display          = state ? 'none' : 'flex';
  document.getElementById('disconnectBtn').style.display       = state ? 'flex' : 'none';
  document.getElementById('disconnectedPlaceholder').style.display = state ? 'none' : 'flex';

  if (state) {
    document.getElementById('infoHost').textContent = data.host;
    document.getElementById('infoPort').textContent = data.port;
    document.getElementById('infoMap').textContent  = data.map || '—';
  } else {
    document.getElementById('infoMap').textContent  = '—';
  }
}

// ── Connect ─────────────────────────────────────────────────────
async function connect() {
  const host    = document.getElementById('hostInput').value.trim();
  const port    = document.getElementById('portInput').value;
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
    toast(`Connected — ${data.map}`, 'ok');
    addLog(`Connected. Map: ${data.map} | TM port: ${data.tm_port}`, 'ok');
    loadMaps(); loadBlueprints(); loadAllBlueprints(); loadEmergencyBlueprints();
    startPolling();
  } else {
    toast('Connection failed: ' + data.error, 'err', 5000);
    addLog('Connect error: ' + data.error, 'err');
  }
}

// ── Disconnect ─────────────────────────────────────────────────
async function disconnect() {
  clearInterval(pollInterval);
  stopStream();
  toast('Disconnecting...');
  const data = await api('/disconnect', 'POST');
  setConnected(false);
  toast(
    data.success ? 'Disconnected' : 'Disconnect error: ' + data.error,
    data.success ? 'info' : 'err'
  );
  addLog(
    data.success ? 'Disconnected' : 'Disconnect error: ' + data.error,
    data.success ? 'warn' : 'err'
  );
}

// ── Status polling ─────────────────────────────────────────────
// Fix 4: poll lightweight /api/status/summary every 5s;
//         load heavy /api/status/actors only when that tab is open.

function startPolling() {
  clearInterval(pollInterval);
  
  // If socket is connected, we don't need HTTP polling as server pushes status_update
  if (typeof socket !== 'undefined' && socket && socket.connected) {
    console.log('Socket active: HTTP polling disabled');
    return;
  }

  pollInterval = setInterval(refreshStatus, 5000);   // 5s fallback
  refreshStatus();
}

async function refreshStatus() {
  const data = await api('/api/status/summary');

  if (!data.connected) {
    // If we thought we were connected, flag the loss
    if (document.getElementById('connectBtn').style.display === 'none') {
      setConnected(false);
      clearInterval(pollInterval);
      toast('Lost connection to CARLA', 'err');
      addLog('Connection lost', 'err');
    }
    return;
  }

  // Sync UI if server reports connected but UI shows disconnected
  if (document.getElementById('connectBtn').style.display !== 'none') {
    setConnected(true, data);
  }

  document.getElementById('infoMap').textContent      = data.map;
  document.getElementById('infoActors').textContent   = data.actor_count;
  document.getElementById('statActors').textContent   = data.actor_count;
  document.getElementById('statVehicles').textContent = data.vehicle_count;
  document.getElementById('statWalkers').textContent  = data.walker_count;
  document.getElementById('statSensors').textContent  = data.sensor_count;

  if (data.spectator) updateSpectatorDisplay(data.spectator);
  if (data.weather)   buildWeatherSliders(data.weather);   // in weather.js

  // Sync control toggle
  const ctrlRes = await api('/control/status');
  if (ctrlRes.success) {
    const cb = document.getElementById('controlToggle');
    if (cb) cb.checked = ctrlRes.enabled;
  }

  // Heavy actor table — only when the actors tab is open
  if (_actorsTabOpen) {
    const full = await api('/api/status/actors');
    renderActorTable((full && full.actors) || []);
  }
}

// Called from main.js / tab switcher to notify this module
function setActorsTabOpen(isOpen) {
  _actorsTabOpen = isOpen;
  if (isOpen) {
    // Fetch immediately when tab opens rather than waiting for next poll
    api('/api/status/actors').then(r => renderActorTable((r && r.actors) || []));
  }
}

function setTrafficTabOpen(isOpen) {
  _trafficTabOpen = isOpen;
  if (isOpen) {
    // Fetch immediately when tab opens
    loadTrafficLights();
  }
}

function renderActorTable(actors) {
  const tbody = document.getElementById('actorTableBody');
  if (!tbody) return;
  if (!actors || actors.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="tbl-empty">No actors in world</td></tr>`;
    return;
  }
  tbody.innerHTML = actors.map(a => {
    let cls = 'badge-o';
    if (a.type.startsWith('vehicle'))      cls = 'badge-v';
    else if (a.type.startsWith('walker'))  cls = 'badge-w';
    else if (a.type.startsWith('sensor'))  cls = 'badge-s';
    else if (a.type.includes('traffic'))   cls = 'badge-t';
    return `<tr>
      <td>${a.id}</td>
      <td><span class="badge ${cls}">${a.type.split('.').slice(0, 2).join('.')}</span></td>
      <td>${a.x}</td><td>${a.y}</td><td>${a.z ?? '—'}</td>
      <td style="display:flex; gap:4px;">
        <button class="btn btn-cyan btn-xs" onclick="attachCamera(${a.id})" title="Attach Camera">CAM</button>
        <button class="btn btn-danger btn-xs" onclick="destroyActor(${a.id})">X</button>
      </td>
    </tr>`;
  }).join('');
}

// ── Debug BBoxes ───────────────────────────────────────────────
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

// ── Control toggle ─────────────────────────────────────────────
async function toggleControl(enabled) {
  const res = await api('/control/set', 'POST', { enabled });
  if (res.success) {
    toast(`Vehicle control ${enabled ? 'ENABLED' : 'DISABLED'}`, enabled ? 'ok' : 'warn');
    addLog(`System: Vehicle control ${enabled ? 'unlocked' : 'locked'}.`, enabled ? 'info' : 'warn');
  } else {
    toast('Error toggling control: ' + res.error, 'err');
  }
}

// ── Quick Actions ──────────────────────────────────────────────
async function spawnNPCBatch() {
  toast('Spawning NPC batch...');
  const res = await api('/spawn/npc', 'POST', { count: 10 });
  if (res.success) {
    toast(`Spawned ${res.spawned} NPCs`, 'ok');
    addLog(`Quick Action: Spawned 10 NPCs`, 'ok');
  } else {
    toast('Batch spawn failed: ' + res.error, 'err');
  }
}

async function emergencyStop() {
  toast('EMERGENCY STOP...', 'err');
  const res = await api('/control/set', 'POST', { enabled: false });
  if (res.success) {
    const cb = document.getElementById('controlToggle');
    if (cb) cb.checked = false;
    addLog('EMERGENCY STOP triggered by user', 'err');
    toast('CONTROL LOCKED', 'err');
  }
}

async function clearAllActors() {
  if (!confirm('Permanently destroy all spawned actors?')) return;
  toast('Clearing actors...');
  const res = await api('/destroy/all', 'POST');
  if (res.success) {
    toast(`Cleared ${res.destroyed} actors`, 'ok');
    addLog(`Quick Action: Cleared all actors (${res.destroyed} removed)`, 'warn');
  } else {
    toast('Clear failed: ' + res.error, 'err');
  }
}
