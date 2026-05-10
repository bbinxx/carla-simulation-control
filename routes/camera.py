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
        
        # Merge with metadata (names)
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id, name FROM camera_metadata")
        names = {r["actor_id"]: r["name"] for r in c.fetchall()}
        conn.close()
        
        for cam in cameras:
            cam["name"] = names.get(cam["id"], f"Sensor #{cam['id']}")
            
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
        c.execute("INSERT OR REPLACE INTO camera_metadata (actor_id, name) VALUES (?, ?)", (actor_id, name))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "id": actor_id, "name": name})
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

        # Remove listener reference so GC can collect
        with _listeners_lock:
            _listener_actors.pop(actor_id, None)

        # Cleanup metadata
        try:
            conn = get_connection()
            conn.execute("DELETE FROM camera_metadata WHERE actor_id = ?", (actor_id,))
            conn.commit()
            conn.close()
        except: pass

        if hasattr(actor, 'stop'):
            try:
                actor.stop()
            except Exception:
                pass
        actor.destroy()
        logger.info(f"Destroyed camera #{actor_id}")
        return jsonify({"success": True})
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


@blueprint.route("/camera/status")
def camera_status():
    """Debug endpoint — returns camera streaming status."""
    try:
        return jsonify({"success": True, **get_camera_status()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
