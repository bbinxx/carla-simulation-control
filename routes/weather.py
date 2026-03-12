# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\weather.py
from flask import Blueprint, request, jsonify
import carla
from utils.helpers import get_world, make_weather, WEATHER_PRESETS, format_weather

blueprint = Blueprint('weather', __name__)

_PRESET_MAP = {
    "clear":  carla.WeatherParameters.ClearNoon,
    "cloudy": carla.WeatherParameters.CloudyNoon,
    "rain":   carla.WeatherParameters.MidRainyNoon,
    "storm":  carla.WeatherParameters.HardRainNoon,
    "sunset": carla.WeatherParameters.ClearSunset,
    "fog": carla.WeatherParameters(cloudiness=60, fog_density=80, fog_distance=10),
    "night": carla.WeatherParameters(sun_altitude_angle=-15),
}
_PRESET_MAP.update(WEATHER_PRESETS)

@blueprint.route("/weather", methods=["GET"])
def weather_get():
    try:
        world = get_world()
        return jsonify({"success": True, "values": format_weather(world.get_weather())})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/weather", methods=["POST"])
def weather_set():
    try:
        world = get_world()
        w = make_weather(request.json or {})
        world.set_weather(w)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/weather/preset", methods=["POST"])
def weather_preset():
    try:
        preset = (request.json or {}).get("preset", "").strip()
        wp = _PRESET_MAP.get(preset) or _PRESET_MAP.get(preset.lower())
        if wp is None: return jsonify({"success": False, "error": f"Unknown preset '{preset}'"})
        world = get_world()
        world.set_weather(wp)
        return jsonify({"success": True, "values": format_weather(world.get_weather())})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
