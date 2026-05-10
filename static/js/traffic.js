// ═══════════════════════════════════════════════════════════════
//  traffic.js — traffic light table, set, freeze
// ═══════════════════════════════════════════════════════════════

async function loadTrafficLights() {
  const radius = document.getElementById('tlRadius').value;
  const data   = await api('/traffic_lights?radius=' + radius);
  if (data.success) {
    renderTrafficLights(data.lights);
    toast(`${data.lights.length} light(s)`, 'ok');
    addLog(`Traffic lights: ${data.lights.length} within ${radius}m`, 'ok');
  } else {
    const tbody  = document.getElementById('tlTableBody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty tbl-err">${data.error}</td></tr>`;
  }
}

function renderTrafficLights(lights) {
  const tbody  = document.getElementById('tlTableBody');
  if (!tbody) return;

  if (!lights || lights.length === 0) {
    const radius = document.getElementById('tlRadius')?.value || 200;
    tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty">No lights within ${radius}m</td></tr>`;
    return;
  }

  tbody.innerHTML = lights.map(tl => {
    const s   = tl.state.toLowerCase();
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
