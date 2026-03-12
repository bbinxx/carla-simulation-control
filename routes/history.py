# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\history.py
from flask import Blueprint, request, jsonify, current_app
import carla
import sqlite3

from config.state import carla_state, state_lock
from utils.helpers import get_world, get_actors_info, get_spectator_transform, format_weather
from core.database import get_connection

blueprint = Blueprint('history', __name__)

@blueprint.route("/history", methods=["GET"])
def get_history():
    try:
        conn = get_connection()
        c = conn.cursor()
        
        c.execute("SELECT host, port FROM hosts ORDER BY last_used DESC LIMIT 10")
        hosts = [{"host": r["host"], "port": r["port"]} for r in c.fetchall()]
        
        c.execute("SELECT * FROM locations ORDER BY name")
        locations = {}
        for r in c.fetchall():
            locations[r["name"]] = {"x": r["x"], "y": r["y"], "z": r["z"], "pitch": r["pitch"], "yaw": r["yaw"], "roll": r["roll"]}
            
        c.execute("SELECT host, port FROM last_connection WHERE id = 1")
        last_conn = c.fetchone()
        last = {"host": last_conn["host"], "port": last_conn["port"]} if last_conn else None
        
        conn.close()
        return jsonify({"success": True, "hosts": hosts, "locations": locations, "last_connection": last})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/history/host", methods=["POST"])
def save_host():
    try:
        d = request.json
        host = d.get("host")
        port = int(d.get("port", 2000))
        if not host: return jsonify({"success": False, "error": "No host"})
        
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO hosts (host, port, last_used) VALUES (?, ?, CURRENT_TIMESTAMP)", (host, port))
        c.execute("INSERT OR REPLACE INTO last_connection (id, host, port) VALUES (1, ?, ?)", (host, port))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/history/location", methods=["POST"])
def save_location():
    try:
        d = request.json
        name = d.get("name")
        if not name: return jsonify({"success": False, "error": "No name"})
        
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO locations (name, x, y, z, pitch, yaw, roll) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (name, float(d.get("x",0)), float(d.get("y",0)), float(d.get("z",0)), float(d.get("pitch",0)), float(d.get("yaw",0)), float(d.get("roll",0))))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/connect", methods=["POST"])
def connect():
    data = request.json
    host = data.get("host", "localhost")
    port = int(data.get("port", 2000))
    timeout = float(data.get("timeout", 10.0))

    try:
        from core.camera import stop_stream_camera
        stop_stream_camera()
        
        client = carla.Client(host, port)
        client.set_timeout(timeout)

        world = client.get_world()
        map_name = world.get_map().name

        # Sync Mode Settings — 30Hz physics + substepping for max smoothness
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.033   # 30 Hz (was 20 Hz)
        settings.substepping = True
        settings.max_substep_delta_time = 0.01
        settings.max_substeps = 10
        world.apply_settings(settings)

        # Traffic Manager Setup
        tm = client.get_trafficmanager(8000)
        from core.vehicles import sync_global_tm
        
        # Update state partially so sync_global_tm finds the TM
        with state_lock:
            carla_state["tm"] = tm
            
        sync_global_tm(world)
        tm_port = tm.get_port()
        world.tick()

        with state_lock:
            carla_state.update({
                "client": client, "world": world, "connected": True,
                "host": host, "port": port, "map": map_name,
                "tm": tm, "tm_port": tm_port,
            })

        current_app.logger.info(f"Connected to CARLA {host}:{port}")
        return jsonify({"success": True, "map": map_name, "host": host, "port": port})

    except Exception as e:
        current_app.logger.error(f"Failed to connect: {e}")
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/disconnect", methods=["POST"])
def disconnect():
    with state_lock:
        carla_state.update({"client": None, "world": None, "connected": False, "host": "", "map": ""})
    return jsonify({"success": True})

@blueprint.route("/status")
def status():
    try:
        world = get_world()
        actors = get_actors_info(world)
        spec = get_spectator_transform(world)
        
        with state_lock:
            host = carla_state.get("host")
            port = carla_state.get("port")
            map_name = carla_state.get("map")

        veh_count = sum(1 for a in actors if a["type"] == "vehicle")
        wlk_count = sum(1 for a in actors if a["type"] == "walker")
        sns_count = sum(1 for a in actors if a["type"] == "sensor")

        return jsonify({
            "connected": True, "host": host, "port": port, "map": map_name,
            "actor_count": len(actors),
            "vehicle_count": veh_count,
            "walker_count": wlk_count,
            "sensor_count": sns_count,
            "actors": actors[:80],
            "weather": format_weather(world.get_weather()),
            "spectator": spec,
        })
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})
