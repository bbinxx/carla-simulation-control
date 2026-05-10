# d:\MAIN_PRO\carla-simulation-control\core\camera.py
import cv2
import base64
import numpy as np
import threading
import time
import logging
from config.state import carla_state, state_lock
from config.socket import socketio

logger = logging.getLogger(__name__)

# ── Frame Store ───────────────────────────────────────────────────────────────
# { actor_id (int or None) : latest jpeg bytes }
# None key = internal spectator-follow camera
_frames         = {}
_frame_counters = {}
_frames_lock    = threading.Lock()
stream_condition = threading.Condition()

# ── Active Listeners ──────────────────────────────────────────────────────────
# { actor_id (int) : actor_object }  — holds strong refs so GC won't drop them
_listener_actors = {}
_listeners_lock  = threading.Lock()

# ── Internal Spectator Camera ─────────────────────────────────────────────────
_spec_camera      = None
_spec_camera_lock = threading.Lock()
_spec_follow_active = False

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
    global _spec_camera, _selected_id, _spec_follow_active
    _spec_follow_active = False

    # Stop internal spectator camera
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
            with state_lock:
                qlty = carla_state.get("stream_quality", 30)
            ok, buf = cv2.imencode(".jpg", arr[:, :, :3], [cv2.IMWRITE_JPEG_QUALITY, qlty])
            if ok:
                jpeg_bytes = buf.tobytes()
                with _frames_lock:
                    _frames[key] = jpeg_bytes
                    _frame_counters[key] = _frame_counters.get(key, 0) + 1

                with stream_condition:
                    stream_condition.notify_all()

                # Emit over Socket.IO (Binary payload for better performance)
                try:
                    room = f"camera_{key}" if key is not None else "camera_selected"
                    socketio.emit("frame", {"id": key, "data": jpeg_bytes}, room=room)
                except Exception:
                    pass  # Avoid crashing callback if socketio fails
        except Exception as exc:
            logger.warning(f"Frame encode error (id={key}): {exc}")
    return _on_frame


# ─────────────────────────────────────────────────────────────────────────────
#  Spectator-follow background thread
# ─────────────────────────────────────────────────────────────────────────────

def _spectator_follow_loop():
    """Sync the internal spectator camera transform to the CARLA spectator every 80ms."""
    from utils.cache import world_cache
    global _spec_follow_active
    logger.info("Spectator follow loop started")
    while _spec_follow_active:
        try:
            with _spec_camera_lock:
                cam = _spec_camera
            if cam is not None:
                try:
                    if cam.is_alive:
                        world = world_cache.get_world()
                        if world:
                            t = world.get_spectator().get_transform()
                            cam.set_transform(t)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.08)  # ~12 Hz position updates
    logger.info("Spectator follow loop stopped")


# ─────────────────────────────────────────────────────────────────────────────
#  Ensure a camera is streaming
# ─────────────────────────────────────────────────────────────────────────────

def ensure_stream_camera(client, actor_id=None):
    """
    Attach a CARLA listen() callback for actor_id if not already active.
    actor_id=None → spawn/maintain the internal spectator-follow camera.
    """
    global _spec_camera, _spec_follow_active

    with _selected_id_lock:
        sid = _selected_id

    target = actor_id if actor_id is not None else sid

    # ── External actor ────────────────────────────────────────────────────────
    if target is not None:
        with _listeners_lock:
            existing = _listener_actors.get(target)

        if existing is not None:
            # Verify the actor is still alive
            try:
                if existing.is_alive:
                    return  # already streaming
            except Exception:
                pass
            # Actor died — clean up stale reference
            with _listeners_lock:
                _listener_actors.pop(target, None)

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
        if _spec_camera is not None:
            try:
                if _spec_camera.is_alive:
                    return  # already running fine
            except Exception:
                pass
            # Camera is dead — clean up and fall through to respawn
            try:
                _spec_camera.stop()
                _spec_camera.destroy()
            except Exception:
                pass
            _spec_camera = None

        try:
            world = client.get_world()
            bpl   = world.get_blueprint_library()
            bp    = bpl.find("sensor.camera.rgb")

            with state_lock:
                fw = carla_state.get("stream_width",  640)
                fh = carla_state.get("stream_height", 360)

            bp.set_attribute("image_size_x", str(fw))
            bp.set_attribute("image_size_y", str(fh))
            bp.set_attribute("fov",          "90")
            bp.set_attribute("sensor_tick",  "0.033")  # ~30 fps

            transform = world.get_spectator().get_transform()
            cam = world.spawn_actor(bp, transform)

            cam.listen(_make_callback(None))
            _spec_camera = cam
            logger.info("Spectator stream camera spawned")

            # Start follow thread if not running
            if not _spec_follow_active:
                _spec_follow_active = True
                threading.Thread(
                    target=_spectator_follow_loop,
                    daemon=True,
                    name="spec-follow"
                ).start()

        except Exception as exc:
            logger.error(f"Failed to spawn spectator camera: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  Camera list / control helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_all_cameras(world):
    """Return list of all camera/sensor actors — excludes the internal spectator cam."""
    with _selected_id_lock:
        sid = _selected_id
    # Get the internal spectator camera id to exclude it from the list
    with _spec_camera_lock:
        spec_id = _spec_camera.id if _spec_camera is not None else None

    cameras = []
    for actor in world.get_actors().filter("sensor.camera.*"):
        # Exclude the internal spectator-follow camera
        if spec_id is not None and actor.id == spec_id:
            continue

        t = actor.get_transform()
        cam = {
            "id":        actor.id,
            "type":      actor.type_id,
            "x":         round(t.location.x,   2),
            "y":         round(t.location.y,   2),
            "z":         round(t.location.z,   2),
            "pitch":     round(t.rotation.pitch, 2),
            "yaw":       round(t.rotation.yaw,   2),
            "roll":      round(t.rotation.roll,  2),
            "parent_id": actor.parent.id if actor.parent else None,
        }

        # Safely extract camera attributes (width, height, fov)
        width, height, fov = 1280, 720, 90.0
        attrs = getattr(actor, 'attributes', [])

        if isinstance(attrs, dict):
            width  = int(attrs.get("image_size_x", width))
            height = int(attrs.get("image_size_y", height))
            fov    = float(attrs.get("fov", fov))
        else:
            for a in attrs:
                try:
                    name = getattr(a, 'name', None)
                    if name == "image_size_x":  width  = int(a.value)
                    elif name == "image_size_y": height = int(a.value)
                    elif name == "fov":          fov    = float(a.value)
                except (ValueError, TypeError, AttributeError):
                    continue

        cam.update({
            "width":        width,
            "height":       height,
            "fov":          fov,
            "is_streaming": (actor.id == sid),
            "has_feed":     (actor.id in _listener_actors),
        })
        cameras.append(cam)

    return cameras


def get_camera_status():
    """Return streaming diagnostics for debug endpoint."""
    with _selected_id_lock:
        sid = _selected_id
    with _spec_camera_lock:
        spec_alive = _spec_camera is not None and _spec_camera.is_alive
    with _listeners_lock:
        listener_ids = list(_listener_actors.keys())
    with _frames_lock:
        frame_ids = [str(k) for k in _frames.keys()]
        frame_sizes = {str(k): len(v) for k, v in _frames.items()}
    return {
        "selected_id":     sid,
        "spec_cam_alive":  spec_alive,
        "spec_follow_active": _spec_follow_active,
        "listeners":       sorted(listener_ids),
        "frame_ids":       sorted(frame_ids),
        "frame_sizes":     frame_sizes,
    }


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
