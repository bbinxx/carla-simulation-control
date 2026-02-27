
    // --- SQL Database History ---
    let serverLocations = {};

    async function initHistory() {
      try {
        const res = await api("/history", "GET");
        if (res.success) {
          const hosts = res.hosts || [];
          const dl = document.getElementById("hostHistory");
          if (dl) dl.innerHTML = hosts.map(h => `<option value="${h.host}">`).join("");

          if (res.last_connection) {
            if (document.getElementById("hostInput")) document.getElementById("hostInput").value = res.last_connection.host;
            if (document.getElementById("portInput")) document.getElementById("portInput").value = res.last_connection.port;
          }

          serverLocations = res.locations || {};
          renderSavedLocations();
        }
      } catch (e) { console.error("Failed to load DB history", e); }
    }

    async function saveHostHistory(host, port) {
      await api("/history/host", "POST", { host, port });
      initHistory();
    }

    function renderSavedLocations() {
      const sel = document.getElementById("savedLocations");
      if (!sel) return;
      sel.innerHTML = '<option value="">-- Load Location --</option>' +
        Object.keys(serverLocations).map(k => `<option value="${k}">${k}</option>`).join("");
    }

    async function saveSpectatorPosition() {
      const name = document.getElementById("locName").value || "Location " + new Date().toLocaleTimeString();
      const payload = {
        name: name,
        x: document.getElementById("sX").textContent,
        y: document.getElementById("sY").textContent,
        z: document.getElementById("sZ").textContent,
        pitch: document.getElementById("sPitch").textContent,
        yaw: document.getElementById("sYaw").textContent,
        roll: document.getElementById("sRoll").textContent,
      };

      const res = await api("/history/location", "POST", payload);
      if (res.success) {
        toast(`Saved to DB: ${name}`, "ok");
        document.getElementById("locName").value = "";
        initHistory();
      } else {
        toast("Failed to save location", "err");
      }
    }

    function loadSpectatorPosition(name) {
      if (!name) return;
      const loc = serverLocations[name];
      if (loc) {
        document.getElementById("specX").value = loc.x;
        document.getElementById("specY").value = loc.y;
        document.getElementById("specZ").value = loc.z;
        document.getElementById("specPitch").value = loc.pitch;
        document.getElementById("specYaw").value = loc.yaw;
        document.getElementById("specRoll").value = loc.roll;
        moveSpectator();
      }
      document.getElementById("savedLocations").value = "";
    }

    document.addEventListener("DOMContentLoaded", initHistory);

    let pollInterval = null;
    let weatherValues = {};
    let screenshotB64 = null;

    const weatherParams = [
      { key: "cloudiness", label: "Cloudiness", min: 0, max: 100 },
      { key: "precipitation", label: "Precipitation", min: 0, max: 100 },
      { key: "precipitation_deposits", label: "Precip. Deposits", min: 0, max: 100 },
      { key: "wind_intensity", label: "Wind Intensity", min: 0, max: 100 },
      { key: "sun_azimuth_angle", label: "Sun Azimuth", min: 0, max: 360 },
      { key: "sun_altitude_angle", label: "Sun Altitude", min: -90, max: 90 },
      { key: "fog_density", label: "Fog Density", min: 0, max: 100 },
      { key: "fog_distance", label: "Fog Distance", min: 0, max: 200 },
      { key: "wetness", label: "Wetness", min: 0, max: 100 },
    ];

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

    function switchTab(name, el) {
      document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.getElementById("tab-" + name).classList.add("active");
      el.classList.add("active");
      if (name === "traffic") loadTrafficLights();
    }

    function toast(msg, type = "info") {
      const t = document.getElementById("toast");
      t.textContent = msg; t.className = "show " + type;
      clearTimeout(window._tt);
      window._tt = setTimeout(() => t.className = "", 3200);
    }

    function addLog(msg, type = "info") {
      const box = document.getElementById("logBox");
      const ts = new Date().toLocaleTimeString();
      const e = document.createElement("div");
      e.className = `log-entry log-${type}`;
      e.textContent = `[${ts}] ${msg}`;
      box.appendChild(e); box.scrollTop = box.scrollHeight;
    }
    function clearLog() { document.getElementById("logBox").innerHTML = ""; }

    function syncColor(el) {
      const hex = el.value;
      const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
      document.getElementById("colorText").value = `${r},${g},${b}`;
    }
    function syncColorText(el) {
      const p = el.value.split(",").map(Number);
      if (p.length === 3 && p.every(n => !isNaN(n))) {
        document.getElementById("colorPicker").value = "#" + p.map(n => Math.min(255, Math.max(0, n)).toString(16).padStart(2, "0")).join("");
      }
    }

    async function api(path, method = "GET", body = null) {
      const opts = { method, headers: { "Content-Type": "application/json" } };
      if (body) opts.body = JSON.stringify(body);
      const res = await fetch(path, opts);
      return res.json();
    }

    // ── Connect ──
    async function connect() {
      const host = document.getElementById("hostInput").value.trim();
      const port = document.getElementById("portInput").value;
      const timeout = document.getElementById("timeoutInput").value;
      if (!host) { toast("Enter a host address", "err"); return; }
      document.getElementById("connectBtn").disabled = true;
      document.getElementById("connectBtn").textContent = "Connecting…";
      addLog(`Connecting to ${host}:${port}…`, "info");
      const data = await api("/connect", "POST", { host, port, timeout });
      document.getElementById("connectBtn").disabled = false;
      document.getElementById("connectBtn").textContent = "⚡ Connect";
      if (data.success) {
        setConnected(true, data);
        saveHostHistory(host, port);
        toast(`Connected — ${data.map}`, "ok");
        addLog(`Connected. Map: ${data.map}`, "ok");
        loadMaps(); loadBlueprints(); loadAllBlueprints(); startPolling();
      } else {
        toast("Connection failed: " + data.error, "err");
        addLog("Error: " + data.error, "err");
      }
    }

    async function disconnect() {
      clearInterval(pollInterval);
      stopStream();
      await api("/disconnect", "POST");
      setConnected(false);
      toast("Disconnected", "info");
      addLog("Disconnected", "warn");
    }

    async function toggleDebugBboxes() {
      const btn = document.getElementById("debugBoxesBtn");
      try {
        const res = await api("/debug/toggle_bboxes", "POST");
        if (res.success) {
          btn.textContent = res.enabled ? "🔲 Hide Debug BBoxes" : "🔳 Show Debug BBoxes";
          toast(res.enabled ? "Debug BBoxes ENABLED" : "Debug BBoxes DISABLED", "info");
        }
      } catch (e) {
        toast("Failed to toggle bboxes", "error");
      }
    }

    function setConnected(state, data = {}) {
      const badge = document.getElementById("statusBadge");
      badge.className = "status-badge " + (state ? "connected" : "disconnected");
      document.getElementById("statusText").textContent = state ? `${data.host}:${data.port}` : "Disconnected";
      ["connectBtn"].forEach(id => document.getElementById(id).style.display = state ? "none" : "block");
      ["disconnectBtn", "serverInfoCard", "mapCard", "spectatorLiveCard", "statsRow", "mainTabs", "screenshotBtn"]
        .forEach(id => document.getElementById(id).style.display = state ? "block" : "none");
      document.getElementById("disconnectedPlaceholder").style.display = state ? "none" : "flex";
      document.getElementById("statsRow").style.display = state ? "grid" : "none";
      if (state) {
        document.getElementById("infoHost").textContent = data.host;
        document.getElementById("infoPort").textContent = data.port;
        document.getElementById("infoMap").textContent = data.map || "—";
      }
    }

    // ── Poll ──
    function startPolling() { clearInterval(pollInterval); pollInterval = setInterval(refreshStatus, 3000); refreshStatus(); }

    async function refreshStatus() {
      const data = await api("/status");
      if (!data.connected) {
        setConnected(false); clearInterval(pollInterval);
        toast("Lost connection to CARLA", "err"); addLog("Connection lost", "err"); return;
      }
      document.getElementById("infoMap").textContent = data.map;
      document.getElementById("infoActors").textContent = data.actor_count;
      document.getElementById("statActors").textContent = data.actor_count;
      document.getElementById("statVehicles").textContent = data.vehicle_count;
      document.getElementById("statWalkers").textContent = data.walker_count;
      document.getElementById("statSensors").textContent = data.sensor_count;

      // spectator
      if (data.spectator) updateSpectatorDisplay(data.spectator);

      // actor table
      const tbody = document.getElementById("actorTableBody");
      if (!data.actors || data.actors.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:20px">No actors</td></tr>`;
      } else {
        tbody.innerHTML = data.actors.map(a => {
          let cls = "type-other";
          if (a.type.startsWith("vehicle")) cls = "type-vehicle";
          else if (a.type.startsWith("walker")) cls = "type-walker";
          else if (a.type.startsWith("sensor")) cls = "type-sensor";
          else if (a.type.includes("traffic")) cls = "type-tl";
          return `<tr>
        <td>${a.id}</td>
        <td><span class="type-badge ${cls}">${a.type.split(".").slice(0, 2).join(".")}</span></td>
        <td>${a.x}</td><td>${a.y}</td><td>${a.z}</td>
        <td><button class="btn btn-sm btn-danger" onclick="destroyActor(${a.id})">✕</button></td>
      </tr>`;
        }).join("");
      }
      if (data.weather) buildWeatherSliders(data.weather);
    }

    // ── Spectator ──
    function updateSpectatorDisplay(s) {
      document.getElementById("sX").textContent = s.x;
      document.getElementById("sY").textContent = s.y;
      document.getElementById("sZ").textContent = s.z;
      document.getElementById("sPitch").textContent = s.pitch;
      document.getElementById("sYaw").textContent = s.yaw;
      document.getElementById("sRoll").textContent = s.roll;
    }

    async function fetchSpectator() {
      const data = await api("/spectator/get");
      if (data.success) updateSpectatorDisplay(data);
    }

    async function moveSpectator() {
      const d = {
        x: parseFloat(document.getElementById("specX").value),
        y: parseFloat(document.getElementById("specY").value),
        z: parseFloat(document.getElementById("specZ").value),
        pitch: parseFloat(document.getElementById("specPitch").value),
        yaw: parseFloat(document.getElementById("specYaw").value),
        roll: parseFloat(document.getElementById("specRoll").value),
      };
      const data = await api("/spectator/set", "POST", d);
      if (data.success) { toast("Camera moved", "ok"); addLog(`Spectator → (${d.x},${d.y},${d.z})`, "ok"); }
      else { toast("Error: " + data.error, "err"); }
    }

    // ── Maps ──
    async function loadMaps() {
      const data = await api("/map/list");
      if (data.success) {
        document.getElementById("mapSelect").innerHTML = data.maps.map(m => `<option value="${m}">${m.split("/").pop()}</option>`).join("");
      }
    }

    async function loadMap() {
      const map = document.getElementById("mapSelect").value;
      toast("Loading map…", "info"); addLog(`Loading: ${map}`, "info");
      const data = await api("/map/load", "POST", { map });
      if (data.success) { toast(`Map: ${data.map}`, "ok"); addLog(`Map loaded: ${data.map}`, "ok"); }
      else { toast("Error: " + data.error, "err"); addLog("Map error: " + data.error, "err"); }
    }

    // ── Blueprints ──
    async function loadBlueprints() {
      const data = await api("/blueprints?filter=vehicle.*");
      if (data.success) document.getElementById("vehicleBp").innerHTML = data.blueprints.map(b => `<option value="${b}">${b}</option>`).join("");
    }

    async function loadAllBlueprints() {
      const data = await api("/blueprints?filter=*");
      if (data.success) document.getElementById("anyBp").innerHTML = data.blueprints.map(b => `<option value="${b}">${b}</option>`).join("");
    }

    async function filterBps() {
      const filt = document.getElementById("bpFilter").value || "*";
      const data = await api(`/blueprints?filter=${encodeURIComponent(filt)}`);
      if (data.success) document.getElementById("anyBp").innerHTML = data.blueprints.map(b => `<option value="${b}">${b}</option>`).join("");
    }

    // ── Spawn ──
    async function spawnVehicle() {
      const data = await api("/spawn/vehicle", "POST", {
        blueprint: document.getElementById("vehicleBp").value,
        color: document.getElementById("colorText").value,
        autopilot: document.getElementById("autopilotCb").checked,
        at_spectator: document.getElementById("atSpectatorCb").checked,
      });
      if (data.success) { toast(`Spawned ${data.blueprint}`, "ok"); addLog(`Spawned ID:${data.actor_id}`, "ok"); }
      else { toast("Error: " + data.error, "err"); addLog("Spawn error: " + data.error, "err"); }
    }

    async function spawnNPC() {
      const count = parseInt(document.getElementById("npcCount").value);
      const radius = parseFloat(document.getElementById("npcRadius").value);
      addLog(`Spawning ${count} NPCs…`, "info");
      const data = await api("/spawn/npc", "POST", { count, radius });
      if (data.success) { toast(`Spawned ${data.spawned} NPCs`, "ok"); addLog(`NPCs spawned: ${data.spawned}`, "ok"); }
      else { toast("Error: " + data.error, "err"); }
    }

    async function spawnWalkers() {
      const count = parseInt(document.getElementById("walkerCount").value);
      const data = await api("/spawn/walker", "POST", { count });
      if (data.success) { toast(`Spawned ${data.spawned} walkers`, "ok"); addLog(`Walkers: ${data.spawned}`, "ok"); }
      else { toast("Error: " + data.error, "err"); }
    }

    async function spawnCamera() {
      const data = await api("/spawn/camera", "POST", {
        width: parseInt(document.getElementById("camW").value),
        height: parseInt(document.getElementById("camH").value),
        fov: parseInt(document.getElementById("camFov").value),
      });
      if (data.success) { toast(`Camera spawned ID:${data.actor_id}`, "ok"); addLog(`Camera ID:${data.actor_id}`, "ok"); }
      else { toast("Error: " + data.error, "err"); }
    }

    async function spawnAny() {
      const data = await api("/spawn/any", "POST", {
        blueprint: document.getElementById("anyBp").value,
        z_offset: parseFloat(document.getElementById("anyZOffset").value),
        autopilot: document.getElementById("anyAutopilot").checked,
      });
      if (data.success) { toast(`Spawned ${data.blueprint}`, "ok"); addLog(`Spawned ID:${data.actor_id} ${data.blueprint}`, "ok"); }
      else { toast("Error: " + data.error, "err"); addLog("Error: " + data.error, "err"); }
    }

    // ── Destroy ──
    async function destroyFilter(filter) {
      const data = await api("/destroy/all", "POST", { filter });
      if (data.success) { toast(`Destroyed ${data.destroyed}`, "ok"); addLog(`Destroyed ${data.destroyed} (${filter})`, "warn"); }
      else { toast("Error: " + data.error, "err"); }
    }
    async function destroyActor(id) {
      const data = await api("/destroy/actor", "POST", { id });
      if (data.success) { toast(`Actor ${id} destroyed`, "ok"); addLog(`Destroyed actor ${id}`, "warn"); refreshStatus(); }
      else toast("Error: " + data.error, "err");
    }

    // ── Weather ──
    async function weatherPreset(preset) {
      const data = await api("/weather/preset", "POST", { preset });
      if (data.success) {
        toast(`Weather: ${preset}`, "ok"); addLog(`Preset: ${preset}`, "ok");
        if (data.values) buildWeatherSliders(data.values);
      } else { toast("Error: " + data.error, "err"); }
    }
    async function applyWeather() {
      const data = await api("/weather", "POST", weatherValues);
      if (data.success) { toast("Weather applied", "ok"); addLog("Custom weather applied", "ok"); }
      else { toast("Error: " + data.error, "err"); }
    }

    // ── Traffic Lights ──
    async function loadTrafficLights() {
      const radius = document.getElementById("tlRadius").value;
      const data = await api(`/traffic_lights?radius=${radius}`);
      const tbody = document.getElementById("tlTableBody");
      if (!data.success) { tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--red);padding:16px">${data.error}</td></tr>`; return; }
      if (data.lights.length === 0) { tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:16px">No lights within ${radius}m</td></tr>`; return; }
      tbody.innerHTML = data.lights.map(tl => {
        const s = tl.state.toLowerCase();
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
    }

    async function setTL(id, state) {
      const data = await api("/traffic_light/set", "POST", { id, state, freeze: true });
      if (data.success) { toast(`TL ${id} → ${state}`, "ok"); setTimeout(loadTrafficLights, 300); }
      else toast("Error: " + data.error, "err");
    }
    async function freezeTL(id) {
      const data = await api("/traffic_light/set", "POST", { id, freeze: true });
      if (data.success) toast(`TL ${id} frozen`, "ok");
      else toast("Error: " + data.error, "err");
    }
    async function freezeAll(state) {
      const data = await api("/traffic_light/freeze_all", "POST", { freeze: true, state });
      if (data.success) { toast(`All lights → ${state} (frozen)`, "ok"); addLog(`All TL → ${state}`, "ok"); setTimeout(loadTrafficLights, 400); }
      else toast("Error: " + data.error, "err");
    }
    async function unfreezeAll() {
      const data = await api("/traffic_light/freeze_all", "POST", { freeze: false });
      if (data.success) { toast("Traffic lights resumed", "ok"); addLog("TL unfrozen", "ok"); setTimeout(loadTrafficLights, 400); }
      else toast("Error: " + data.error, "err");
    }

    // ── Environment ──
    async function toggleEnvObject(enable) {
      const label = document.getElementById("envObjectSelect").value;
      const data = await api("/env_objects/toggle", "POST", { label, enable });
      if (data.success) {
        toast(`${enable ? 'Showed' : 'Hid'} ${label} (${data.count} objects)`, "ok");
        addLog(`${enable ? 'Show' : 'Hide'} ${label} (${data.count} objects)`, "info");
      } else {
        toast("Error: " + data.error, "err");
      }
    }

    // ── Screenshot ──
    async function takeScreenshot() {
      const btn = document.getElementById("ssBtn");
      const st = document.getElementById("ssStatus");
      btn.disabled = true; btn.textContent = "⏳ Capturing…"; st.textContent = "Spawning camera and capturing…";
      const data = await api("/screenshot", "POST", {
        width: parseInt(document.getElementById("ssW").value),
        height: parseInt(document.getElementById("ssH").value),
        fov: parseInt(document.getElementById("ssFov").value),
      });
      btn.disabled = false; btn.textContent = "📷 Capture";
      if (data.success) {
        screenshotB64 = data.image;
        const img = document.getElementById("screenshotImg");
        img.src = "data:image/png;base64," + data.image;
        img.style.display = "block";
        document.getElementById("ssDownloadBtn").style.display = "inline-flex";
        st.textContent = `Captured ${data.width}×${data.height}`;
        toast("Screenshot captured", "ok"); addLog(`Screenshot ${data.width}×${data.height}`, "ok");
      } else {
        st.textContent = "Error: " + data.error;
        toast("Screenshot error: " + data.error, "err");
        addLog("Screenshot error: " + data.error, "err");
      }
    }

    function downloadScreenshot() {
      if (!screenshotB64) return;
      const a = document.createElement("a");
      a.href = "data:image/png;base64," + screenshotB64;
      a.download = `carla_${Date.now()}.png`;
      a.click();
    }

    // ── Live Stream ──
    function startStream() {
      const img = document.getElementById("liveStream");
      img.src = "/video_feed?" + new Date().getTime();
      img.style.display = "block";
      document.getElementById("liveStreamStatus").style.display = "none";
      document.getElementById("streamBtn").style.display = "none";
      document.getElementById("streamStopBtn").style.display = "block";
      addLog("Started live video stream", "info");
    }

    function stopStream() {
      const img = document.getElementById("liveStream");
      img.src = "";
      img.style.display = "none";
      document.getElementById("liveStreamStatus").style.display = "block";
      document.getElementById("streamBtn").style.display = "block";
      document.getElementById("streamStopBtn").style.display = "none";
      addLog("Stopped live video stream", "info");
    }
  