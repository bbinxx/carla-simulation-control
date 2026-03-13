// ═══════════════════════════════════════════════════════════════
//  environment.js — env object toggle, screenshot
// ═══════════════════════════════════════════════════════════════

// ── Environment Objects ────────────────────────────────────────

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

let screenshotB64 = null;

async function takeScreenshot() {
  const btn = document.getElementById('ssBtn');
  btn.disabled = true; btn.textContent = 'CAPTURING...';
  document.getElementById('ssStatus').textContent = 'Capturing frame...';
  toast('Capturing screenshot...');

  const data = await api('/screenshot', 'POST', {
    width:  parseInt(document.getElementById('ssW').value),
    height: parseInt(document.getElementById('ssH').value),
    fov:    parseInt(document.getElementById('ssFov').value),
  });
  btn.disabled = false; btn.textContent = 'CAPTURE';

  if (data.success) {
    screenshotB64 = data.image;
    const img     = document.getElementById('screenshotImg');
    img.src       = 'data:image/png;base64,' + data.image;
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
  const a  = document.createElement('a');
  a.href   = 'data:image/png;base64,' + screenshotB64;
  a.download = 'carla_' + Date.now() + '.png';
  a.click();
  toast('Downloading...', 'ok');
}
