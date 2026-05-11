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

  // Prevent re-render while user is interacting with a dropdown
  if (document.activeElement && document.activeElement.classList.contains('tl-dir-sel')) return;

  if (!lights || lights.length === 0) {
    const radius = document.getElementById('tlRadius')?.value || 200;
    tbody.innerHTML = `<tr><td colspan="5" class="tbl-empty">No lights within ${radius}m</td></tr>`;
    return;
  }

  tbody.innerHTML = lights.map(tl => {
    const s   = tl.state.toLowerCase();
    const cls = s === 'red' ? 'tl-r' : s === 'green' ? 'tl-g' : s === 'yellow' ? 'tl-y' : 'tl-o';
    const d   = tl.direction || "";
    
    return `<tr>
      <td>${tl.id}</td>
      <td>
        <select class="tl-dir-sel" style="padding:2px; font-size:0.6rem; width:45px;" 
                onchange="setTLDirection(${tl.id}, this.value)">
            <option value=""  ${d === "" ? "selected" : ""}>-</option>
            <option value="N" ${d === "N" ? "selected" : ""}>N</option>
            <option value="S" ${d === "S" ? "selected" : ""}>S</option>
            <option value="E" ${d === "E" ? "selected" : ""}>E</option>
            <option value="W" ${d === "W" ? "selected" : ""}>W</option>
        </select>
      </td>
      <td><span class="${cls}">${tl.state}</span></td>
      <td>${tl.distance}</td>
      <td>
        <div class="tl-btns">
          <button class="btn btn-danger btn-xs"  onclick="setTL(${tl.id},'red')">R</button>
          <button class="btn btn-success btn-xs" onclick="setTL(${tl.id},'green')">G</button>
          <button class="btn btn-warn btn-xs"    onclick="setTL(${tl.id},'yellow')">Y</button>
        </div>
      </td>
      <td>
        <div style="display:flex; gap:4px;">
            <button class="btn btn-cyan btn-xs" onclick="freezeTL(${tl.id})" title="Freeze">FRZ</button>
            <button class="btn btn-bright btn-xs" onclick="copyTLApiLink(${tl.id})" title="Copy API Link">LINK</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

async function setTLDirection(id, direction) {
  const res = await api('/traffic_light/set_direction', 'POST', { id, direction });
  if (res.success) {
    toast(`TL #${id} mapped to ${direction || 'None'}`, 'ok');
  } else {
    toast(res.error, 'err');
  }
}

function copyTLApiLink(id) {
  const baseUrl = window.location.origin + '/traffic_light/' + id;
  navigator.clipboard.writeText(baseUrl)
    .then(() => toast(`Base API Link copied for #${id}`, 'ok'))
    .catch(() => toast('Failed to copy link', 'err'));
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
