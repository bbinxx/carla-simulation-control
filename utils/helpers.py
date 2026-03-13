import carla
from functools import wraps
from flask import jsonify

from config.state import carla_state, state_lock
from utils.cache import world_cache


# ── @require_carla decorator ─────────────────────────────────────────────────

def require_carla(f):
    """
    Route decorator: returns HTTP 503 with JSON error if CARLA is not connected.
    The decorated function receives no implicit extra args; it calls get_world()
    or world_cache itself as needed.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except RuntimeError as e:
            msg = str(e)
            code = 503 if "Not connected" in msg else 500
            return jsonify({"success": False, "error": msg}), code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    return wrapper


# ── @ensure_control decorator ────────────────────────────────────────────────

def ensure_control(f):
    """Route decorator: blocks request if vehicle control is globally disabled."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        with state_lock:
            if not carla_state.get("control_enabled", True):
                return jsonify({
                    "success": False,
                    "error": "Vehicle control is currently disabled via global lock."
                })
        return f(*args, **kwargs)
    return wrapper


# ── World access ─────────────────────────────────────────────────────────────

def get_world():
    """Return cached world object, or raise RuntimeError if disconnected."""
    w = world_cache.get_world()
    if w is not None:
        return w
    # Fallback: fetch once and prime the cache
    with state_lock:
        client = carla_state.get("client")
        connected = carla_state.get("connected")
    if not connected or client is None:
        raise RuntimeError("Not connected to CARLA")
    w = client.get_world()
    world_cache.set_world(w)
    return w


# ── Spectator helpers ─────────────────────────────────────────────────────────

def get_spectator_transform(world=None):
    """Return spectator transform as a plain dict."""
    if world is None:
        world = get_world()
    t = world.get_spectator().get_transform()
    return {
        "x":     round(t.location.x, 3),
        "y":     round(t.location.y, 3),
        "z":     round(t.location.z, 3),
        "pitch": round(t.rotation.pitch, 3),
        "yaw":   round(t.rotation.yaw, 3),
        "roll":  round(t.rotation.roll, 3),
    }


# ── Weather helpers ───────────────────────────────────────────────────────────

def format_weather(w):
    """Convert a CARLA WeatherParameters object to a JSON-serialisable dict."""
    return {
        "cloudiness":            round(w.cloudiness, 2),
        "precipitation":         round(w.precipitation, 2),
        "precipitation_deposits": round(w.precipitation_deposits, 2),
        "wind_intensity":        round(w.wind_intensity, 2),
        "sun_azimuth_angle":     round(w.sun_azimuth_angle, 2),
        "sun_altitude_angle":    round(w.sun_altitude_angle, 2),
        "fog_density":           round(w.fog_density, 2),
        "fog_distance":          round(w.fog_distance, 2),
        "wetness":               round(w.wetness, 2),
    }


def make_weather(params: dict) -> carla.WeatherParameters:
    """Build a WeatherParameters object from a request JSON dict."""
    w = carla.WeatherParameters()
    for field in ["cloudiness", "precipitation", "precipitation_deposits",
                  "wind_intensity", "sun_azimuth_angle", "sun_altitude_angle",
                  "fog_density", "fog_distance", "wetness"]:
        if field in params:
            setattr(w, field, float(params[field]))
    return w


# ── Actor info ────────────────────────────────────────────────────────────────

def get_actors_info(world):
    """
    Return summarised actor list using the WorldCache (TTL=2s).
    Avoids repeated get_actors() RPC calls across the same poll cycle.
    """
    all_actors = world_cache.get_actors(world)
    actors = []

    for a in all_actors:
        tid = a.type_id
        t = a.get_transform()
        base = {
            "id": a.id,
            "x":  round(t.location.x, 1),
            "y":  round(t.location.y, 1),
            "z":  round(t.location.z, 1),
            "yaw": round(t.rotation.yaw, 1),
        }

        if tid.startswith("vehicle."):
            actors.append({**base, "type": "vehicle", "type_id": tid})
        elif tid.startswith("walker.pedestrian."):
            actors.append({**base, "type": "walker", "type_id": tid})
        elif "traffic_light" in tid:
            state = str(a.get_state()).split(".")[-1].lower()
            actors.append({**base, "type": "traffic_light", "state": state})
        elif tid.startswith("sensor."):
            actors.append({**base, "type": "sensor", "type_id": tid})

    return actors


# ── Traffic light state map ───────────────────────────────────────────────────

TL_STATE_MAP = {
    "red":    carla.TrafficLightState.Red,
    "green":  carla.TrafficLightState.Green,
    "yellow": carla.TrafficLightState.Yellow,
    "off":    carla.TrafficLightState.Off,
}


# ── Weather preset map ────────────────────────────────────────────────────────

WEATHER_PRESETS = {
    "ClearNoon":       carla.WeatherParameters.ClearNoon,
    "CloudyNoon":      carla.WeatherParameters.CloudyNoon,
    "WetNoon":         carla.WeatherParameters.WetNoon,
    "WetCloudyNoon":   carla.WeatherParameters.WetCloudyNoon,
    "MidRainyNoon":    carla.WeatherParameters.MidRainyNoon,
    "HardRainNoon":    carla.WeatherParameters.HardRainNoon,
    "SoftRainNoon":    carla.WeatherParameters.SoftRainNoon,
    "ClearSunset":     carla.WeatherParameters.ClearSunset,
    "CloudySunset":    carla.WeatherParameters.CloudySunset,
    "WetSunset":       carla.WeatherParameters.WetSunset,
    "WetCloudySunset": carla.WeatherParameters.WetCloudySunset,
    "MidRainSunset":   carla.WeatherParameters.MidRainSunset,
    "HardRainSunset":  carla.WeatherParameters.HardRainSunset,
    "SoftRainSunset":  carla.WeatherParameters.SoftRainSunset,
}
