# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\camera.py
from flask import Blueprint, request, jsonify
import carla
import logging
import json
from config.state import carla_state, state_lock
from utils.helpers import get_world, get_spectator_transform, ensure_control
from core.camera import get_all_cameras, set_stream_source, stop_stream_camera
from core.database import get_connection

blueprint = Blueprint('camera', __name__)
logger = logging.getLogger(__name__)

@blueprint.route("/camera/list")
def list_cameras():
    try:
        world = get_world()
        cameras = get_all_cameras(world)
        return jsonify({"success": True, "cameras": cameras})
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
        if not bp: return jsonify({"success": False, "error": f"BP {bp_name} not found"})
        
        # Attributes
        bp.set_attribute("image_size_x", str(d.get("width", 1280)))
        bp.set_attribute("image_size_y", str(d.get("height", 720)))
        bp.set_attribute("fov", str(d.get("fov", 90)))
        
        # Transform (if provided, else spectator)
        if "x" in d:
            transform = carla.Transform(
                carla.Location(x=float(d["x"]), y=float(d["y"]), z=float(d["z"])),
                carla.Rotation(pitch=float(d["pitch"]), yaw=float(d["yaw"]), roll=float(d["roll"]))
            )
        else:
            transform = world.get_spectator().get_transform()
            
        camera = world.spawn_actor(bp, transform)
        return jsonify({"success": True, "actor_id": camera.id, "type": camera.type_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/camera/set_stream_source", methods=["POST"])
def set_stream():
    try:
        d = request.json or {}
        source_id = d.get("id") # None means spectator
        set_stream_source(source_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/camera/set_stream_resolution", methods=["POST"])
def set_stream_resolution():
    try:
        d = request.json or {}
        w = int(d.get("width", 640))
        h = int(d.get("height", 360))
        q = int(d.get("quality", 80))
        with state_lock:
            carla_state["stream_width"] = w
            carla_state["stream_height"] = h
            carla_state["stream_quality"] = q
            
        from core.camera import reset_spectator_camera
        reset_spectator_camera()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/camera/update", methods=["POST"])
@ensure_control
def update_camera():
    """Update camera location. Attributes (FOV/Size) require re-spawn."""
    try:
        d = request.json or {}
        world = get_world()
        actor = world.get_actor(int(d["id"]))
        if not actor: return jsonify({"success": False, "error": "Camera not found"})
        
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
        if not actor: return jsonify({"success": False, "error": "Camera not found"})
        
        # If this was the stream source, stop it properly
        from core.camera import _selected_id
        if actor_id == _selected_id:
            stop_stream_camera()
            
        if hasattr(actor, 'stop'):
            actor.stop()
        actor.destroy()
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
        if not parent: return jsonify({"success": False, "error": "Parent actor not found"})

        bp_name = d.get("blueprint", "sensor.camera.rgb")
        bpl = world.get_blueprint_library()
        bp = bpl.find(bp_name)
        
        # Set resolution
        bp.set_attribute("image_size_x", str(d.get("width", 800)))
        bp.set_attribute("image_size_y", str(d.get("height", 450)))
        
        # Default offset for third-person view
        x = float(d.get("x", -5.5))
        y = float(d.get("y", 0.0))
        z = float(d.get("z", 2.8))
        pitch = float(d.get("pitch", -15.0))
        
        transform = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch))
        camera = world.spawn_actor(bp, transform, attach_to=parent)
        
        return jsonify({"success": True, "actor_id": camera.id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/camera/setups", methods=["GET"])
def get_camera_setups():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT name, config, created_at FROM camera_setups ORDER BY created_at DESC")
        setups = [{"name": r["name"], "config": json.loads(r["config"]), "created_at": r["created_at"]} for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "setups": setups})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/camera/save_setup", methods=["POST"])
def save_camera_setup():
    try:
        d = request.json or {}
        name = d.get("name")
        if not name: return jsonify({"success": False, "error": "No name provided"})
        
        world = get_world()
        cameras = get_all_cameras(world)
        
        # We only want to save the configuration, not the dynamic state like is_streaming
        clean_configs = []
        for c in cameras:
            clean_configs.append({
                "type": c["type"],
                "x": c["x"], "y": c["y"], "z": c["z"],
                "pitch": c["pitch"], "yaw": c["yaw"], "roll": c["roll"],
                "width": c["width"], "height": c["height"], "fov": c["fov"]
            })
            
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO camera_setups (name, config) VALUES (?, ?)", (name, json.dumps(clean_configs)))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "count": len(clean_configs)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/camera/load_setup", methods=["POST"])
def load_camera_setup():
    try:
        d = request.json or {}
        name = d.get("name")
        if not name: return jsonify({"success": False, "error": "No name provided"})
        
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT config FROM camera_setups WHERE name = ?", (name,))
        row = c.fetchone()
        conn.close()
        
        if not row: return jsonify({"success": False, "error": "Setup not found"})
        configs = json.loads(row["config"])
        
        world = get_world()
        bpl = world.get_blueprint_library()
        
        spawned_count = 0
        for conf in configs:
            try:
                bp = bpl.find(conf["type"])
                if not bp: continue
                
                bp.set_attribute("image_size_x", str(conf.get("width", 1280)))
                bp.set_attribute("image_size_y", str(conf.get("height", 720)))
                bp.set_attribute("fov", str(conf.get("fov", 90)))
                
                transform = carla.Transform(
                    carla.Location(x=float(conf["x"]), y=float(conf["y"]), z=float(conf["z"])),
                    carla.Rotation(pitch=float(conf["pitch"]), yaw=float(conf["yaw"]), roll=float(conf["roll"]))
                )
                
                world.spawn_actor(bp, transform)
                spawned_count += 1
            except Exception as e:
                logger.warning(f"Failed to spawn camera in setup: {e}")
                
        return jsonify({"success": True, "spawned": spawned_count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
