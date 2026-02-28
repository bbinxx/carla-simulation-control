# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\history.py
from flask import Blueprint, request, jsonify, render_template, current_app
import carla
import sqlite3
import random
import time
import base64
import numpy as np
import cv2

from config.state import carla_state, state_lock, DB_PATH
from utils.helpers import get_world, get_actors_info, get_spectator_transform, make_weather, TL_STATE_MAP, WEATHER_PRESETS

blueprint = Blueprint('history', __name__)


def _weather_dict(w):
    return {
        "cloudiness": round(w.cloudiness, 2),
        "precipitation": round(w.precipitation, 2),
        "precipitation_deposits": round(w.precipitation_deposits, 2),
        "wind_intensity": round(w.wind_intensity, 2),
        "sun_azimuth_angle": round(w.sun_azimuth_angle, 2),
        "sun_altitude_angle": round(w.sun_altitude_angle, 2),
        "fog_density": round(w.fog_density, 2),
        "fog_distance": round(w.fog_distance, 2),
        "wetness": round(w.wetness, 2),
    }


@blueprint.route("/history", methods=["GET"])
def get_history():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
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
        if not host:
            return jsonify({"success": False, "error": "No host"})
        
        conn = sqlite3.connect(DB_PATH)
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
        if not name:
            return jsonify({"success": False, "error": "No name"})
        
        conn = sqlite3.connect(DB_PATH)
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
    data    = request.json
    host    = data.get("host", "localhost")
    port    = int(data.get("port", 2000))
    timeout = float(data.get("timeout", 10.0))
    try:
        client = carla.Client(host, port)
        client.set_timeout(timeout)

        # ── Traffic Manager: strict real-life settings ─────────────────────
        tm = client.get_trafficmanager(8000)
        
        world    = client.get_world()
        map_name = world.get_map().name

        # Critical: TM sync mode must exactly match server sync mode, 
        # otherwise vehicles skip physics ticks and blow through red lights.
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05  # Forces simulation to run at a steady 20 FPS
        world.apply_settings(settings)
        tm.set_synchronous_mode(True)

        # Slow them down slightly so they have time to react at junctions
        tm.global_percentage_speed_difference(20.0)

        # Increase gap to 3.5 or 4.0 meters
        tm.set_global_distance_to_leading_vehicle(4.0)

        # Global fallbacks: 100% obey lights, signs, and vehicles
        # Note: TrafficManager doesn't have a global set_ignore_lights_percentage
        # so this must be handled entirely on the per-vehicle basis when spawned.

        tm_port = tm.get_port()

        with state_lock:
            carla_state.update({
                "client":   client,
                "world":    world,
                "connected":True,
                "host":     host,
                "port":     port,
                "map":      map_name,
                "tm":       tm,
                "tm_port":  tm_port,
            })
        current_app.logger.info(
            f"Connected to CARLA at {host}:{port}. Map: {map_name} TM Port: {tm_port}")
        return jsonify({"success": True, "map": map_name, "host": host,
                        "port": port, "tm_port": tm_port})
    except Exception as e:
        current_app.logger.error(f"Failed to connect: {e}")
        return jsonify({"success": False, "error": str(e)})



@blueprint.route("/disconnect", methods=["POST"])
def disconnect():
    with state_lock:
        carla_state.update({"client": None, "world": None, "connected": False, "host": "", "map": ""})
    current_app.logger.info("Disconnected from CARLA")
    return jsonify({"success": True})


@blueprint.route("/status")
def status():
    with state_lock:
        connected = carla_state["connected"]
        client = carla_state.get("client")
        host = carla_state.get("host")
        port = carla_state.get("port")
        map_name = carla_state.get("map")

    if not connected or not client:
        return jsonify({"connected": False})

    try:
        world = client.get_world()
        actors = get_actors_info(world)
        vehicles = [a for a in actors if a["type"].startswith("vehicle")]
        walkers  = [a for a in actors if a["type"].startswith("walker")]
        sensors  = [a for a in actors if a["type"].startswith("sensor")]
        spec = get_spectator_transform(world)
        return jsonify({
            "connected": True,
            "host": host,
            "port": port,
            "map": map_name,
            "actor_count": len(actors),
            "vehicle_count": len(vehicles),
            "walker_count": len(walkers),
            "sensor_count": len(sensors),
            "actors": actors[:80],
            "weather": _weather_dict(world.get_weather()),
            "spectator": spec,
        })
    except Exception as e:
        with state_lock:
            carla_state["connected"] = False
        return jsonify({"connected": False, "error": str(e)})

