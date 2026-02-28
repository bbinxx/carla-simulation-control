# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\main.py
from flask import Blueprint, request, jsonify, render_template, Response
import logging
import time
from config.state import carla_state, state_lock
from utils.helpers import get_world
from core.camera import get_stream_frame, ensure_stream_camera, stop_stream_camera, take_screenshot

blueprint = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@blueprint.route("/")
def index():
    return render_template("index.html")

@blueprint.route("/map/list")
def map_list():
    try:
        with state_lock:
            client = carla_state.get("client")
        if not client: return jsonify({"success": False, "error": "Not connected"})
        return jsonify({"success": True, "maps": sorted(client.get_available_maps())})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/map/load", methods=["POST"])
def map_load():
    try:
        map_name = (request.json or {}).get("map")
        if not map_name: return jsonify({"success": False, "error": "No map name"})
        with state_lock:
            client = carla_state.get("client")
        if not client: return jsonify({"success": False, "error": "Not connected"})
        
        stop_stream_camera()
        world = client.load_world(map_name)
        new_map = world.get_map().name
        
        with state_lock:
            carla_state["world"] = world
            carla_state["map"] = new_map
            
        return jsonify({"success": True, "map": new_map})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/debug/toggle_bboxes", methods=["POST"])
def toggle_bboxes():
    with state_lock:
        carla_state["debug_bboxes"] = not carla_state.get("debug_bboxes", False)
        enabled = carla_state["debug_bboxes"]
    return jsonify({"success": True, "enabled": enabled})

@blueprint.route("/screenshot", methods=["POST"])
def screenshot():
    try:
        d = request.json or {}
        world = get_world()
        data = take_screenshot(world, d.get("width", 1280), d.get("height", 720), d.get("fov", 90))
        if not data: return jsonify({"success": False, "error": "Capture failed"})
        return jsonify({"success": True, "image": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def _gen_frames():
    while True:
        frame = get_stream_frame()
        if frame:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(0.04)
        else:
            with state_lock:
                client = carla_state.get("client")
            if client: ensure_stream_camera(client)
            time.sleep(0.5)

@blueprint.route("/video_feed")
def video_feed():
    with state_lock:
        client = carla_state.get("client")
    if not client: return jsonify({"error": "Not connected"}), 400
    ensure_stream_camera(client)
    return Response(_gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")
