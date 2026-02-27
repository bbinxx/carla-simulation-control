
  // ── State ──────────────────────────────────────────────────────────────────
  let serverLocations = {};
  let pollInterval    = null;
  let weatherValues   = {};
  let screenshotB64   = null;

  const weatherParams = [
    { key: "cloudiness",            label: "Cloudiness",       min: 0,   max: 100 },
    { key: "precipitation",         label: "Precipitation",    min: 0,   max: 100 },
    { key: "precipitation_deposits",label: "Precip. Deposits", min: 0,   max: 100 },
    { key: "wind_intensity",        label: "Wind Intensity",   min: 0,   max: 100 },
    { key: "sun_azimuth_angle",     label: "Sun Azimuth",      min: 0,   max: 360 },
    { key: "sun_altitude_angle",    label: "Sun Altitude",     min: -90, max: 90  },
    { key: "fog_density",           label: "Fog Density",      min: 0,   max: 100 },
    { key: "fog_distance",          label: "Fog Distance",     min: 0,   max: 200 },
    { key: "wetness",               label: "Wetness",          min: 0,   max: 100 },
  ];

  // ── Core UI helpers ────────────────────────────────────────────────────────
  function toast(msg, type = "info", duration = 3500) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className   = "show " + type;
    clearTimeout(window._tt);
    window._tt = setTimeout(() => t.className = "", duration);
  }

  function addLog(msg, type = "info") {
    const box = document.getElementById("logBox");
    const ts  = new Date().toLocaleTimeString();
    const e   = document.createElement("div");
    e.className   = `log-entry log-${type}`;
    e.textContent = `[${ts}] ${msg}`;
    box.appendChild(e);
    box.scrollTop = box.scrollHeight;
    // Mirror errors to browser console
    if (type === "err")  console.error(`[CARLA] ${msg}`);
    if (type === "warn") console.warn(`[CARLA] ${msg}`);
  }

  function clearLog() { document.getElementById("logBox").innerHTML = ""; }

  // ── API wrapper ────────────────────────────────────────────────────────────
  async function api(path, method = "GET", body = null) {
    try {
      const opts = { method, headers: { "Content-Type": "application/json" } };
      if (body) opts.body = JSON.stringify(body);
      const res  = await fetch(path, opts);
      if (!res.ok) {
        const txt = await res.text();
        const msg = `HTTP ${res.status} on ${method} ${path}: ${txt.slice(0, 200)}`;
        addLog(msg, "err");
        console.error("[api]", msg);
        return { success: false, error: msg };
      }
      return await res.json();
    } catch (err) {
      const msg = `Network error on ${method} ${path}: ${err.message}`;
      addLog(msg, "err");
      console.error("[api]", err);
      return { success: false, error: msg };
    }
  }

  // ── History / DB ───────────────────────────────────────────────────────────
  async function initHistory() {
    try {
      const res = await api("/history", "GET");
      if (res.success) {
        const hosts = res.hosts || [];
        const dl = document.getElementById("hostHistory");
        if (dl) dl.innerHTML = hosts.map(h => `<option value="${h.host}">`).join("");

        if (res.last_connection) {
          const hi = document.getElementById("hostInput");
          const pi = document.getElementById("portInput");
          if (hi) hi.value = res.last_connection.host;
          if (pi) pi.value = res.last_connection.port;
        }
        serverLocations = res.locations || {};
        renderSavedLocations();
        addLog(`History loaded — ${hosts.length} host(s), ${Object.keys(serverLocations).length} location(s)`, "info");
      } else {
        addLog("Failed to load history: " + res.error, "warn");
      }
    } catch (e) {
      addLog("initHistory exception: " + e.message, "err");
      console.error(e);
    }
  }

  async function saveHostHistory(host, port) {
    const res = await api("/history/host", "POST", { host, port });
    if (!res.success) addLog("Host save failed: " + res.error, "warn");
    initHistory();
  }

  function renderSavedLocations() {
    const sel = document.getElementById("savedLocations");
    if (!sel) return;
    sel.innerHTML = '<option value="">-- Load Location --</option>' +
      Object.keys(serverLocations).map(k => `<option value="${k}">${k}</option>`).join("");
  }

  async function saveSpectatorPosition() {
    const name = document.getElementById("locName").value.trim() ||
                 "Location " + new Date().toLocaleTimeString();
    const payload = {
      name,
      x:     document.getElementById("sX").textContent,
      y:     document.getElementById("sY").textContent,
      z:     document.getElementById("sZ").textContent,
      pitch: document.getElementById("sPitch").textContent,
      yaw:   document.getElementById("sYaw").textContent,
      roll:  document.getElementById("sRoll").textContent,
    };
    toast(`Saving "${name}"…`, "info");
    const res = await api("/history/location", "POST", payload);
    if (res.success) {
      toast(`📍 Saved: ${name}`, "ok");
      addLog(`Location saved: ${name}`, "ok");
      document.getElementById("locName").value = "";
      initHistory();
    } else {
      toast("Save failed: " + res.error, "err");
      addLog("Save location error: " + res.error, "err");
    }
  }

  function loadSpectatorPosition(name) {
    if (!name) return;
    const loc = serverLocations[name];
    if (!loc) { toast("Location not found: " + name, "err"); return; }
    document.getElementById("specX").value     = loc.x;
    document.getElementById("specY").value     = loc.y;
    document.getElementById("specZ").value     = loc.z;
    document.getElementById("specPitch").value = loc.pitch;
    document.getElementById("specYaw").value   = loc.yaw;
    document.getElementById("specRoll").value  = loc.roll;
    toast(`📍 Loaded: ${name}`, "ok");
    addLog(`Location loaded into form: ${name}`, "ok");
    moveSpectator();
    document.getElementById("savedLocations").value = "";
  }

  document.addEventListener("DOMContentLoaded", initHistory);

  // ── Weather sliders ────────────────────────────────────────────────────────
  function buildWeatherSliders(values = {}) {
    const wrap = document.getElementById("weatherSliders");
    wrap.innerHTML = "";
    weatherParams.forEach(p => {
      const val = values[p.key] ?? weatherValues[p.key] ?? 0;
      weatherValues[p.key] = val;
      wrap.innerHTML += `<div class="slider-group">
        <div class="slider-label">
          <label style="margin:0">${p.label}</label>
          <span id="val_${p.key}">${val}</span>
        </div>
        <input type="range" min="${p.min}" max="${p.max}" value="${val}"
          oninput="weatherValues['${p.key}']=parseFloat(this.value);document.getElementById('val_${p.key}').textContent=this.value"/>
      </div>`;
    });
  }
  buildWeatherSliders();

  // ── Tabs ───────────────────────────────────────────────────────────────────
  function switchTab(name, el) {
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.getElementById("tab-" + name).classList.add("active");
    el.classList.add("active");
    if (name === "traffic") loadTrafficLights();
  }

  // ── Color helpers ──────────────────────────────────────────────────────────
  function syncColor(el) {
    const hex = el.value;
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    document.getElementById("colorText").value = `${r},${g},${b}`;
  }
  function syncColorText(el) {
    const p = el.value.split(",").map(Number);
    if (p.length === 3 && p.every(n => !isNaN(n)))
      document.getElementById("colorPicker").value = "#" + p.map(n => Math.min(255,Math.max(0,n)).toString(16).padStart(2,"0")).join("");
  }

  // ── Connect / Disconnect ───────────────────────────────────────────────────
  async function connect() {
    const host    = document.getElementById("hostInput").value.trim();
    const port    = document.getElementById("portInput").value;
    const timeout = document.getElementById("timeoutInput").value;
    if (!host) { toast("⚠️ Enter a host address", "err"); return; }

    const btn = document.getElementById("connectBtn");
    btn.disabled    = true;
    btn.textContent = "Connecting…";
    toast(`🔌 Connecting to ${host}:${port}…`, "info");
    addLog(`Connecting to ${host}:${port}…`, "info");

    const data = await api("/connect", "POST", { host, port, timeout });
    btn.disabled    = false;
    btn.textContent = "⚡ Connect";

    if (data.success) {
      setConnected(true, data);
      saveHostHistory(host, port);
      toast(`✅ Connected — ${data.map}`, "ok");
      addLog(`Connected. Map: ${data.map} | TM port: ${data.tm_port}`, "ok");
      loadMaps(); loadBlueprints(); loadAllBlueprints(); startPolling();
    } else {
      toast("❌ Connection failed: " + data.error, "err", 5000);
      addLog("Connect error: " + data.error, "err");
    }
  }

  async function disconnect() {
    clearInterval(pollInterval);
    stopStream();
    toast("🔌 Disconnecting…", "info");
    const data = await api("/disconnect", "POST");
    setConnected(false);
    if (data.success) {
      toast("🔌 Disconnected", "info");
      addLog("Disconnected", "warn");
    } else {
      toast("⚠️ Disconnect error: " + data.error, "err");
      addLog("Disconnect error: " + data.error, "err");
    }
  }

  async function toggleDebugBboxes() {
    const btn = document.getElementById("debugBoxesBtn");
    toast("Toggling debug bboxes…", "info");
    const res = await api("/debug/toggle_bboxes", "POST");
    if (res.success) {
      btn.textContent = res.enabled ? "🔲 Hide Debug BBoxes" : "🔳 Show Debug BBoxes";
      toast(res.enabled ? "🔲 Debug BBoxes ON" : "🔳 Debug BBoxes OFF", "ok");
      addLog(`Debug BBoxes: ${res.enabled ? "ON" : "OFF"}`, "info");
    } else {
      toast("⚠️ BBox toggle failed: " + res.error, "err");
      addLog("BBox toggle error: " + res.error, "err");
    }
  }

  // ── Connected state ────────────────────────────────────────────────────────
  function setConnected(state, data = {}) {
    const badge = document.getElementById("statusBadge");
    badge.className = "status-badge " + (state ? "connected" : "disconnected");
    document.getElementById("statusText").textContent =
      state ? `${data.host}:${data.port}` : "Disconnected";
    ["connectBtn"].forEach(id => document.getElementById(id).style.display = state ? "none" : "block");
    ["disconnectBtn","serverInfoCard","mapCard","spectatorLiveCard","statsRow","mainTabs","screenshotBtn"]
      .forEach(id => document.getElementById(id).style.display = state ? "block" : "none");
    document.getElementById("disconnectedPlaceholder").style.display = state ? "none" : "flex";
    document.getElementById("statsRow").style.display = state ? "grid" : "none";
    if (state) {
      document.getElementById("infoHost").textContent = data.host;
      document.getElementById("infoPort").textContent = data.port;
      document.getElementById("infoMap").textContent  = data.map || "—";
    }
  }

  // ── Polling ────────────────────────────────────────────────────────────────
  function startPolling() {
    clearInterval(pollInterval);
    pollInterval = setInterval(refreshStatus, 3000);
    refreshStatus();
  }

  async function refreshStatus() {
    const data = await api("/status");
    if (!data.connected) {
      setConnected(false);
      clearInterval(pollInterval);
      if (data.error) {
        toast("❌ CARLA connection lost: " + data.error, "err", 6000);
        addLog("Connection lost: " + data.error, "err");
      } else {
        toast("⚠️ Lost connection to CARLA", "err");
        addLog("Connection lost", "err");
      }
      return;
    }
    document.getElementById("infoMap").textContent     = data.map;
    document.getElementById("infoActors").textContent  = data.actor_count;
    document.getElementById("statActors").textContent  = data.actor_count;
    document.getElementById("statVehicles").textContent= data.vehicle_count;
    document.getElementById("statWalkers").textContent = data.walker_count;
    document.getElementById("statSensors").textContent = data.sensor_count;

    if (data.spectator) updateSpectatorDisplay(data.spectator);

    const tbody = document.getElementById("actorTableBody");
    if (!data.actors || data.actors.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:20px">No actors in world</td></tr>`;
    } else {
      tbody.innerHTML = data.actors.map(a => {
        let cls = "type-other";
        if (a.type.startsWith("vehicle"))        cls = "type-vehicle";
        else if (a.type.startsWith("walker"))    cls = "type-walker";
        else if (a.type.startsWith("sensor"))    cls = "type-sensor";
        else if (a.type.includes("traffic"))     cls = "type-tl";
        return `<tr>
          <td>${a.id}</td>
          <td><span class="type-badge ${cls}">${a.type.split(".").slice(0,2).join(".")}</span></td>
          <td>${a.x}</td><td>${a.y}</td><td>${a.z}</td>
          <td><button class="btn btn-sm btn-danger" onclick="destroyActor(${a.id})">✕</button></td>
        </tr>`;
      }).join("");
    }
    if (data.weather) buildWeatherSliders(data.weather);
  }

  // ── Spectator ──────────────────────────────────────────────────────────────
  function updateSpectatorDisplay(s) {
    document.getElementById("sX").textContent     = s.x;
    document.getElementById("sY").textContent     = s.y;
    document.getElementById("sZ").textContent     = s.z;
    document.getElementById("sPitch").textContent = s.pitch;
    document.getElementById("sYaw").textContent   = s.yaw;
    document.getElementById("sRoll").textContent  = s.roll;
  }

  async function fetchSpectator() {
    toast("Fetching spectator…", "info");
    const data = await api("/spectator/get");
    if (data.success) {
      updateSpectatorDisplay(data);
      toast("📷 Spectator updated", "ok");
      addLog(`Spectator: X=${data.x} Y=${data.y} Z=${data.z}`, "info");
    } else {
      toast("⚠️ Spectator fetch failed: " + data.error, "err");
      addLog("Spectator fetch error: " + data.error, "err");
    }
  }

  async function moveSpectator() {
    const d = {
      x:     parseFloat(document.getElementById("specX").value),
      y:     parseFloat(document.getElementById("specY").value),
      z:     parseFloat(document.getElementById("specZ").value),
      pitch: parseFloat(document.getElementById("specPitch").value),
      yaw:   parseFloat(document.getElementById("specYaw").value),
      roll:  parseFloat(document.getElementById("specRoll").value),
    };
    toast("🎯 Moving camera…", "info");
    const data = await api("/spectator/set", "POST", d);
    if (data.success) {
      toast(`✅ Camera moved to (${d.x}, ${d.y}, ${d.z})`, "ok");
      addLog(`Spectator → (${d.x}, ${d.y}, ${d.z}) pitch=${d.pitch} yaw=${d.yaw}`, "ok");
    } else {
      toast("❌ Move failed: " + data.error, "err");
      addLog("Move spectator error: " + data.error, "err");
    }
  }

  // ── Maps ───────────────────────────────────────────────────────────────────
  async function loadMaps() {
    const data = await api("/map/list");
    if (data.success) {
      document.getElementById("mapSelect").innerHTML =
        data.maps.map(m => `<option value="${m}">${m.split("/").pop()}</option>`).join("");
      addLog(`Maps loaded: ${data.maps.length} available`, "info");
    } else {
      addLog("Map list error: " + data.error, "err");
      toast("⚠️ Could not load map list: " + data.error, "err");
    }
  }

  async function loadMap() {
    const map = document.getElementById("mapSelect").value;
    if (!map) { toast("⚠️ Select a map first", "err"); return; }
    toast(`🗺 Loading ${map.split("/").pop()}…`, "info");
    addLog(`Loading map: ${map}`, "info");
    const data = await api("/map/load", "POST", { map });
    if (data.success) {
      toast(`✅ Map loaded: ${data.map}`, "ok");
      addLog(`Map loaded: ${data.map}`, "ok");
    } else {
      toast("❌ Map load failed: " + data.error, "err", 5000);
      addLog("Map load error: " + data.error, "err");
    }
  }

  // ── Blueprints ─────────────────────────────────────────────────────────────
  async function loadBlueprints() {
    const data = await api("/blueprints?filter=vehicle.*");
    if (data.success) {
      document.getElementById("vehicleBp").innerHTML =
        data.blueprints.map(b => `<option value="${b}">${b}</option>`).join("");
      addLog(`Vehicle blueprints: ${data.blueprints.length}`, "info");
    } else {
      addLog("Blueprint load error: " + data.error, "err");
      toast("⚠️ Blueprint load failed: " + data.error, "err");
    }
  }

  async function loadAllBlueprints() {
    const data = await api("/blueprints?filter=*");
    if (data.success) {
      document.getElementById("anyBp").innerHTML =
        data.blueprints.map(b => `<option value="${b}">${b}</option>`).join("");
    } else {
      addLog("All-blueprints load error: " + data.error, "err");
    }
  }

  async function filterBps() {
    const filt = document.getElementById("bpFilter").value.trim() || "*";
    toast(`🔍 Filtering: ${filt}`, "info");
    const data = await api(`/blueprints?filter=${encodeURIComponent(filt)}`);
    if (data.success) {
      document.getElementById("anyBp").innerHTML =
        data.blueprints.map(b => `<option value="${b}">${b}</option>`).join("");
      toast(`🔍 ${data.blueprints.length} result(s)`, "ok");
      addLog(`Blueprint filter "${filt}": ${data.blueprints.length} results`, "info");
    } else {
      toast("⚠️ Filter error: " + data.error, "err");
      addLog("Blueprint filter error: " + data.error, "err");
    }
  }

  // ── Spawn ──────────────────────────────────────────────────────────────────
  async function spawnVehicle() {
    const bp = document.getElementById("vehicleBp").value;
    if (!bp) { toast("⚠️ Select a blueprint", "err"); return; }
    toast(`🚘 Spawning ${bp}…`, "info");
    addLog(`Spawning vehicle: ${bp}`, "info");
    const data = await api("/spawn/vehicle", "POST", {
      blueprint:   bp,
      color:       document.getElementById("colorText").value,
      autopilot:   document.getElementById("autopilotCb").checked,
      at_spectator:document.getElementById("atSpectatorCb").checked,
    });
    if (data.success) {
      toast(`✅ Spawned ${data.blueprint} (ID:${data.actor_id})`, "ok");
      addLog(`Vehicle spawned — ID:${data.actor_id} bp:${data.blueprint}`, "ok");
    } else {
      toast("❌ Spawn failed: " + data.error, "err", 5000);
      addLog("Spawn vehicle error: " + data.error, "err");
    }
  }

  async function spawnNPC() {
    const count  = parseInt(document.getElementById("npcCount").value);
    const radius = parseFloat(document.getElementById("npcRadius").value);
    toast(`🚦 Spawning ${count} NPCs…`, "info");
    addLog(`Spawning ${count} NPCs (radius: ${radius})`, "info");
    const data = await api("/spawn/npc", "POST", { count, radius });
    if (data.success) {
      toast(`✅ Spawned ${data.spawned} NPC vehicle(s)`, "ok");
      addLog(`NPCs spawned: ${data.spawned}/${count}`, "ok");
    } else {
      toast("❌ NPC spawn failed: " + data.error, "err", 5000);
      addLog("NPC spawn error: " + data.error, "err");
    }
  }

  async function spawnWalkers() {
    const count = parseInt(document.getElementById("walkerCount").value);
    toast(`🚶 Spawning ${count} walkers…`, "info");
    addLog(`Spawning ${count} walkers`, "info");
    const data = await api("/spawn/walker", "POST", { count });
    if (data.success) {
      toast(`✅ Spawned ${data.spawned} walker(s)`, "ok");
      addLog(`Walkers spawned: ${data.spawned}/${count}`, "ok");
    } else {
      toast("❌ Walker spawn failed: " + data.error, "err", 5000);
      addLog("Walker spawn error: " + data.error, "err");
    }
  }

  async function spawnCamera() {
    const w = parseInt(document.getElementById("camW").value);
    const h = parseInt(document.getElementById("camH").value);
    const f = parseInt(document.getElementById("camFov").value);
    toast(`📷 Spawning camera ${w}×${h}…`, "info");
    addLog(`Spawning camera ${w}×${h} fov:${f}`, "info");
    const data = await api("/spawn/camera", "POST", { width: w, height: h, fov: f });
    if (data.success) {
      toast(`✅ Camera spawned (ID:${data.actor_id})`, "ok");
      addLog(`Camera spawned — ID:${data.actor_id}`, "ok");
    } else {
      toast("❌ Camera spawn failed: " + data.error, "err", 5000);
      addLog("Camera spawn error: " + data.error, "err");
    }
  }

  async function spawnAny() {
    const bp = document.getElementById("anyBp").value;
    if (!bp) { toast("⚠️ Select a blueprint", "err"); return; }
    const zOff = parseFloat(document.getElementById("anyZOffset").value);
    const auto = document.getElementById("anyAutopilot").checked;
    toast(`⚡ Spawning ${bp}…`, "info");
    addLog(`Spawning any: ${bp} z_offset=${zOff}`, "info");
    const data = await api("/spawn/any", "POST", { blueprint: bp, z_offset: zOff, autopilot: auto });
    if (data.success) {
      toast(`✅ Spawned ${data.blueprint} (ID:${data.actor_id})`, "ok");
      addLog(`Spawned — ID:${data.actor_id} bp:${data.blueprint}`, "ok");
    } else {
      toast("❌ Spawn failed: " + data.error, "err", 5000);
      addLog("Spawn any error: " + data.error, "err");
    }
  }

  // ── Destroy ────────────────────────────────────────────────────────────────
  async function destroyFilter(filter) {
    toast(`🗑 Destroying ${filter}…`, "info");
    addLog(`Destroying all: ${filter}`, "warn");
    const data = await api("/destroy/all", "POST", { filter });
    if (data.success) {
      toast(`✅ Destroyed ${data.destroyed} actor(s)`, "ok");
      addLog(`Destroyed ${data.destroyed} (filter: ${filter})`, "warn");
    } else {
      toast("❌ Destroy failed: " + data.error, "err", 5000);
      addLog("Destroy error: " + data.error, "err");
    }
  }

  async function destroyActor(id) {
    toast(`🗑 Destroying ID:${id}…`, "info");
    addLog(`Destroying actor ID:${id}`, "warn");
    const data = await api("/destroy/actor", "POST", { id });
    if (data.success) {
      toast(`✅ Actor ${id} destroyed`, "ok");
      addLog(`Actor ${id} destroyed`, "warn");
      refreshStatus();
    } else {
      toast("❌ Destroy failed: " + data.error, "err");
      addLog(`Destroy actor ${id} error: ` + data.error, "err");
    }
  }

  // ── Weather ────────────────────────────────────────────────────────────────
  async function weatherPreset(preset) {
    toast(`🌤 Applying preset: ${preset}…`, "info");
    addLog(`Weather preset: ${preset}`, "info");
    const data = await api("/weather/preset", "POST", { preset });
    if (data.success) {
      toast(`✅ Weather: ${preset}`, "ok");
      addLog(`Weather preset applied: ${preset}`, "ok");
      if (data.values) buildWeatherSliders(data.values);
    } else {
      toast("❌ Preset failed: " + data.error, "err", 5000);
      addLog("Weather preset error: " + data.error, "err");
    }
  }

  async function applyWeather() {
    toast("🌤 Applying custom weather…", "info");
    addLog("Applying custom weather", "info");
    const data = await api("/weather", "POST", weatherValues);
    if (data.success) {
      toast("✅ Weather applied", "ok");
      addLog("Custom weather applied", "ok");
    } else {
      toast("❌ Weather error: " + data.error, "err", 5000);
      addLog("Apply weather error: " + data.error, "err");
    }
  }

  // ── Traffic Lights ─────────────────────────────────────────────────────────
  async function loadTrafficLights() {
    const radius = document.getElementById("tlRadius").value;
    toast(`🚦 Loading lights within ${radius}m…`, "info");
    const data = await api(`/traffic_lights?radius=${radius}`);
    const tbody = document.getElementById("tlTableBody");
    if (!data.success) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--red);padding:16px">${data.error}</td></tr>`;
      addLog("Traffic lights error: " + data.error, "err");
      toast("❌ TL load failed: " + data.error, "err");
      return;
    }
    if (data.lights.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:16px">No lights within ${radius}m</td></tr>`;
      toast(`ℹ️ No lights within ${radius}m`, "info");
      addLog(`No traffic lights within ${radius}m`, "warn");
      return;
    }
    tbody.innerHTML = data.lights.map(tl => {
      const s   = tl.state.toLowerCase();
      const cls = s === "red" ? "tl-red" : s === "green" ? "tl-green" : s === "yellow" ? "tl-yellow" : "tl-off";
      return `<tr>
        <td>${tl.id}</td>
        <td><span class="${cls}">${tl.state}</span></td>
        <td>${tl.distance}</td>
        <td>
          <div class="tl-controls">
            <button class="tl-btn-r" onclick="setTL(${tl.id},'red')">R</button>
            <button class="tl-btn-g" onclick="setTL(${tl.id},'green')">G</button>
            <button class="tl-btn-y" onclick="setTL(${tl.id},'yellow')">Y</button>
          </div>
        </td>
        <td><button class="btn btn-sm btn-warning" onclick="freezeTL(${tl.id})">❄</button></td>
      </tr>`;
    }).join("");
    toast(`✅ ${data.lights.length} light(s) loaded`, "ok");
    addLog(`Traffic lights: ${data.lights.length} within ${radius}m`, "ok");
  }

  async function setTL(id, state) {
    toast(`🚦 Setting TL ${id} → ${state}…`, "info");
    const data = await api("/traffic_light/set", "POST", { id, state, freeze: true });
    if (data.success) {
      toast(`✅ TL ${id} → ${state}`, "ok");
      addLog(`TL ${id} set to ${state} (frozen)`, "ok");
      setTimeout(loadTrafficLights, 300);
    } else {
      toast("❌ TL set failed: " + data.error, "err");
      addLog(`TL ${id} set error: ` + data.error, "err");
    }
  }

  async function freezeTL(id) {
    toast(`❄️ Freezing TL ${id}…`, "info");
    const data = await api("/traffic_light/set", "POST", { id, freeze: true });
    if (data.success) {
      toast(`✅ TL ${id} frozen`, "ok");
      addLog(`TL ${id} frozen`, "ok");
    } else {
      toast("❌ Freeze failed: " + data.error, "err");
      addLog(`TL freeze ${id} error: ` + data.error, "err");
    }
  }

  async function freezeAll(state) {
    toast(`🚦 Setting all lights → ${state}…`, "info");
    addLog(`Freeze all TL: ${state}`, "info");
    const data = await api("/traffic_light/freeze_all", "POST", { freeze: true, state });
    if (data.success) {
      toast(`✅ All lights → ${state} (frozen)`, "ok");
      addLog(`All TL set to ${state} (frozen)`, "ok");
      setTimeout(loadTrafficLights, 400);
    } else {
      toast("❌ Freeze-all failed: " + data.error, "err");
      addLog("Freeze all TL error: " + data.error, "err");
    }
  }

  async function unfreezeAll() {
    toast("▶ Unfreezing all traffic lights…", "info");
    addLog("Unfreeze all TL", "info");
    const data = await api("/traffic_light/freeze_all", "POST", { freeze: false });
    if (data.success) {
      toast("✅ Traffic lights resumed", "ok");
      addLog("All TL unfrozen", "ok");
      setTimeout(loadTrafficLights, 400);
    } else {
      toast("❌ Unfreeze failed: " + data.error, "err");
      addLog("Unfreeze all TL error: " + data.error, "err");
    }
  }

  // ── Environment ────────────────────────────────────────────────────────────
  async function toggleEnvObject(enable) {
    const label = document.getElementById("envObjectSelect").value;
    toast(`${enable ? "👁 Showing" : "🚫 Hiding"} ${label}…`, "info");
    addLog(`${enable ? "Show" : "Hide"} env objects: ${label}`, "info");
    const data = await api("/env_objects/toggle", "POST", { label, enable });
    if (data.success) {
      toast(`✅ ${enable ? "Showed" : "Hid"} ${label} (${data.count} objects)`, "ok");
      addLog(`${enable ? "Shown" : "Hidden"}: ${label} — ${data.count} object(s)`, "ok");
    } else {
      toast("❌ Env toggle failed: " + data.error, "err", 5000);
      addLog("Env toggle error: " + data.error, "err");
    }
  }

  // ── Screenshot ─────────────────────────────────────────────────────────────
  async function takeScreenshot() {
    const btn = document.getElementById("ssBtn");
    const st  = document.getElementById("ssStatus");
    btn.disabled    = true;
    btn.textContent = "⏳ Capturing…";
    st.textContent  = "Spawning camera and capturing frame…";
    toast("📷 Capturing screenshot…", "info");
    addLog("Screenshot capture started", "info");

    const data = await api("/screenshot", "POST", {
      width:  parseInt(document.getElementById("ssW").value),
      height: parseInt(document.getElementById("ssH").value),
      fov:    parseInt(document.getElementById("ssFov").value),
    });
    btn.disabled    = false;
    btn.textContent = "📷 Capture";

    if (data.success) {
      screenshotB64 = data.image;
      const img = document.getElementById("screenshotImg");
      img.src           = "data:image/png;base64," + data.image;
      img.style.display = "block";
      document.getElementById("ssDownloadBtn").style.display = "inline-flex";
      st.textContent = `Captured ${data.width}×${data.height}`;
      toast(`✅ Screenshot ${data.width}×${data.height}`, "ok");
      addLog(`Screenshot captured — ${data.width}×${data.height}`, "ok");
    } else {
      st.textContent = "❌ Error: " + data.error;
      toast("❌ Screenshot failed: " + data.error, "err", 6000);
      addLog("Screenshot error: " + data.error, "err");
    }
  }

  function downloadScreenshot() {
    if (!screenshotB64) { toast("⚠️ No screenshot to download", "err"); return; }
    const a = document.createElement("a");
    a.href     = "data:image/png;base64," + screenshotB64;
    a.download = `carla_${Date.now()}.png`;
    a.click();
    toast("⬇ Downloading screenshot…", "ok");
    addLog("Screenshot downloaded", "info");
  }

  // ── Live Stream ────────────────────────────────────────────────────────────
  function startStream() {
    const img = document.getElementById("liveStream");
    img.src           = "/video_feed?" + new Date().getTime();
    img.style.display = "block";
    img.onerror = () => {
      toast("❌ Stream failed — check CARLA connection", "err", 6000);
      addLog("Live stream error — feed unavailable", "err");
      stopStream();
    };
    document.getElementById("liveStreamStatus").style.display = "none";
    document.getElementById("streamBtn").style.display        = "none";
    document.getElementById("streamStopBtn").style.display    = "block";
    toast("▶ Live stream started (1280×720 @ 30fps)", "ok");
    addLog("Live stream started", "info");
  }

  function stopStream() {
    const img = document.getElementById("liveStream");
    img.src           = "";
    img.style.display = "none";
    img.onerror       = null;
    document.getElementById("liveStreamStatus").style.display = "block";
    document.getElementById("streamBtn").style.display        = "block";
    document.getElementById("streamStopBtn").style.display    = "none";
    toast("⏹ Stream stopped", "info");
    addLog("Live stream stopped", "info");
  }