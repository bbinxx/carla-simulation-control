"""
MJPEG stream camera thread.

Spawns a single CARLA sensor.camera.rgb actor that follows the spectator
pawn every 100 ms so the live stream stays locked to where the user is looking.

Public API
----------
start_stream(client)  — spawn/start the camera (idempotent)
stop_stream()         — stop + destroy camera
get_frame()           — latest JPEG bytes (or None)
"""
import threading
import time
import logging

logger = logging.getLogger(__name__)

# ── module-level state ────────────────────────────────────────────────────────
_stream_frame = None
_stream_lock  = threading.Lock()

_stream_camera      = None
_stream_camera_lock = threading.Lock()

_stream_active = False


def get_frame():
    """Return the latest JPEG bytes captured from the stream camera, or None."""
    with _stream_lock:
        return _stream_frame


def _follow_spectator_loop():
    """Background micro-thread: sync camera transform to spectator every 100 ms."""
    from utils.cache import world_cache
    global _stream_active
    while _stream_active:
        try:
            with _stream_camera_lock:
                cam = _stream_camera
            if cam is not None and cam.is_alive:
                world = world_cache.get_world()
                if world:
                    t = world.get_spectator().get_transform()
                    cam.set_transform(t)
        except Exception:
            pass
        time.sleep(0.1)


def start_stream(client):
    """
    Spawn the spectator-follow stream camera.
    Idempotent — safe to call multiple times; does nothing if already running.
    """
    global _stream_camera, _stream_active, _stream_frame

    with _stream_camera_lock:
        if _stream_camera is not None:
            return   # already running

    try:
        import numpy as np
        import cv2
        from utils.cache import world_cache
        from config.state import carla_state, state_lock

        world = world_cache.get_world() or client.get_world()
        bpl   = world.get_blueprint_library()
        bp    = bpl.find("sensor.camera.rgb")

        with state_lock:
            fw = carla_state.get("stream_width",  640)
            fh = carla_state.get("stream_height", 360)
            fq = carla_state.get("stream_quality", 80)

        bp.set_attribute("image_size_x", str(fw))
        bp.set_attribute("image_size_y", str(fh))
        bp.set_attribute("fov",          "90")
        bp.set_attribute("sensor_tick",  "0.033")   # ~30 fps

        transform = world.get_spectator().get_transform()
        cam = world.spawn_actor(bp, transform)

        def on_frame(img):
            global _stream_frame
            try:
                import numpy as _np
                import cv2 as _cv2
                from config.state import carla_state as _state, state_lock as _lock
                arr = _np.frombuffer(img.raw_data, dtype=_np.uint8)
                arr = arr.reshape((img.height, img.width, 4))
                with _lock:
                    q = _state.get("stream_quality", 80)
                ok, buf = _cv2.imencode(".jpg", arr[:, :, :3],
                                        [_cv2.IMWRITE_JPEG_QUALITY, q])
                if ok:
                    with _stream_lock:
                        _stream_frame = buf.tobytes()
            except Exception:
                pass

        cam.listen(on_frame)

        with _stream_camera_lock:
            _stream_camera = cam

        _stream_active = True
        threading.Thread(target=_follow_spectator_loop, daemon=True,
                         name="stream-follow").start()
        logger.info("Stream camera started")

    except Exception as e:
        logger.error(f"Stream start error: {e}")


def stop_stream():
    """Stop and destroy the stream camera."""
    global _stream_camera, _stream_active, _stream_frame
    _stream_active = False

    with _stream_camera_lock:
        cam = _stream_camera
        _stream_camera = None

    if cam is not None:
        try:
            cam.stop()
            cam.destroy()
        except Exception:
            pass

    with _stream_lock:
        _stream_frame = None

    logger.info("Stream camera stopped")
