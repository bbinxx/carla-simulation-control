"""
routes/connection.py
====================
CARLA connection lifecycle + status endpoints.

Extracted from routes/history.py (which now handles only DB operations).
"""
from flask import Blueprint, request, jsonify, current_app
import carla

from config.state import carla_state, state_lock, DEFAULT_TM_PORT
from config.db import get_db
from utils.cache import world_cache
from utils.helpers import get_actors_info, get_spectator_transform, format_weather
from threads.stream import stop_stream

blueprint = Blueprint("connection", __name__)


# ── Internal helper ────────────────────────────────────────────────────────────

def _weather_dict(w):
    keys = ["cloudiness", "precipitation", "precipitation_deposits",
            "wind_intensity", "sun_azimuth_angle", "sun_altitude_angle",
            "fog_density", "fog_distance", "wetness"]
    return {k: round(getattr(w, k), 2) for k in keys}


# ── Connect ────────────────────────────────────────────────────────────────────

@blueprint.route("/connect", methods=["POST"])
def connect():
    data    = request.json or {}
    host    = data.get("host", "localhost")
    port    = int(data.get("port", 2000))
    timeout = float(data.get("timeout", 10.0))

    try:
        # Stop any existing stream on reconnect
        stop_stream()

        client = carla.Client(host, port)
        client.set_timeout(timeout)

        # Traffic Manager — async mode so we don't stall the tick loop
        tm = client.get_trafficmanager(DEFAULT_TM_PORT)
        tm.set_synchronous_mode(False)
        tm.global_percentage_speed_difference(10.0)
        tm.set_global_distance_to_leading_vehicle(3.0)
        tm_port = tm.get_port()

        world    = client.get_world()
        map_name = world.get_map().name

        # Prime the cache immediately — all subsequent get_world() calls are free
        world_cache.set_world(world)

        with state_lock:
            carla_state.update({
                "client":    client,
                "connected": True,
                "host":      host,
                "port":      port,
                "map":       map_name,
                "tm":        tm,
                "tm_port":   tm_port,
            })

        # Persist the host to DB (for history dropdown)
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO hosts (host,port,last_used) VALUES (?,?,CURRENT_TIMESTAMP)",
                (host, port))
            conn.execute(
                "INSERT OR REPLACE INTO last_connection (id,host,port) VALUES (1,?,?)",
                (host, port))

        current_app.logger.info(f"Connected {host}:{port} map={map_name}")
        return jsonify({"success": True, "map": map_name,
                        "host": host, "port": port, "tm_port": tm_port})

    except Exception as e:
        current_app.logger.error(f"Connect failed: {e}")
        return jsonify({"success": False, "error": str(e)})


# ── Disconnect ─────────────────────────────────────────────────────────────────

@blueprint.route("/disconnect", methods=["POST"])
def disconnect():
    stop_stream()
    world_cache.invalidate()
    with state_lock:
        carla_state.update({
            "client":    None,
            "connected": False,
            "host":      "",
            "map":       "",
            "tm":        None,
        })
    return jsonify({"success": True})


# ── Status: lightweight summary (polled every 5 s) ────────────────────────────

@blueprint.route("/api/status/summary")
def status_summary():
    """Lightweight poll — counts actors from cache, no per-actor RPC."""
    with state_lock:
        connected = carla_state.get("connected", False)
        client    = carla_state.get("client")
        host      = carla_state.get("host")
        port      = carla_state.get("port")
        map_name  = carla_state.get("map")

    if not connected or not client:
        return jsonify({"connected": False})

    try:
        world  = world_cache.get_world() or client.get_world()
        actors = world_cache.get_actors(world)

        vehicle_count = sum(1 for a in actors if a.type_id.startswith("vehicle."))
        walker_count  = sum(1 for a in actors if a.type_id.startswith("walker."))
        sensor_count  = sum(1 for a in actors if a.type_id.startswith("sensor."))
        actor_count   = vehicle_count + walker_count + sensor_count

        return jsonify({
            "connected":     True,
            "host":          host,
            "port":          port,
            "map":           map_name,
            "actor_count":   actor_count,
            "vehicle_count": vehicle_count,
            "walker_count":  walker_count,
            "sensor_count":  sensor_count,
            "spectator":     get_spectator_transform(world),
            "weather":       _weather_dict(world.get_weather()),
        })
    except Exception as e:
        # Treat any failure as a broken connection
        world_cache.invalidate()
        with state_lock:
            carla_state["connected"] = False
        return jsonify({"connected": False, "error": str(e)})


# ── Status: heavy actor list (only when Actors tab is open) ───────────────────

@blueprint.route("/api/status/actors")
def status_actors():
    """Full actor list — call only when the Actors tab is visible."""
    try:
        world = world_cache.get_world()
        if not world:
            return jsonify({"success": False, "error": "Not connected"})
        actors = get_actors_info(world)
        return jsonify({"success": True, "actors": actors[:100]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── Legacy /status alias (backwards compat) ───────────────────────────────────

@blueprint.route("/status")
def status_legacy():
    return status_summary()


# ── Control lock ──────────────────────────────────────────────────────────────

@blueprint.route("/control/set", methods=["POST"])
def set_control():
    try:
        d       = request.json or {}
        enabled = d.get("enabled", True)
        with state_lock:
            carla_state["control_enabled"] = enabled
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/control/status")
def get_control_status():
    with state_lock:
        return jsonify({"success": True,
                        "enabled": carla_state.get("control_enabled", True)})
