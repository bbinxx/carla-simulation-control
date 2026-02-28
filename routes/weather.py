# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\weather.py
from flask import Blueprint, request, jsonify
import carla

from utils.helpers import get_world, make_weather, WEATHER_PRESETS

blueprint = Blueprint('weather', __name__)

# Maps short JS preset keys → carla.WeatherParameters objects
_PRESET_MAP = {
    "clear":  carla.WeatherParameters.ClearNoon,
    "cloudy": carla.WeatherParameters.CloudyNoon,
    "rain":   carla.WeatherParameters.MidRainyNoon,
    "storm":  carla.WeatherParameters.HardRainNoon,
    "sunset": carla.WeatherParameters.ClearSunset,
    "fog": carla.WeatherParameters(
        cloudiness=60,
        precipitation=0,
        precipitation_deposits=0,
        wind_intensity=10,
        sun_azimuth_angle=45,
        sun_altitude_angle=15,
        fog_density=80,
        fog_distance=10,
        wetness=0,
    ),
    "night": carla.WeatherParameters(
        cloudiness=20,
        precipitation=0,
        precipitation_deposits=0,
        wind_intensity=5,
        sun_azimuth_angle=270,
        sun_altitude_angle=-15,
        fog_density=0,
        fog_distance=0,
        wetness=0,
    ),
}
# Also allow full CARLA preset names
_PRESET_MAP.update(WEATHER_PRESETS)


def _weather_to_dict(w):
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


@blueprint.route("/weather", methods=["GET"])
def weather_get():
    try:
        world = get_world()
        return jsonify({"success": True, "values": _weather_to_dict(world.get_weather())})
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
        if wp is None:
            return jsonify({"success": False, "error": f"Unknown preset '{preset}'"})
        world = get_world()
        world.set_weather(wp)
        values = _weather_to_dict(world.get_weather())
        return jsonify({"success": True, "values": values})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
