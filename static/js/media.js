// ═══════════════════════════════════════════════════════════════
//  media.js — live stream + camera manager
// ═══════════════════════════════════════════════════════════════

let camPollInterval = null;

// Track blob URLs to prevent memory leaks
let liveStreamBlobUrl = null;
let previewStreamBlobUrl = null;

socket.on('connect', () => {
  console.log('Socket.IO connected');
});

socket.on('frame', (data) => {
  // data = { id: actor_id (int or null), data: ArrayBuffer }
  
  const liveImg = document.getElementById('liveStream');
  const previewImg = document.getElementById('camPreviewImg');
  const badgeId = document.getElementById('camBadgeId');
  
  // Update Live Stream (Spectator Cam)
  if (liveImg && liveImg.style.display !== 'none' && data.id === null) {
    const blob = new Blob([data.data], { type: 'image/jpeg' });
    if (liveStreamBlobUrl) URL.revokeObjectURL(liveStreamBlobUrl);
    liveStreamBlobUrl = URL.createObjectURL(blob);
    liveImg.src = liveStreamBlobUrl;
  }

  // Update Camera Preview (Specific Actor)
  if (previewImg && previewImg.style.display !== 'none' && badgeId) {
    const activeId = badgeId.textContent;
    // Check if the incoming frame matches the selected preview ID
    if ((activeId === '--' && data.id === null) || activeId == data.id) {
      const blob = new Blob([data.data], { type: 'image/jpeg' });
      if (previewStreamBlobUrl) URL.revokeObjectURL(previewStreamBlobUrl);
      previewStreamBlobUrl = URL.createObjectURL(blob);
      previewImg.src = previewStreamBlobUrl;
    }
  }
});

// ── Live Stream (Spectator) ────────────────────────────────────

async function startStream() {
  const img = document.getElementById('liveStream');
  img.style.display = 'block';
  
  // 1. Tell backend to ensure spectator camera exists
  toast('Initializing stream sensor...');
  const res = await api('/camera/set_stream_source', 'POST', { id: null });
  
  if (res.success) {
    // 2. Join the socket room
    socket.emit('join_camera', { id: null });
    
    document.getElementById('liveStreamStatus').style.display = 'none';
    document.getElementById('streamBtn').style.display        = 'none';
    document.getElementById('streamStopBtn').style.display    = 'flex';
    toast('Live stream started', 'ok');
    addLog('Live stream started (Spectator Follow)');
  } else {
    toast('Stream failed: ' + res.error, 'err');
  }
}

function stopStream() {
  const img = document.getElementById('liveStream');
  img.src = '';
  img.style.display = 'none';
  
  if (liveStreamBlobUrl) {
    URL.revokeObjectURL(liveStreamBlobUrl);
    liveStreamBlobUrl = null;
  }

  // Leave the selected camera room
  socket.emit('leave_camera', { id: null });

  document.getElementById('liveStreamStatus').style.display = 'block';
  document.getElementById('streamBtn').style.display        = 'flex';
  document.getElementById('streamStopBtn').style.display    = 'none';
  toast('Stream stopped');
  addLog('Live stream stopped');
}

async function setStreamResolution() {
  const parts = document.getElementById('liveStreamRes').value.split('x');
  const w     = parseInt(parts[0]);
  const h     = parseInt(parts[1]);
  const q     = parseInt(document.getElementById('liveStreamQual').value || 80);

  toast(`Setting resolution to ${w}x${h} (${q}%)...`);
  const res = await api('/camera/set_stream_resolution', 'POST', { width: w, height: h, quality: q });
  if (res.success) {
    toast(`Resolution updated`, 'ok');
    addLog(`Stream config: ${w}x${h} @ ${q}%`, 'ok');
  } else {
    toast(res.error, 'err');
  }
}

// ── Camera Manager ─────────────────────────────────────────────

function updateInputIfNoFocus(id, val) {
  const el = document.getElementById(id);
  if (el && document.activeElement !== el) el.value = val;
}

async function attachCamera(id) {
  toast('Attaching camera to actor ' + id + '...');
  const res = await api('/camera/attach', 'POST', { parent_id: id });
  if (res.success) {
    toast(`Camera #${res.actor_id} attached!`, 'ok');
    addLog(`Attached sensor #${res.actor_id} to parent #${id}`, 'ok');
    refreshCameras();
    openWin('win-cameras');
    setTimeout(() => {
        const card = document.querySelector(`.cam-card[data-id="${res.actor_id}"]`);
        if (card) card.click();
    }, 500);
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

  const saveSetupBtn = document.getElementById('camSaveSetupBtn');
  if (saveSetupBtn) {
    const hasCameras = data.cameras.length > 0;
    saveSetupBtn.disabled = !hasCameras;
    saveSetupBtn.style.opacity = hasCameras ? '1' : '0.4';
    saveSetupBtn.style.cursor = hasCameras ? 'pointer' : 'not-allowed';
    saveSetupBtn.title = hasCameras ? 'Save current camera configuration' : 'No cameras to save';
  }

  if (data.cameras.length === 0) {
    container.innerHTML = `<div style="color:var(--c-dim); font-size:0.7rem; padding:10px; font-family:'Share Tech Mono'; text-align:center;">NO SENSORS FOUND</div>`;
    return;
  }

  container.innerHTML = data.cameras.map(c => {
    const isStreaming = c.is_streaming;
    const typeShort   = c.type.split('.').pop().toUpperCase();
    return `
      <div class="actor-card cam-card ${isStreaming ? 'selected' : ''}" data-id="${c.id}"
           onclick='selectCamera(${JSON.stringify(c).replace(/'/g, "\\'")})' style="cursor:pointer;">
        <div style="display:flex; justify-content:space-between; align-items:center; pointer-events:none;">
          <div style="display:flex; flex-direction:column; gap:2px;">
            <span style="font-size:0.55rem; color:var(--c-muted); text-transform:uppercase;">${typeShort}</span>
            <span style="font-size:0.75rem; color:var(--c-bright); font-weight:600;">${c.name}</span>
          </div>
          <span style="font-size:0.6rem; color:var(--c-dim);">#${c.id}</span>
        </div>
      </div>`;
  }).join('');

  // Auto-sync transform inputs
  const badgeId  = document.getElementById('camBadgeId');
  const selectedId = badgeId ? badgeId.textContent : null;
  const followCheck = document.getElementById('camFollowSync');
  const isSyncEnabled = followCheck ? followCheck.checked : true;

  if (selectedId && selectedId !== '--' && isSyncEnabled) {
    const cam = data.cameras.find(c => c.id == selectedId);
    if (cam) {
      const inputs   = ['camX', 'camY', 'camZ', 'camPitch', 'camYaw', 'camRoll'];
      const hasFocus = inputs.some(id => document.activeElement === document.getElementById(id));
      if (!hasFocus) {
        updateInputIfNoFocus('camX',     cam.x.toFixed(2));
        updateInputIfNoFocus('camY',     cam.y.toFixed(2));
        updateInputIfNoFocus('camZ',     cam.z.toFixed(2));
        updateInputIfNoFocus('camPitch', Math.round(cam.pitch));
        updateInputIfNoFocus('camYaw',   Math.round(cam.yaw));
        updateInputIfNoFocus('camRoll',  Math.round(cam.roll));
      }
    }
  }
}

async function selectCamera(c) {
  const panel = document.getElementById('camControlPanel');
  panel.style.opacity      = '1';
  panel.style.pointerEvents = 'all';

  document.getElementById('camX').value     = c.x.toFixed(2);
  document.getElementById('camY').value     = c.y.toFixed(2);
  document.getElementById('camZ').value     = c.z.toFixed(2);
  document.getElementById('camPitch').value = Math.round(c.pitch);
  document.getElementById('camYaw').value   = Math.round(c.yaw);
  document.getElementById('camRoll').value  = Math.round(c.roll);

  const badgeId = document.getElementById('camBadgeId');
  const badgeName = document.getElementById('camBadgeName');
  const badge   = document.getElementById('camBadge');
  
  if (badgeId) badgeId.textContent = c.id;
  if (badgeName) badgeName.textContent = c.name;
  if (badge)   badge.style.display  = 'flex';
  
  const dirSel = document.getElementById('camDirectionSelect');
  if (dirSel) dirSel.value = c.direction || "";

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
        panel.style.opacity      = '0.4';
        panel.style.pointerEvents = 'none';
        if (badgeId) badgeId.textContent = '--';
        if (badgeName) badgeName.textContent = '--';
        if (badge)   badge.style.display  = 'none';
      } else {
        toast(res.error, 'err');
      }
    };
  }

  await api('/camera/set_stream_source', 'POST', { id: c.id });
  startCamPreview(c.id);

  document.querySelectorAll('.cam-card').forEach(card => {
    card.classList.toggle('selected', card.getAttribute('data-id') == c.id);
  });
}

function startCamPreview(id) {
  const img = document.getElementById('camPreviewImg');
  const ovr = document.getElementById('camPreviewOverlay');
  const ph  = document.getElementById('camPreviewPlaceholder');
  if (!img) return;

  if (window._activePreviewId !== undefined) {
    socket.emit('leave_camera', { id: window._activePreviewId });
  }

  window._activePreviewId = id;
  socket.emit('join_camera', { id: id });

  img.style.display = 'block';
  if (ovr) ovr.style.display = 'block';
  if (ph)  ph.style.display  = 'none';
}

function stopCamPreview() {
  const img = document.getElementById('camPreviewImg');
  const ovr = document.getElementById('camPreviewOverlay');
  const ph  = document.getElementById('camPreviewPlaceholder');
  if (!img) return;

  if (window._activePreviewId !== undefined) {
    socket.emit('leave_camera', { id: window._activePreviewId });
    window._activePreviewId = undefined;
  }

  img.src = '';
  img.style.display = 'none';
  if (ovr) ovr.style.display = 'none';
  if (ph)  ph.style.display  = 'flex';
  
  if (previewStreamBlobUrl) {
    URL.revokeObjectURL(previewStreamBlobUrl);
    previewStreamBlobUrl = null;
  }
}

async function renameCamera() {
    const idEl = document.getElementById('camBadgeId');
    const nameEl = document.getElementById('camBadgeName');
    const id = idEl ? idEl.textContent : null;
    if (!id || id === '--') return;
    
    const newName = prompt(`Enter new name for Sensor #${id}:`, nameEl.textContent);
    if (!newName) return;
    
    toast('Updating sensor name...');
    const res = await api('/camera/rename', 'POST', { id: parseInt(id), name: newName });
    if (res.success) {
        toast('Name updated', 'ok');
        if (nameEl) nameEl.textContent = newName;
        refreshCameras();
    } else {
        toast(res.error, 'err');
    }
}

async function jumpToCamera() {
    const idEl = document.getElementById('camBadgeId');
    const id = idEl ? idEl.textContent : null;
    if (!id || id === '--') return;
    
    toast('Jumping to camera position...');
    const d = {
        x:     parseFloat(document.getElementById('camX').value),
        y:     parseFloat(document.getElementById('camY').value),
        z:     parseFloat(document.getElementById('camZ').value) + 2.0, // small offset to see the camera
        pitch: parseFloat(document.getElementById('camPitch').value),
        yaw:   parseFloat(document.getElementById('camYaw').value),
        roll:  0,
    };
    const res = await api('/spectator/set', 'POST', d);
    if (res.success) {
        toast('Spectator moved', 'ok');
        if (typeof fetchSpectator === 'function') fetchSpectator();
    } else {
        toast(res.error, 'err');
    }
}

function copyCamLink() {
  const idEl   = document.getElementById('camBadgeId');
  const id     = idEl ? idEl.textContent : null;
  const baseUrl = window.location.origin + '/video_feed';
  const url    = (id && id !== '--') ? `${baseUrl}?id=${id}` : baseUrl;
  navigator.clipboard.writeText(url)
    .then(() => toast('Live link copied to clipboard!', 'ok'))
    .catch(() => toast('Failed to copy link', 'err'));
}

async function updateCameraPosition() {
  const idEl = document.getElementById('camBadgeId');
  const id   = idEl ? idEl.textContent : null;
  if (!id || id === '--') return;
  const d = {
    id:    parseInt(id),
    x:     parseFloat(document.getElementById('camX').value),
    y:     parseFloat(document.getElementById('camY').value),
    z:     parseFloat(document.getElementById('camZ').value),
    pitch: parseFloat(document.getElementById('camPitch').value),
    yaw:   parseFloat(document.getElementById('camYaw').value),
    roll:  parseFloat(document.getElementById('camRoll').value),
  };
  const res = await api('/camera/update', 'POST', d);
  if (res.success) { 
    toast(`Cam #${id} updated`, 'ok'); 
    refreshCameras(); 
  } else {
    toast(res.error, 'err');
  }
}

async function spawnType(type) {
  const bps = {
    rgb: 'sensor.camera.rgb', 
    depth: 'sensor.camera.depth',
    sem: 'sensor.camera.semantic_segmentation', 
    dvs: 'sensor.camera.dvs',
  };
  toast(`Spawning ${type.toUpperCase()}...`);
  const res = await api('/camera/spawn', 'POST', { 
    blueprint: bps[type] || bps.rgb, 
    width: 1280, 
    height: 720, 
    fov: 90 
  });
  if (res.success) { 
    toast(`Spawned ${type.toUpperCase()} (#${res.actor_id})`, 'ok'); 
    refreshCameras(); 
  } else {
    toast(res.error, 'err');
  }
}

function camSetToSpectator() {
  document.getElementById('camX').value     = document.getElementById('sX').textContent;
  document.getElementById('camY').value     = document.getElementById('sY').textContent;
  document.getElementById('camZ').value     = document.getElementById('sZ').textContent;
  document.getElementById('camPitch').value = document.getElementById('sPitch').textContent;
  document.getElementById('camYaw').value   = document.getElementById('sYaw').textContent;
  document.getElementById('camRoll').value  = document.getElementById('sRoll').textContent;
  toast('Matched spectator position', 'info');
}

function camLoadPosition(name) {
  if (!name) return;
  const loc = serverLocations[name];
  if (!loc) { toast('Location not found: ' + name, 'err'); return; }
  document.getElementById('camX').value     = parseFloat(loc.x).toFixed(2);
  document.getElementById('camY').value     = parseFloat(loc.y).toFixed(2);
  document.getElementById('camZ').value     = parseFloat(loc.z).toFixed(2);
  document.getElementById('camPitch').value = Math.round(parseFloat(loc.pitch));
  document.getElementById('camYaw').value   = Math.round(parseFloat(loc.yaw));
  document.getElementById('camRoll').value  = Math.round(parseFloat(loc.roll));
  toast('Preset loaded: ' + name, 'info');
  updateCameraPosition();
}

async function camSavePosition() {
  const idEl = document.getElementById('camBadgeId');
  const id   = idEl ? idEl.textContent : 'Unknown';
  const name = prompt('Enter name for this location:', `Cam #${id} Loc ` + new Date().toLocaleTimeString());
  if (!name) return;
  const payload = {
    name,
    x:     document.getElementById('camX').value,
    y:     document.getElementById('camY').value,
    z:     document.getElementById('camZ').value,
    pitch: document.getElementById('camPitch').value,
    yaw:   document.getElementById('camYaw').value,
    roll:  document.getElementById('camRoll').value,
  };
  toast(`Saving "${name}"...`);
  const res = await api('/history/location', 'POST', payload);
  if (res.success) { 
    toast(`Saved: ${name}`, 'ok'); 
    initHistory(); 
  } else {
    toast(res.error, 'err');
  }
}

async function camDeletePosition() {
  const sel = document.getElementById('camSavedLocations');
  const name = sel.value;
  if (!name) { toast('Select a preset to delete', 'warn'); return; }
  
  if (!confirm(`Are you sure you want to delete camera preset "${name}"?`)) return;
  
  toast(`Deleting "${name}"...`);
  const res = await api('/history/location', 'DELETE', { name });
  if (res.success) {
    toast(`Deleted: ${name}`, 'ok');
    initHistory();
  } else {
    toast(res.error, 'err');
  }
}

async function saveCameraSetup() {
  const name = prompt('Enter a name for this camera setup:', 'Setup ' + new Date().toLocaleTimeString());
  if (!name) return;
  toast(`Saving camera setup "${name}"...`);
  const res = await api('/camera/save_setup', 'POST', { name });
  if (res.success) {
    toast(`Saved setup: ${name} (${res.count} cameras)`, 'ok');
    addLog(`Camera setup "${name}" saved with ${res.count} cameras.`, 'ok');
    const h = await api('/camera/setups');
    if (h.success) renderSavedSetups(h.setups);
  } else {
    toast('Save failed: ' + res.error, 'err');
  }
}

async function deleteCameraSetup() {
  const sel = document.getElementById('camSavedSetups');
  const name = sel.value;
  if (!name) { toast('Select a setup to delete', 'warn'); return; }
  
  if (!confirm(`Are you sure you want to delete camera setup "${name}"?`)) return;
  
  toast(`Deleting setup "${name}"...`);
  const res = await api('/camera/delete_setup', 'POST', { name });
  if (res.success) {
    toast(`Deleted setup: ${name}`, 'ok');
    const h = await api('/camera/setups');
    if (h.success) renderSavedSetups(h.setups);
  } else {
    toast('Delete failed: ' + res.error, 'err');
  }
}

async function loadCameraSetup(name) {
  if (!name) return;
  toast(`Loading camera setup "${name}"...`, 'info', 5000);
  const res = await api('/camera/load_setup', 'POST', { name });
  if (res.success) {
    toast(`Setup "${name}" loaded: ${res.spawned} cameras spawned`, 'ok');
    addLog(`Camera setup "${name}" loaded. Spawned ${res.spawned} sensors.`, 'ok');
    document.getElementById('camSavedSetups').value = '';
    refreshCameras();
  } else {
    toast('Load failed: ' + res.error, 'err');
  }
}

async function setCameraDirection() {
  const idEl = document.getElementById('camBadgeId');
  const dirEl = document.getElementById('camDirectionSelect');
  const id = idEl ? idEl.textContent : null;
  const direction = dirEl ? dirEl.value : null;
  
  if (!id || id === '--') return;
  
  toast('Updating camera direction...');
  const res = await api('/camera/set_direction', 'POST', { id: parseInt(id), direction: direction || null });
  if (res.success) {
    toast('Direction updated: ' + (direction || 'None'), 'ok');
    refreshCameras();
  } else {
    toast(res.error, 'err');
  }
}
