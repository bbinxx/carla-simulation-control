import logging
import threading
import time
import json
from flask import request, current_app
from flask_socketio import join_room, leave_room
from config.socket import socketio
from config.state import carla_state, state_lock
from utils.cache import world_cache
from utils.helpers import get_spectator_transform

logger = logging.getLogger(__name__)

@socketio.on('connect')
def on_connect():
    logger.info(f"Socket connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    logger.info(f"Socket disconnected: {request.sid}")

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
    """
    Generic API command handler over sockets.
    data = { "path": "/spawn/vehicle", "method": "POST", "body": {...} }
    """
    path = data.get("path")
    method = data.get("method", "GET")
    body = data.get("body", {})

    logger.info(f"Socket API Command: {method} {path}")
    
    # We use the test_client to internally route the request to the Flask blueprints
    # without making actual HTTP network calls.
    with current_app.test_client() as client:
        if method == "POST":
            response = client.post(path, json=body)
        else:
            response = client.get(path, query_string=body)
        
        return response.get_json()

def _status_broadcast_loop():
    """Background thread to push status to all connected clients every 2 seconds."""
    from routes.connection import _weather_dict
    
    while True:
        try:
            with state_lock:
                connected = carla_state.get("connected", False)
                client_obj = carla_state.get("client")
                host = carla_state.get("host")
                port = carla_state.get("port")
                map_name = carla_state.get("map")

            if connected and client_obj:
                world = world_cache.get_world() or client_obj.get_world()
                actors = world_cache.get_actors(world)

                v_count = sum(1 for a in actors if a.type_id.startswith("vehicle."))
                w_count = sum(1 for a in actors if a.type_id.startswith("walker."))
                s_count = sum(1 for a in actors if a.type_id.startswith("sensor."))

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
                }
                socketio.emit('status_update', status)
            else:
                socketio.emit('status_update', {"connected": False})
        except Exception as e:
            pass
        time.sleep(2.0)

# Start status broadcast thread
threading.Thread(target=_status_broadcast_loop, daemon=True, name="socket-status").start()
