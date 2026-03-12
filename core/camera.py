# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\core\camera.py
import cv2
import base64
import numpy as np
import threading
import logging
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

# ── Frame Store ───────────────────────────────────────────────────────────────
# { actor_id (int or None) : latest jpeg bytes }
# None key = internal spectator-follow camera
_frames      = {}
_frame_counters = {}
_frames_lock = threading.Lock()

# ── Active Listeners ──────────────────────────────────────────────────────────
# { actor_id (int) : actor_object }  — holds strong refs so GC won't drop them
_listener_actors  = {}
_listeners_lock   = threading.Lock()

# ── Internal Spectator Camera ─────────────────────────────────────────────────
_spec_camera      = None
_spec_camera_lock = threading.Lock()

# ── Dashboard "selected" stream id ────────────────────────────────────────────
_selected_id      = None   # int or None
_selected_id_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
#  Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def set_stream_source(actor_id):
    """Set the dashboard's 'main' camera. actor_id is int or None."""
    global _selected_id
    with _selected_id_lock:
        _selected_id = actor_id


def get_stream_frame(actor_id=None):
    """
    Return the latest JPEG bytes for the requested actor_id.
    Pass actor_id=None to get the dashboard / selected stream.
    """
    with _selected_id_lock:
        sid = _selected_id

    target = actor_id if actor_id is not None else sid
    with _frames_lock:
        return _frames.get(target), _frame_counters.get(target, 0)


def reset_streams():
    """Called on connect/disconnect to purge all state."""
    global _spec_camera, _selected_id
    # Stop internal camera
    with _spec_camera_lock:
        if _spec_camera is not None:
            try:
                _spec_camera.stop()
                _spec_camera.destroy()
            except Exception:
                pass
            _spec_camera = None
    # Wipe frames and listeners
    with _frames_lock:
        _frames.clear()
        _frame_counters.clear()
    with _listeners_lock:
        _listener_actors.clear()
    with _selected_id_lock:
        _selected_id = None
    logger.info("Camera streams reset")

# keep old name for compatibility
stop_stream_camera = reset_streams

def reset_spectator_camera():
    """Destroy spectator so it respawns with new settings."""
    global _spec_camera
    with _spec_camera_lock:
        if _spec_camera is not None:
            try:
                _spec_camera.stop()
                _spec_camera.destroy()
            except Exception:
                pass
            _spec_camera = None


# ─────────────────────────────────────────────────────────────────────────────
#  Frame callback factory
# ─────────────────────────────────────────────────────────────────────────────

def _make_callback(key):
    """Returns a CARLA listen() callback that encodes BGR→JPEG into _frames[key]."""
    def _on_frame(img):
        try:
            arr = np.frombuffer(img.raw_data, dtype=np.uint8).reshape((img.height, img.width, 4))
            ok, buf = cv2.imencode(".jpg", arr[:, :, :3], [cv2.IMWRITE_JPEG_QUALITY, 50])
            if ok:
                with _frames_lock:
                    _frames[key] = buf.tobytes()
                    _frame_counters[key] = _frame_counters.get(key, 0) + 1
        except Exception as exc:
            logger.warning(f"Frame encode error (id={key}): {exc}")
    return _on_frame


# ─────────────────────────────────────────────────────────────────────────────
#  Ensure a camera is streaming
# ─────────────────────────────────────────────────────────────────────────────

def ensure_stream_camera(client, actor_id=None):
    """
    Attach a CARLA listen() callback for actor_id if not already active.
    actor_id=None → spawn/maintain the internal spectator-follow camera.
    """
    with _selected_id_lock:
        sid = _selected_id

    target = actor_id if actor_id is not None else sid

    # ── External actor ────────────────────────────────────────────────────────
    if target is not None:
        with _listeners_lock:
            if target in _listener_actors:
                return  # already streaming, actor ref kept alive

        try:
            world  = client.get_world()
            actor  = world.get_actor(target)
            if not actor or not actor.is_alive:
                logger.warning(f"Camera #{target} not found or dead")
                return

            logger.info(f"Attaching stream listener to camera #{target}")
            actor.listen(_make_callback(target))

            with _listeners_lock:
                _listener_actors[target] = actor  # keep strong ref
        except Exception as exc:
            logger.error(f"Failed to attach listener to #{target}: {exc}")
        return

    # ── Internal spectator camera ─────────────────────────────────────────────
    with _spec_camera_lock:
        global _spec_camera
        if _spec_camera is not None:
            try:
                if _spec_camera.is_alive:
                    world = client.get_world()
                    _spec_camera.set_transform(world.get_spectator().get_transform())
                    return
            except Exception:
                pass
            # camera is dead – clean up and respawn below
            _spec_camera = None

        try:
            world = client.get_world()
            bp    = world.get_blueprint_library().find("sensor.camera.rgb")
            with state_lock:
                fw = carla_state.get("stream_width", 640)
                fh = carla_state.get("stream_height", 360)
            bp.set_attribute("image_size_x", str(fw))
            bp.set_attribute("image_size_y", str(fh))
            cam   = world.spawn_actor(bp, world.get_spectator().get_transform())

            spectator = world.get_spectator()

            def _on_spec_frame(img):
                # Follow spectator every frame – cheap transform update
                try:
                    with _selected_id_lock:
                        sel = _selected_id
                    if sel is None:
                        cam.set_transform(spectator.get_transform())
                    arr = np.frombuffer(img.raw_data, dtype=np.uint8).reshape((img.height, img.width, 4))
                    ok, buf = cv2.imencode(".jpg", arr[:, :, :3], [cv2.IMWRITE_JPEG_QUALITY, 50])
                    if ok:
                        with _frames_lock:
                            _frames[None] = buf.tobytes()
                            _frame_counters[None] = _frame_counters.get(None, 0) + 1
                except Exception:
                    pass

            cam.listen(_on_spec_frame)
            _spec_camera = cam
            logger.info("Spectator stream camera spawned")
        except Exception as exc:
            logger.error(f"Failed to spawn spectator camera: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  Camera list / control helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_all_cameras(world):
    with _selected_id_lock:
        sid = _selected_id
    cameras = []
    for actor in world.get_actors().filter("sensor.camera.*"):
        t = actor.get_transform()
        cameras.append({
            "id":           actor.id,
            "type":         actor.type_id,
            "x":            round(t.location.x,  2),
            "y":            round(t.location.y,  2),
            "z":            round(t.location.z,  2),
            "pitch":        round(t.rotation.pitch, 2),
            "yaw":          round(t.rotation.yaw,   2),
            "roll":         round(t.rotation.roll,  2),
            "is_streaming": (actor.id == sid),
            "has_feed":     (actor.id in _listener_actors),
        })
    return cameras


def take_screenshot(world, width=1280, height=720, fov=90):
    """Spawn a temporary camera, capture one PNG frame, destroy it."""
    import threading as _t
    bpl = world.get_blueprint_library()
    bp  = bpl.find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(width))
    bp.set_attribute("image_size_y", str(height))
    bp.set_attribute("fov",          str(fov))

    camera = world.spawn_actor(bp, world.get_spectator().get_transform())
    ev     = _t.Event()
    result = {}

    def _on_image(img):
        if ev.is_set():
            return
        try:
            arr = np.frombuffer(img.raw_data, dtype=np.uint8).reshape((img.height, img.width, 4))
            _, buf = cv2.imencode(".png", arr[:, :, :3])
            result["data"] = base64.b64encode(buf).decode("utf-8")
        finally:
            ev.set()

    camera.listen(_on_image)
    ev.wait(timeout=5.0)
    camera.stop()
    camera.destroy()
    return result.get("data")
