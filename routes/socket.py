import logging
import threading
import time
import json
import os
import psutil
from flask import request, current_app
from flask_socketio import join_room, leave_room, emit
from config.socket import socketio
from config.state import carla_state, state_lock
from utils.cache import world_cache
from utils.helpers import get_spectator_transform

logger = logging.getLogger(__name__)

# --- State for Delta Broadcasting ---
_last_status = {}
_last_status_lock = threading.Lock()

@socketio.on('connect')
def on_connect():
    logger.info(f"Socket connected: {request.sid}")
    # Send immediate status on connect
    _broadcast_status(single_sid=request.sid)

@socketio.on('disconnect')
def on_disconnect():
    logger.info(f"Socket disconnected: {request.sid}")

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room')
    if room:
        join_room(room)
        logger.info(f"Client {request.sid} joined room {room}")

@socketio.on('leave_room')
def on_leave_room(data):
    room = data.get('room')
    if room:
        leave_room(room)
        logger.info(f"Client {request.sid} left room {room}")

@socketio.on('join_camera')
def on_join_camera(data):
    cam_id = data.get('id')
    room = f"camera_{cam_id}" if cam_id is not None else "camera_selected"
    join_room(room)
    logger.info(f"Client {request.sid} joined room {room}")

@socketio.on('leave_camera')
def on_leave_camera(data):
    cam_id = data.get('id')
    room = f"camera_{cam_id}" if cam_id is not None else "camera_selected"
    leave_room(room)
    logger.info(f"Client {request.sid} left room {room}")

@socketio.on('api_command')
def on_api_command(data):
    """Generic API command handler over sockets with fast-path for common calls."""
    path = data.get("path")
    method = data.get("method", "GET")
    body = data.get("body", {})

    # Fast-path for health/status to avoid test_client overhead
    if path == "/health":
        process = psutil.Process(os.getpid())
        return {
            "status": "online",
            "cpu_percent": psutil.cpu_percent(),
            "memory_mb": round(process.memory_info().rss / (1024 * 1024), 2)
        }

    try:
        with current_app.test_client() as client:
            if method == "POST":
                response = client.post(path, json=body)
            else:
                response = client.get(path, query_string=body)
            return response.get_json()
    except Exception as e:
        logger.error(f"Socket API Error ({path}): {e}")
        return {"success": False, "error": str(e)}

# --- Broadcasting Logic ---

def _broadcast_status(single_sid=None):
    """Constructs and emits simulation status. If single_sid is set, only sends to that client."""
    from routes.connection import _weather_dict
    global _last_status
    
    try:
        with state_lock:
            connected = carla_state.get("connected", False)
            client_obj = carla_state.get("client")
            host = carla_state.get("host")
            port = carla_state.get("port")
            map_name = carla_state.get("map")

        if not connected or not client_obj:
            payload = {"connected": False}
            if single_sid: socketio.emit('status_update', payload, to=single_sid)
            else: socketio.emit('status_update', payload)
            return

        world = world_cache.get_world() or client_obj.get_world()
        actors = world_cache.get_actors(world)

        v_count = sum(1 for a in actors if a.type_id.startswith("vehicle."))
        w_count = sum(1 for a in actors if a.type_id.startswith("walker."))
        s_count = sum(1 for a in actors if a.type_id.startswith("sensor."))

        process = psutil.Process(os.getpid())
        
        status = {
            "connected": True,
            "host": host,
            "port": port,
            "map": map_name,
            "actor_count": v_count + w_count + s_count,
            "vehicle_count": v_count,
            "walker_count": w_count,
            "sensor_count": s_count,
            "spectator": get_spectator_transform(world),
            "weather": _weather_dict(world.get_weather()),
            "health": {
                "cpu": psutil.cpu_percent(),
                "ram": round(process.memory_info().rss / (1024 * 1024), 2)
            },
            "traffic_lights": [],
            "ts": time.time()
        }

        # Add nearby traffic lights (within 200m)
        spec_loc = world.get_spectator().get_location()
        for a in actors:
            if "traffic_light" in a.type_id:
                loc = a.get_location()
                dist = spec_loc.distance(loc)
                if dist <= 200:
                    status["traffic_lights"].append({
                        "id": a.id,
                        "state": str(a.get_state()).split(".")[-1].lower(),
                        "distance": round(dist, 1)
                    })
        status["traffic_lights"].sort(key=lambda x: x["distance"])

        if single_sid:
            socketio.emit('status_update', status, to=single_sid)
        else:
            # Broadcast to everyone
            socketio.emit('status_update', status)
            
            # High-frequency room for spectator transform only (~10Hz)
            # This is handled separately in _spectator_broadcast_loop
            
    except Exception as e:
        logger.debug(f"Broadcast error: {e}")

def _status_broadcast_loop():
    """Background thread to push status to all connected clients every 1 second."""
    while True:
        _broadcast_status()
        time.sleep(1.0)

def _spectator_broadcast_loop():
    """High-frequency broadcast of spectator transform to 'spectator' room (~10Hz)."""
    while True:
        try:
            with state_lock:
                connected = carla_state.get("connected", False)
                client_obj = carla_state.get("client")
            
            if connected and client_obj:
                world = world_cache.get_world() or client_obj.get_world()
                transform = get_spectator_transform(world)
                if transform:
                    socketio.emit('spectator_update', transform, room='spectator')
        except:
            pass
        time.sleep(0.1)

# Start background broadcast threads
threading.Thread(target=_status_broadcast_loop, daemon=True, name="socket-status").start()
threading.Thread(target=_spectator_broadcast_loop, daemon=True, name="socket-spectator").start()
