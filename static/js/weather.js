// ═══════════════════════════════════════════════════════════════
//  weather.js — sliders, presets, apply
//  Fix 5: _weatherDirty flag prevents slider reset while dragging
// ═══════════════════════════════════════════════════════════════

let weatherValues = {};
let _weatherDirty = false;   // true when user has touched sliders since last apply

const weatherParams = [
  { key: 'cloudiness',             label: 'Cloudiness',      min: 0,   max: 100 },
  { key: 'precipitation',          label: 'Precipitation',   min: 0,   max: 100 },
  { key: 'precipitation_deposits', label: 'Precip Deposits', min: 0,   max: 100 },
  { key: 'wind_intensity',         label: 'Wind Intensity',  min: 0,   max: 100 },
  { key: 'sun_azimuth_angle',      label: 'Sun Azimuth',     min: 0,   max: 360 },
  { key: 'sun_altitude_angle',     label: 'Sun Altitude',    min: -90, max: 90  },
  { key: 'fog_density',            label: 'Fog Density',     min: 0,   max: 100 },
  { key: 'fog_distance',           label: 'Fog Distance',    min: 0,   max: 200 },
  { key: 'wetness',                label: 'Wetness',         min: 0,   max: 100 },
];

function buildWeatherSliders(values = {}) {
  // Fix 5: if user is editing sliders, don't overwrite their work on next poll
  if (_weatherDirty) return;

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
          oninput="weatherValues['${p.key}']=parseFloat(this.value);
                   document.getElementById('sv_${p.key}').textContent=this.value;
                   _weatherDirty=true;"/>
        <span class="sv" id="sv_${p.key}">${val}</span>
      </div>`;
  });
}

async function applyWeather() {
  toast('Applying weather...');
  const data = await api('/weather', 'POST', weatherValues);
  if (data.success) {
    _weatherDirty = false;   // reset — poll can update sliders again
    toast('Weather applied', 'ok');
    addLog('Custom weather applied', 'ok');
  } else {
    toast('Weather error: ' + data.error, 'err', 5000);
  }
}

async function weatherPreset(preset) {
  toast('Applying preset: ' + preset + '...');
  const data = await api('/weather/preset', 'POST', { preset });
  if (data.success) {
    _weatherDirty = false;   // preset overrides user edits
    toast('Weather: ' + preset, 'ok');
    addLog('Weather preset: ' + preset, 'ok');
    if (data.values) buildWeatherSliders(data.values);
  } else {
    toast('Preset failed: ' + data.error, 'err', 5000);
  }
}

// Color picker helpers (used in spawn panel)
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
