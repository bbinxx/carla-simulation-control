from flask import Blueprint, request, jsonify, render_template, Response
import logging
import time

from config.state import carla_state, state_lock
from utils.helpers import get_world, ensure_control, require_carla
from utils.cache import world_cache
from core.camera import (
    get_stream_frame, ensure_stream_camera, stop_stream_camera,
    take_screenshot, get_camera_status, stream_condition
)

blueprint = Blueprint("main", __name__)
logger    = logging.getLogger(__name__)


@blueprint.route("/")
def index():
    return render_template("index.html")


@blueprint.route("/map/list")
def map_list():
    try:
        with state_lock:
            client = carla_state.get("client")
        if not client:
            return jsonify({"success": False, "error": "Not connected"})
        return jsonify({"success": True, "maps": sorted(client.get_available_maps())})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/map/load", methods=["POST"])
@ensure_control
def map_load():
    try:
        map_name = (request.json or {}).get("map")
        if not map_name:
            return jsonify({"success": False, "error": "No map name"})
        with state_lock:
            client = carla_state.get("client")
        if not client:
            return jsonify({"success": False, "error": "Not connected"})

        stop_stream_camera()
        world_cache.invalidate()              # Evict stale world before load

        world    = client.load_world(map_name)
        new_map  = world.get_map().name
        world_cache.set_world(world)          # Prime cache with new world

        with state_lock:
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
@require_carla
def screenshot():
    d     = request.json or {}
    world = get_world()
    data  = take_screenshot(world,
                            d.get("width", 1280),
                            d.get("height", 720),
                            d.get("fov", 90))
    if not data:
        return jsonify({"success": False, "error": "Capture failed"})
    return jsonify({"success": True, "image": data})


# ── MJPEG helpers ─────────────────────────────────────────────────────────────

def _gen_frames(actor_id):
    """MJPEG generator – ensure_stream_camera was already called at request time."""
    last_count = -1
    missed = 0  # track consecutive timeouts for dead-connection detection
    while True:
        try:
            with stream_condition:
                # Wait for a new frame event (1 s timeout as heartbeat)
                stream_condition.wait(timeout=1.0)

            frame, count = get_stream_frame(actor_id)
            if frame and count != last_count:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                last_count = count
                missed = 0
            else:
                missed += 1
                if missed > 30:   # ~30 s with no frames → give up
                    logger.warning(f"MJPEG feed for id={actor_id} timed out, closing.")
                    return
        except GeneratorExit:
            return
        except Exception as exc:
            logger.warning(f"MJPEG gen_frames error: {exc}")
            return


@blueprint.route("/debug/streams")
def debug_streams():
    return jsonify(get_camera_status())


@blueprint.route("/health")
def health_check():
    import psutil
    import os
    process = psutil.Process(os.getpid())
    
    with state_lock:
        connected = carla_state.get("connected", False)
        host = carla_state.get("host", "N/A")
        port = carla_state.get("port", "N/A")
        map_name = carla_state.get("map", "N/A")

    return jsonify({
        "status": "online",
        "cpu_percent": psutil.cpu_percent(),
        "memory_mb": round(process.memory_info().rss / (1024 * 1024), 2),
        "carla": {
            "connected": connected,
            "host": host,
            "port": port,
            "map": map_name
        }
    })


@blueprint.route("/video_feed")
def video_feed():
    raw      = request.args.get("id", "")
    actor_id = int(raw) if raw.isdigit() else None

    with state_lock:
        client = carla_state.get("client")
    if not client:
        return "Not connected", 400

    ensure_stream_camera(client, actor_id)
    return Response(_gen_frames(actor_id),
                    mimetype="multipart/x-mixed-replace; boundary=frame")
