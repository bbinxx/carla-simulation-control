// ═══════════════════════════════════════════════════════════════
//  media.js — live stream + camera manager
//  Fix 9 (stream follows spectator): handled server-side in
//  threads/stream.py + core/camera.py; client just loads the feed.
// ═══════════════════════════════════════════════════════════════

let camPollInterval = null;

socket.on('connect', () => {
  console.log('Socket.IO connected');
});

socket.on('frame', (data) => {
  // data = { id: actor_id, data: base64_jpeg }
  const b64Data = 'data:image/jpeg;base64,' + data.data;
  
  // Update Live Stream window if it's matching the ID
  const liveImg = document.getElementById('liveStream');
  if (liveImg && liveImg.style.display !== 'none') {
    // If it's the selected camera (data.id is null/None on server for spec)
    if (data.id === null) {
      liveImg.src = b64Data;
    }
  }

  // Update Camera Manager Preview if it matches
  const previewImg = document.getElementById('camPreviewImg');
  const badgeId = document.getElementById('camBadgeId');
  if (previewImg && previewImg.style.display !== 'none' && badgeId) {
    const activeId = badgeId.textContent;
    if (activeId === '--' && data.id === null) {
      previewImg.src = b64Data;
    } else if (activeId == data.id) {
      previewImg.src = b64Data;
    }
  }
});

// ── Live Stream ────────────────────────────────────────────────

function startStream() {
  const img = document.getElementById('liveStream');
  img.style.display = 'block';
  // Join the selected camera room
  socket.emit('join_camera', { id: null });
  
  document.getElementById('liveStreamStatus').style.display = 'none';
  document.getElementById('streamBtn').style.display        = 'none';
  document.getElementById('streamStopBtn').style.display    = 'flex';
  toast('Live stream started (Socket.IO)', 'ok');
  addLog('Live stream started via Socket.IO');
}

function stopStream() {
  const img = document.getElementById('liveStream');
  img.src = '';
  img.style.display = 'none';
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
    toast(`Resolution set to ${w}x${h} (${q}%)`, 'ok');
    addLog(`Stream config updated: ${w}x${h} / Q${q}%`, 'ok');
    // Restart feed to apply immediately
    const img = document.getElementById('liveStream');
    if (img && img.style.display !== 'none') startStream();
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
    toast(`Camera ${res.actor_id} attached! Loading preview...`, 'ok');
    addLog(`Camera ID:${res.actor_id} attached to parent ID:${id}`, 'ok');
    await api('/camera/set_stream_source', 'POST', { id: res.actor_id });
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
    const typeShort   = c.type.split('.').pop().toUpperCase();
    return `
      <div class="actor-card cam-card ${isStreaming ? 'selected' : ''}" data-id="${c.id}"
           onclick='selectCamera(${JSON.stringify(c).replace(/'/g, "\\'")})' style="cursor:pointer;">
        <div style="display:flex; justify-content:space-between; align-items:center; pointer-events:none;">
          <span style="font-size:0.75rem; color:var(--c-bright);">#${c.id}</span>
          <span class="badge ${isStreaming ? 'badge-v' : 'badge-o'}">${typeShort}</span>
        </div>
      </div>`;
  }).join('');

  // Auto-update position inputs if camera is selected and not focused
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
  const badge   = document.getElementById('camBadge');
  if (badgeId) badgeId.textContent = c.id;
  if (badge)   badge.style.display  = 'flex';

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
        if (badge)   badge.style.display  = 'none';
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
  const ph  = document.getElementById('camPreviewPlaceholder');
  if (!img) return;

  // Stop any previous preview room
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

async function setCameraAsSource(id) {
  const res = await api('/camera/set_stream_source', 'POST', { id });
  if (!res.success) toast(res.error, 'err');
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
  if (res.success) { toast(`Cam #${id} updated`, 'ok'); refreshCameras(); }
  else toast(res.error, 'err');
}

async function spawnType(type) {
  const bps = {
    rgb: 'sensor.camera.rgb', depth: 'sensor.camera.depth',
    sem: 'sensor.camera.semantic_segmentation', dvs: 'sensor.camera.dvs',
  };
  const res = await api('/camera/spawn', 'POST',
    { blueprint: bps[type] || bps.rgb, width: 640, height: 360, fov: 90 });
  if (res.success) { toast(`Spawned ${type.toUpperCase()} (#${res.actor_id})`, 'ok'); refreshCameras(); }
  else toast(res.error, 'err');
}

function spawnNewCamera() { spawnType('rgb'); }

function camSetToSpectator() {
  document.getElementById('camX').value     = document.getElementById('sX').textContent;
  document.getElementById('camY').value     = document.getElementById('sY').textContent;
  document.getElementById('camZ').value     = document.getElementById('sZ').textContent;
  document.getElementById('camPitch').value = document.getElementById('sPitch').textContent;
  document.getElementById('camYaw').value   = document.getElementById('sYaw').textContent;
  document.getElementById('camRoll').value  = document.getElementById('sRoll').textContent;
  toast('Matched spectator', 'info');
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
  if (res.success) { toast(`Saved: ${name}`, 'ok'); initHistory(); }
  else toast(res.error, 'err');
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
