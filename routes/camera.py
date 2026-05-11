from flask import Blueprint, request, jsonify
import carla
import logging
import json
from config.state import carla_state, state_lock
from utils.helpers import get_world, get_spectator_transform, ensure_control
from core.camera import (
    get_all_cameras, set_stream_source, stop_stream_camera,
    ensure_stream_camera, get_camera_status
)
from core.database import get_connection

blueprint = Blueprint('camera', __name__)
logger = logging.getLogger(__name__)


@blueprint.route("/camera/list")
def list_cameras():
    try:
        world = get_world()
        cameras = get_all_cameras(world)
        
        # Merge with metadata (names and directions)
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id, name, direction FROM camera_metadata")
        meta = {r["actor_id"]: {"name": r["name"], "direction": r["direction"]} for r in c.fetchall()}
        conn.close()
        
        for cam in cameras:
            m = meta.get(cam["id"], {})
            cam["name"] = m.get("name", f"Sensor #{cam['id']}")
            cam["direction"] = m.get("direction")
            
        return jsonify({"success": True, "cameras": cameras})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/rename", methods=["POST"])
def rename_camera():
    try:
        d = request.json or {}
        actor_id = int(d.get("id"))
        name = d.get("name", "").strip()
        
        if not name:
            return jsonify({"success": False, "error": "No name provided"})
            
        conn = get_connection()
        c = conn.cursor()
        # Check if exists to avoid wiping direction
        c.execute("SELECT actor_id FROM camera_metadata WHERE actor_id = ?", (actor_id,))
        if c.fetchone():
            c.execute("UPDATE camera_metadata SET name = ? WHERE actor_id = ?", (name, actor_id))
        else:
            c.execute("INSERT INTO camera_metadata (actor_id, name) VALUES (?, ?)", (actor_id, name))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "id": actor_id, "name": name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/set_direction", methods=["POST"])
def set_direction():
    try:
        d = request.json or {}
        actor_id = int(d.get("id"))
        direction = d.get("direction") # N, S, E, W, or None
        
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id FROM camera_metadata WHERE actor_id = ?", (actor_id,))
        if c.fetchone():
            c.execute("UPDATE camera_metadata SET direction = ? WHERE actor_id = ?", (direction, actor_id))
        else:
            c.execute("INSERT INTO camera_metadata (actor_id, name, direction) VALUES (?, ?, ?)", 
                      (actor_id, f"Sensor #{actor_id}", direction))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "id": actor_id, "direction": direction})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/spawn", methods=["POST"])
@ensure_control
def spawn_camera():
    try:
        d = request.json or {}
        world = get_world()

        bp_name = d.get("blueprint", "sensor.camera.rgb")
        bpl = world.get_blueprint_library()
        bp = bpl.find(bp_name)
        if not bp:
            return jsonify({"success": False, "error": f"Blueprint '{bp_name}' not found"})

        # Attributes
        bp.set_attribute("image_size_x", str(d.get("width",  1280)))
        bp.set_attribute("image_size_y", str(d.get("height",  720)))
        bp.set_attribute("fov",          str(d.get("fov",      90)))
        bp.set_attribute("sensor_tick",  "0.033")

        # Transform — use provided coords or fall back to spectator
        if "x" in d:
            transform = carla.Transform(
                carla.Location(x=float(d["x"]), y=float(d["y"]), z=float(d["z"])),
                carla.Rotation(pitch=float(d.get("pitch", 0)),
                               yaw=float(d.get("yaw", 0)),
                               roll=float(d.get("roll", 0)))
            )
        else:
            transform = world.get_spectator().get_transform()

        camera = world.spawn_actor(bp, transform)
        
        # Prevent "out of scope" warnings by registering immediately
        from core.camera import _camera_registry, _registry_lock
        with _registry_lock:
            _camera_registry[camera.id] = camera
            
        logger.info(f"Spawned camera #{camera.id} ({bp_name})")
        return jsonify({"success": True, "actor_id": camera.id, "type": camera.type_id})
    except Exception as e:
        logger.error(f"Spawn camera error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/set_stream_source", methods=["POST"])
def set_stream():
    try:
        d = request.json or {}
        raw = d.get("id")
        source_id = int(raw) if raw is not None else None

        set_stream_source(source_id)

        # If source is a real camera, attach a listener immediately
        if source_id is not None:
            with state_lock:
                client = carla_state.get("client")
            if client:
                ensure_stream_camera(client, source_id)

        return jsonify({"success": True, "selected_id": source_id})
    except Exception as e:
        logger.error(f"set_stream_source error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/set_stream_resolution", methods=["POST"])
def set_stream_resolution():
    try:
        d = request.json or {}
        w = int(d.get("width",   640))
        h = int(d.get("height",  360))
        q = int(d.get("quality",  30))
        with state_lock:
            carla_state["stream_width"]   = w
            carla_state["stream_height"]  = h
            carla_state["stream_quality"] = q

        # Destroy spectator camera so it respawns at the new resolution
        from core.camera import reset_spectator_camera
        reset_spectator_camera()

        # Re-spawn immediately if connected
        with state_lock:
            client = carla_state.get("client")
        if client:
            ensure_stream_camera(client, None)

        return jsonify({"success": True, "width": w, "height": h, "quality": q})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/update", methods=["POST"])
@ensure_control
def update_camera():
    """Update camera transform (location + rotation) in place."""
    try:
        d = request.json or {}
        actor_id = int(d.get("id"))
        world  = get_world()
        actor  = world.get_actor(actor_id)
        if not actor or not actor.is_alive:
            return jsonify({"success": False, "error": "Camera not found or dead"})

        transform = carla.Transform(
            carla.Location(x=float(d["x"]), y=float(d["y"]), z=float(d["z"])),
            carla.Rotation(pitch=float(d["pitch"]), yaw=float(d["yaw"]), roll=float(d["roll"]))
        )
        actor.set_transform(transform)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/stop_stream", methods=["POST"])
def stop_stream_api():
    stop_stream_camera()
    return jsonify({"success": True})


@blueprint.route("/camera/delete", methods=["POST"])
@ensure_control
def delete_camera():
    try:
        d = request.json or {}
        actor_id = int(d.get("id"))
        world = get_world()
        actor = world.get_actor(actor_id)
        if not actor:
            return jsonify({"success": False, "error": "Camera not found"})

        # If this was the selected stream source, clear it
        from core.camera import _selected_id, _selected_id_lock, _listener_actors, _listeners_lock
        with _selected_id_lock:
            was_selected = (_selected_id == actor_id)
        if was_selected:
            set_stream_source(None)

        # Remove from all registries so GC can collect
        with _listeners_lock:
            _listener_actors.pop(actor_id, None)
        
        from core.camera import _camera_registry, _registry_lock
        with _registry_lock:
            _camera_registry.pop(actor_id, None)

        # Metadata cleanup
        try:
            conn = get_connection()
            conn.execute("DELETE FROM camera_metadata WHERE actor_id = ?", (actor_id,))
            conn.commit()
            conn.close()
        except: pass

        # Stop and destroy
        success = False
        try:
            if hasattr(actor, 'stop'):
                try: actor.stop()
                except: pass
            actor.destroy()
            success = True
        except Exception as e:
            logger.warning(f"Primary destroy failed for #{actor_id}: {e}")

        # Fallback: Batch destruction
        with state_lock:
            client = carla_state.get("client")
        if client:
            try:
                client.apply_batch_sync([carla.command.DestroyActor(actor_id)], True)
                success = True
            except Exception as e:
                logger.warning(f"Batch destroy failed for #{actor_id}: {e}")

        if success:
            logger.info(f"Destroyed camera #{actor_id}")
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Destruction failed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/attach", methods=["POST"])
@ensure_control
def attach_camera():
    try:
        d = request.json or {}
        parent_id = int(d.get("parent_id"))
        world = get_world()
        parent = world.get_actor(parent_id)
        if not parent:
            return jsonify({"success": False, "error": "Parent actor not found"})

        bp_name = d.get("blueprint", "sensor.camera.rgb")
        bpl = world.get_blueprint_library()
        bp = bpl.find(bp_name)
        if not bp:
            return jsonify({"success": False, "error": f"Blueprint '{bp_name}' not found"})

        bp.set_attribute("image_size_x", str(d.get("width",  800)))
        bp.set_attribute("image_size_y", str(d.get("height", 450)))
        bp.set_attribute("sensor_tick",  "0.033")

        # Default offset for third-person view
        x     = float(d.get("x",     -5.5))
        y     = float(d.get("y",      0.0))
        z     = float(d.get("z",      2.8))
        pitch = float(d.get("pitch", -15.0))

        transform = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch))
        camera = world.spawn_actor(bp, transform, attach_to=parent)
        logger.info(f"Attached camera #{camera.id} to actor #{parent_id}")
        return jsonify({"success": True, "actor_id": camera.id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
#  Camera Setup (presets) CRUD
# ─────────────────────────────────────────────────────────────────────────────

@blueprint.route("/camera/setups", methods=["GET"])
def get_camera_setups():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT name, config, created_at FROM camera_setups ORDER BY created_at DESC")
        setups = [
            {"name": r["name"], "config": json.loads(r["config"]), "created_at": r["created_at"]}
            for r in c.fetchall()
        ]
        conn.close()
        return jsonify({"success": True, "setups": setups})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/save_setup", methods=["POST"])
def save_camera_setup():
    try:
        d = request.json or {}
        name = d.get("name")
        if not name:
            return jsonify({"success": False, "error": "No name provided"})

        world = get_world()
        cameras = get_all_cameras(world)

        clean_configs = [
            {
                "type":   c["type"],
                "x":      c["x"],   "y": c["y"],   "z": c["z"],
                "pitch":  c["pitch"], "yaw": c["yaw"], "roll": c["roll"],
                "width":  c["width"], "height": c["height"], "fov": c["fov"],
            }
            for c in cameras
        ]

        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO camera_setups (name, config) VALUES (?, ?)",
            (name, json.dumps(clean_configs))
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "count": len(clean_configs)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/delete_setup", methods=["POST"])
def delete_camera_setup():
    """Delete a saved camera setup by name."""
    try:
        d = request.json or {}
        name = d.get("name")
        if not name:
            return jsonify({"success": False, "error": "No name provided"})

        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM camera_setups WHERE name = ?", (name,))
        rows = c.rowcount
        conn.commit()
        conn.close()
        if rows == 0:
            return jsonify({"success": False, "error": f"Setup '{name}' not found"})
        return jsonify({"success": True, "deleted": name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/load_setup", methods=["POST"])
def load_camera_setup():
    try:
        d = request.json or {}
        name = d.get("name")
        if not name:
            return jsonify({"success": False, "error": "No name provided"})

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT config FROM camera_setups WHERE name = ?", (name,))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Setup not found"})
        configs = json.loads(row["config"])

        world = get_world()
        bpl = world.get_blueprint_library()

        spawned_count = 0
        for conf in configs:
            try:
                bp = bpl.find(conf["type"])
                if not bp:
                    continue
                bp.set_attribute("image_size_x", str(conf.get("width",  1280)))
                bp.set_attribute("image_size_y", str(conf.get("height",  720)))
                bp.set_attribute("fov",          str(conf.get("fov",      90)))
                bp.set_attribute("sensor_tick",  "0.033")

                transform = carla.Transform(
                    carla.Location(x=float(conf["x"]), y=float(conf["y"]), z=float(conf["z"])),
                    carla.Rotation(pitch=float(conf["pitch"]), yaw=float(conf["yaw"]), roll=float(conf["roll"]))
                )
                world.spawn_actor(bp, transform)
                spawned_count += 1
            except Exception as e:
                logger.warning(f"Failed to spawn camera in setup '{name}': {e}")

        return jsonify({"success": True, "spawned": spawned_count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/camera/live_links")
def live_links():
    """Returns a list of all camera live links, ordered NSEW, using network IP."""
    try:
        import socket
        def get_ip():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('10.255.255.255', 1))
                IP = s.getsockname()[0]
            except Exception:
                IP = '127.0.0.1'
            finally:
                s.close()
            return IP

        ip = get_ip()
        world = get_world()
        if not world:
            return "<h2>Error: CARLA World not available</h2><p>Please ensure you are connected to a CARLA server first.</p>", 400
            
        cameras = get_all_cameras(world)
        
        # Merge with metadata (names and directions)
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id, name, direction FROM camera_metadata")
        meta = {r["actor_id"]: {"name": r["name"], "direction": r["direction"]} for r in c.fetchall()}
        conn.close()
        
        for cam in cameras:
            m = meta.get(cam["id"], {})
            cam["name"] = m.get("name", f"Sensor #{cam['id']}")
            cam["direction"] = m.get("direction")
            cam["link"] = f"http://{ip}:5000/video_feed?id={cam['id']}"

        def get_sort_key(cam):
            # 1. Explicit Direction assignment
            d = (cam.get("direction") or "").upper()
            if d == "N": return 0
            if d == "S": return 1
            if d == "E": return 2
            if d == "W": return 3

            # 2. Name-based fallback
            name = cam["name"].upper()
            if "NORTH" in name: return 0
            if "SOUTH" in name: return 1
            if "EAST" in name:  return 2
            if "WEST" in name:  return 3
            
            # 3. Orientation-based fallback
            yaw = cam.get("yaw", 0)
            if -135 < yaw <= -45: return 0
            if 45 < yaw <= 135:   return 1
            if -45 < yaw <= 45:    return 2
            return 3

        cameras.sort(key=get_sort_key)

        # Build a premium-looking HTML response for easy copying
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Camera Live Links - NSEW</title>
    <style>
        :root {{
            --bg: #0a0b10;
            --card-bg: rgba(255, 255, 255, 0.03);
            --accent: #00e87a;
            --text: #e0e0e0;
            --link: #00d4ff;
            --border: rgba(255, 255, 255, 0.1);
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .container {{
            max-width: 800px;
            width: 100%;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        h1 {{
            color: var(--accent);
            font-size: 1.5rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 0;
        }}
        .ip-badge {{
            display: inline-block;
            background: rgba(0, 232, 122, 0.1);
            color: var(--accent);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            margin-top: 10px;
            border: 1px solid var(--accent);
        }}
        .link-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .link-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 16px 20px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.2s ease;
        }}
        .link-card:hover {{
            background: rgba(255, 255, 255, 0.05);
            border-color: var(--accent);
            transform: translateX(4px);
        }}
        .cam-info {{
            display: flex;
            flex-direction: column;
        }}
        .cam-name {{
            font-weight: bold;
            color: #ffca28;
            font-size: 0.9rem;
            text-transform: uppercase;
        }}
        .cam-id {{
            font-size: 0.7rem;
            color: rgba(255, 255, 255, 0.4);
            font-family: monospace;
        }}
        .link-container {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .link-text {{
            color: var(--link);
            font-family: 'Share Tech Mono', monospace;
            font-size: 0.95rem;
            background: rgba(0, 0, 0, 0.3);
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            user-select: all;
            border: 1px solid rgba(0, 212, 255, 0.2);
        }}
        .copy-btn {{
            background: var(--accent);
            color: #000;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.7rem;
            cursor: pointer;
            text-transform: uppercase;
        }}
        .copy-btn:active {{
            transform: scale(0.95);
        }}
        .copy-all-btn {{
            background: var(--accent);
            color: #000;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 0.9rem;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 232, 122, 0.2);
        }}
        .copy-all-btn:hover {{
            background: #00ff85;
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 232, 122, 0.3);
        }}
        .copy-all-btn.success {{
            background: #ffca28;
            box-shadow: 0 4px 15px rgba(255, 202, 40, 0.2);
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: rgba(255, 255, 255, 0.3);
            font-size: 0.75rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Camera Stream Hub</h1>
            <div class="ip-badge">NETWORK IP: {ip}</div>
            <div style="margin-top: 20px;">
                <button class="copy-all-btn" onclick="copyAll()">COPY ALL LINKS (NSEW)</button>
            </div>
        </div>
        
        <div class="link-list">
            {"".join([f'''
            <div class="link-card">
                <div class="cam-info">
                    <span class="cam-name">{c["name"]}</span>
                    <span class="cam-id">ID: #{c["id"]} | YAW: {c["yaw"]:.1f}°</span>
                </div>
                <div class="link-container">
                    <span class="link-text" onclick="copyText(this)">{c["link"]}</span>
                    <button class="copy-btn" onclick="copyText(this.previousElementSibling)">Copy</button>
                </div>
            </div>
            ''' for c in cameras])}
        </div>
        
        <div class="footer">
            Ordered by NSEW configuration. Click "COPY ALL" to get all links at once.
        </div>
    </div>

    <script>
        function fallbackCopyTextToClipboard(text) {{
            var textArea = document.createElement("textarea");
            textArea.value = text;
            
            // Avoid scrolling to bottom
            textArea.style.top = "0";
            textArea.style.left = "0";
            textArea.style.position = "fixed";

            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();

            try {{
                var successful = document.execCommand('copy');
                var msg = successful ? 'successful' : 'unsuccessful';
                console.log('Fallback: Copying text command was ' + msg);
                return successful;
            }} catch (err) {{
                console.error('Fallback: Oops, unable to copy', err);
                return false;
            }} finally {{
                document.body.removeChild(textArea);
            }}
        }}

        function copyToClipboard(text) {{
            if (!navigator.clipboard) {{
                return Promise.resolve(fallbackCopyTextToClipboard(text));
            }}
            return navigator.clipboard.writeText(text).then(() => true).catch(() => fallbackCopyTextToClipboard(text));
        }}

        function copyText(el) {{
            const text = el.innerText || el.textContent;
            copyToClipboard(text).then((success) => {{
                if (!success) return;
                const original = el.innerText;
                if (el.tagName === 'BUTTON') {{
                    el.innerText = 'COPIED!';
                    setTimeout(() => el.innerText = original, 1500);
                }} else {{
                    const btn = el.nextElementSibling;
                    btn.innerText = 'COPIED!';
                    setTimeout(() => btn.innerText = 'COPY', 1500);
                }}
            }});
        }}

        function copyAll() {{
            const links = Array.from(document.querySelectorAll('.link-text'))
                               .map(el => el.innerText.trim());
            const text = links.join('\\n');
            copyToClipboard(text).then((success) => {{
                if (!success) return;
                const btn = document.querySelector('.copy-all-btn');
                const original = btn.innerText;
                btn.innerText = 'ALL LINKS COPIED!';
                btn.classList.add('success');
                setTimeout(() => {{
                    btn.innerText = original;
                    btn.classList.remove('success');
                }}, 2000);
            }});
        }}
    </script>
</body>
</html>
        """
        return html
    except Exception as e:
        logger.error(f"live_links error: {e}")
        return f"Error: {str(e)}", 500
