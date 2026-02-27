from flask import Blueprint, request, jsonify, render_template, current_app, Response
import carla
import base64
import time
import logging
import numpy as np
import threading
import cv2

from config.state import carla_state, state_lock

blueprint = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

# ── Live stream globals ──────────────────────────────────────────────────────
_stream_frame = None
_stream_lock  = threading.Lock()
_stream_camera = None
_stream_camera_lock = threading.Lock()


@blueprint.route("/")
def index():
    return render_template("index.html")


# ── Map ───────────────────────────────────────────────────────────────────────
@blueprint.route("/map/list")
def map_list():
    try:
        with state_lock:
            client = carla_state.get("client")
        if not client:
            return jsonify({"success": False, "error": "Not connected to CARLA"})
        maps = sorted(client.get_available_maps())
        logger.info(f"Available maps: {len(maps)}")
        return jsonify({"success": True, "maps": maps})
    except Exception as e:
        logger.error(f"/map/list error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/map/load", methods=["POST"])
def map_load():
    try:
        map_name = (request.json or {}).get("map")
        if not map_name:
            return jsonify({"success": False, "error": "No map name provided"})
        with state_lock:
            client = carla_state.get("client")
        if not client:
            return jsonify({"success": False, "error": "Not connected to CARLA"})
        # Stop stream camera before loading (world gets destroyed)
        _stop_stream_camera()
        logger.info(f"Loading map: {map_name}")
        world = client.load_world(map_name)
        new_map = world.get_map().name
        with state_lock:
            carla_state["world"] = world
            carla_state["map"]   = new_map
        logger.info(f"Map loaded: {new_map}")
        return jsonify({"success": True, "map": new_map})
    except Exception as e:
        logger.error(f"/map/load error: {e}")
        return jsonify({"success": False, "error": str(e)})


# ── Debug BBoxes ──────────────────────────────────────────────────────────────
@blueprint.route("/debug/toggle_bboxes", methods=["POST"])
def toggle_bboxes():
    try:
        with state_lock:
            current = carla_state.get("debug_bboxes", False)
            carla_state["debug_bboxes"] = not current
            enabled = carla_state["debug_bboxes"]
        logger.info(f"Debug BBoxes: {'ON' if enabled else 'OFF'}")
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        logger.error(f"/debug/toggle_bboxes error: {e}")
        return jsonify({"success": False, "error": str(e)})


# ── Screenshot ────────────────────────────────────────────────────────────────
@blueprint.route("/screenshot", methods=["POST"])
def screenshot():
    camera = None
    try:
        d = request.json or {}
        width  = int(d.get("width",  1280))
        height = int(d.get("height", 720))
        fov    = int(d.get("fov",    90))

        with state_lock:
            client = carla_state.get("client")
        if not client:
            return jsonify({"success": False, "error": "Not connected to CARLA"})

        world = client.get_world()
        bpl   = world.get_blueprint_library()
        bp    = bpl.find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(width))
        bp.set_attribute("image_size_y", str(height))
        bp.set_attribute("fov",          str(fov))

        spec_transform = world.get_spectator().get_transform()
        camera = world.spawn_actor(bp, spec_transform)

        image_event = threading.Event()
        captured    = {}

        def on_image(img):
            # Raw BGRA → RGB
            arr = np.frombuffer(img.raw_data, dtype=np.uint8)
            arr = arr.reshape((img.height, img.width, 4))
            bgr = arr[:, :, :3]           # drop alpha – already BGR order from CARLA
            captured["img"] = bgr
            captured["w"]   = img.width
            captured["h"]   = img.height
            image_event.set()

        camera.listen(on_image)
        got = image_event.wait(timeout=10.0)
        camera.stop()
        camera.destroy()
        camera = None

        if not got or "img" not in captured:
            return jsonify({"success": False, "error": "Timeout waiting for camera frame"})

        _, buf = cv2.imencode(".png", captured["img"],
                              [cv2.IMWRITE_PNG_COMPRESSION, 3])
        b64 = base64.b64encode(buf).decode("utf-8")
        logger.info(f"Screenshot captured {captured['w']}×{captured['h']}")
        return jsonify({"success": True, "image": b64,
                        "width": captured["w"], "height": captured["h"]})
    except Exception as e:
        logger.error(f"/screenshot error: {e}")
        if camera:
            try:
                camera.stop()
                camera.destroy()
            except Exception as ce:
                logger.warning(f"Camera cleanup error: {ce}")
        return jsonify({"success": False, "error": str(e)})


# ── MJPEG live stream ─────────────────────────────────────────────────────────
def _gen_frames():
    while True:
        with _stream_lock:
            frame = _stream_frame
        if frame is not None:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.033)   # ~30 fps cap


@blueprint.route("/video_feed")
def video_feed():
    with state_lock:
        client = carla_state.get("client")
        connected = carla_state.get("connected", False)
    if not connected or not client:
        return jsonify({"error": "Not connected to CARLA"}), 400
    _ensure_stream_camera(client)
    return Response(_gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


def _stop_stream_camera():
    global _stream_camera, _stream_frame
    with _stream_camera_lock:
        if _stream_camera is not None:
            try:
                _stream_camera.stop()
                _stream_camera.destroy()
                logger.info("Stream camera stopped")
            except Exception as e:
                logger.warning(f"Stream camera stop error: {e}")
            _stream_camera = None
    with _stream_lock:
        _stream_frame = None


def _ensure_stream_camera(client):
    global _stream_camera, _stream_frame
    with _stream_camera_lock:
        if _stream_camera is not None:
            return
        try:
            world = client.get_world()
            bpl   = world.get_blueprint_library()
            bp    = bpl.find("sensor.camera.rgb")
            # Max quality settings
            bp.set_attribute("image_size_x",  "1280")
            bp.set_attribute("image_size_y",  "720")
            bp.set_attribute("fov",           "90")
            bp.set_attribute("sensor_tick",   "0.033")  # ~30 fps

            transform = world.get_spectator().get_transform()
            cam = world.spawn_actor(bp, transform)

            def on_frame(img):
                global _stream_frame
                # CARLA gives BGRA raw_data — correct color order for cv2 (BGR)
                arr = np.frombuffer(img.raw_data, dtype=np.uint8)
                arr = arr.reshape((img.height, img.width, 4))
                bgr = arr[:, :, :3]   # drop alpha, keep BGR — correct for imencode
                _, buf = cv2.imencode(".jpg", bgr,
                                      [cv2.IMWRITE_JPEG_QUALITY, 90])
                with _stream_lock:
                    _stream_frame = buf.tobytes()

            cam.listen(on_frame)
            _stream_camera = cam
            logger.info("Stream camera spawned at spectator position")
        except Exception as e:
            logger.error(f"Stream camera spawn error: {e}")
