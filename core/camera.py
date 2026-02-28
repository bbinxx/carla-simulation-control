# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\core\camera.py
import carla
import cv2
import numpy as np
import threading
import time
import logging
import base64
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

# Streaming States
_stream_frame = None
_stream_lock  = threading.Lock()
_stream_camera = None
_stream_camera_lock = threading.Lock()

def get_stream_frame():
    with _stream_lock:
        return _stream_frame

def stop_stream_camera():
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

def ensure_stream_camera(client):
    global _stream_camera, _stream_frame
    with _stream_camera_lock:
        if _stream_camera is not None:
            try:
                world = client.get_world()
                _stream_camera.set_transform(world.get_spectator().get_transform())
            except: pass
            return
        try:
            world = client.get_world()
            bpl   = world.get_blueprint_library()
            bp    = bpl.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x",  "800")
            bp.set_attribute("image_size_y",  "450")
            bp.set_attribute("fov",           "90")
            bp.set_attribute("sensor_tick",   "0.04")

            transform = world.get_spectator().get_transform()
            cam = world.spawn_actor(bp, transform)

            def on_frame(img):
                global _stream_frame
                try:
                    cam.set_transform(world.get_spectator().get_transform())
                    arr = np.frombuffer(img.raw_data, dtype=np.uint8)
                    arr = arr.reshape((img.height, img.width, 4))
                    bgr = arr[:, :, :3]
                    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    with _stream_lock:
                        _stream_frame = buf.tobytes()
                except Exception as e:
                    logger.error(f"Stream callback error: {e}")

            cam.listen(on_frame)
            _stream_camera = cam
            logger.info("Live stream camera active")
        except Exception as e:
            logger.error(f"Stream camera spawn error: {e}")

def take_screenshot(world, width=1280, height=720, fov=90):
    """Temporary camera for a high-quality snapshot."""
    bpl = world.get_blueprint_library()
    bp = bpl.find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(width))
    bp.set_attribute("image_size_y", str(height))
    bp.set_attribute("fov", str(fov))

    spec_transform = world.get_spectator().get_transform()
    camera = world.spawn_actor(bp, spec_transform)
    
    image_event = threading.Event()
    captured = {}

    def on_image(img):
        if image_event.is_set(): return
        try:
            arr = np.frombuffer(img.raw_data, dtype=np.uint8)
            arr = np.reshape(arr, (img.height, img.width, 4))
            bgr = arr[:, :, :3]
            _, buf = cv2.imencode(".png", bgr)
            captured["data"] = base64.b64encode(buf).decode("utf-8")
        finally:
            image_event.set()

    camera.listen(on_image)
    image_event.wait(timeout=5.0)
    camera.stop()
    camera.destroy()
    return captured.get("data")
