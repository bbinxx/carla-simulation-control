// ═══════════════════════════════════════════════════════════════
//  spawn.js — spawn + destroy + TM fix + lane operations
// ═══════════════════════════════════════════════════════════════

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

async function loadEmergencyBlueprints() {
  const data = await api('/blueprints/emergency');
  const sel  = document.getElementById('emergencyBp');
  if (data.success && data.blueprints.length > 0) {
    sel.innerHTML = data.blueprints.map(b => `<option value="${b}">${b}</option>`).join('');
    addLog(`Emergency blueprints: ${data.blueprints.length}`);
  } else {
    sel.innerHTML = '<option value="">None found — using random</option>';
    addLog('No emergency vehicle blueprints found', 'warn');
  }
}

// ── Spawn ──────────────────────────────────────────────────────

async function spawnVehicle() {
  const bp = document.getElementById('vehicleBp').value;
  if (!bp) { toast('Select a blueprint', 'err'); return; }
  toast('Spawning ' + bp + '...');
  const data = await api('/spawn/vehicle', 'POST', {
    blueprint: bp,
    color:     document.getElementById('colorText').value,
    autopilot: document.getElementById('autopilotCb').checked,
  });
  if (data.success) {
    toast(`Spawned ${bp} (ID:${data.actor_id})`, 'ok');
    addLog(`Vehicle spawned — ID:${data.actor_id}`, 'ok');
  } else {
    toast('Spawn failed: ' + data.error, 'err', 5000);
  }
}

async function spawnNPC() {
  const count = parseInt(document.getElementById('npcCount').value);
  toast(`Spawning ${count} NPCs...`);
  const data = await api('/spawn/npc', 'POST', { count });
  if (data.success) {
    toast(`Spawned ${data.spawned} NPC vehicle(s)`, 'ok');
    addLog(`NPCs spawned: ${data.spawned}/${count}`, 'ok');
  } else {
    toast('NPC spawn failed: ' + data.error, 'err', 5000);
  }
}

async function spawnEmergency() {
  const bp        = document.getElementById('emergencyBp').value;
  const autopilot = document.getElementById('emergencyAutopilot').checked;
  toast('Spawning ' + (bp || 'random emergency') + '...');
  const data = await api('/spawn/emergency', 'POST', { blueprint: bp, autopilot });
  if (data.success) {
    toast(`Emergency spawned: ${data.blueprint} (ID:${data.actor_id})`, 'ok');
    addLog(`Emergency ID:${data.actor_id} — ${data.blueprint}`, 'ok');
  } else {
    toast('Emergency spawn failed: ' + data.error, 'err', 5000);
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

async function spawnAny() {
  const bp   = document.getElementById('anyBp').value;
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

// ── Lane ───────────────────────────────────────────────────────

let lanePollInterval = null;

async function fetchLaneInfo() {
  const res = await api('/lane/current', 'GET');
  if (!res.success) {
    document.getElementById('laneRoad').innerText    = '--';
    document.getElementById('laneSection').innerText = '--';
    document.getElementById('laneJunc').innerText    = '--';
    document.getElementById('laneS').innerText       = '--';
    document.getElementById('laneSchematic').innerHTML  = `<div style="color:var(--c-red);font-size:0.7rem;text-align:center;">${res.error}</div>`;
    document.getElementById('laneVehicleList').innerHTML = '';
    return;
  }

  document.getElementById('laneRoad').innerText    = res.road_id;
  document.getElementById('laneSection').innerText = res.section_id;
  document.getElementById('laneJunc').innerText    = res.is_junction ? `YES (${res.junction_id})` : 'NO';
  document.getElementById('laneS').innerText       = res.s.toFixed(1) + 'm';

  const schematic = document.getElementById('laneSchematic');
  schematic.innerHTML = res.lanes.map(l => {
    const isCurrent = l.is_current;
    const type      = l.type.toUpperCase();
    let bg     = 'rgba(255,255,255,0.02)';
    let accent = 'var(--c-dim)';
    if (type === 'DRIVING') {
      accent = isCurrent ? 'var(--c-accent)' : 'var(--c-dim)';
      bg     = isCurrent ? 'rgba(0, 212, 245, 0.12)' : 'rgba(255,255,255,0.05)';
    } else if (type === 'SIDEWALK') {
      accent = 'var(--c-muted)'; bg = 'rgba(29, 37, 53, 0.6)';
    } else if (type === 'SHOULDER' || type === 'PARKING') {
      accent = 'var(--c-muted)'; bg = 'rgba(29, 37, 53, 0.3)';
    }
    return `
      <div style="display:flex; align-items:center; gap:8px; padding:4px 10px; background:${bg}; border:1px solid ${isCurrent ? 'var(--c-accent)' : 'rgba(255,255,255,0.05)'}; position:relative; overflow:hidden;">
        ${isCurrent ? '<div style="position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--c-accent);"></div>' : ''}
        <span style="font-family:\'Share Tech Mono\'; font-size:0.75rem; color:${accent}; width:35px; text-align:right;">${l.lane_id}</span>
        <div style="flex:1; display:flex; flex-direction:column; gap:1px;">
          <div style="font-size:0.55rem; color:${accent}; font-weight:700; letter-spacing:0.05em;">${type}</div>
          <div style="height:2px; background:${accent}; opacity:0.15;"></div>
        </div>
        <span style="font-family:\'Share Tech Mono\'; font-size:0.6rem; color:var(--c-muted); opacity:0.8;">${l.width.toFixed(1)}m</span>
      </div>`;
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
      </div>`).join('');
  }
}

async function changeLane(actorId, direction) {
  const res = await api('/lane/change_lane', 'POST', { id: actorId, direction });
  if (res.success) { toast(`Commanded #${actorId} ${direction}`, 'ok'); setTimeout(fetchLaneInfo, 500); }
  else toast(res.error, 'err');
}

async function spawnInLane(isEmergency = false) {
  toast('Spawning in lane...', 'ok');
  const res = await api('/lane/spawn', 'POST', {
    blueprint: isEmergency ? '' : 'vehicle.tesla.model3',
    emergency: isEmergency,
    autopilot: true,
    distance: 8.0,
  });
  if (res.success) { toast(`Spawned ${res.type} (#${res.id})`, 'ok'); fetchLaneInfo(); }
  else toast(res.error, 'err');
}

async function clearLaneVehicles() {
  if (!confirm('Destroy ALL vehicles in this lane?')) return;
  const res = await api('/lane/clear', 'POST');
  if (res.success) { toast(`Cleared ${res.cleared} vehicles`, 'ok'); fetchLaneInfo(); }
  else toast(res.error, 'err');
}
