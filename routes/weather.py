from flask import Blueprint, request, jsonify
import carla

from utils.helpers import get_world, make_weather, WEATHER_PRESETS, format_weather, require_carla

blueprint = Blueprint("weather", __name__)

_PRESET_MAP = {
    "clear":  carla.WeatherParameters.ClearNoon,
    "cloudy": carla.WeatherParameters.CloudyNoon,
    "rain":   carla.WeatherParameters.MidRainyNoon,
    "storm":  carla.WeatherParameters.HardRainNoon,
    "sunset": carla.WeatherParameters.ClearSunset,
    "fog":    carla.WeatherParameters(cloudiness=60, fog_density=80, fog_distance=10),
    "night":  carla.WeatherParameters(sun_altitude_angle=-15),
}
_PRESET_MAP.update(WEATHER_PRESETS)


def _weather_to_dict(wp):
    """Return a WeatherParameters object as a plain dict without an RPC call."""
    return {
        "cloudiness":            round(wp.cloudiness, 2),
        "precipitation":         round(wp.precipitation, 2),
        "precipitation_deposits": round(wp.precipitation_deposits, 2),
        "wind_intensity":        round(wp.wind_intensity, 2),
        "sun_azimuth_angle":     round(wp.sun_azimuth_angle, 2),
        "sun_altitude_angle":    round(wp.sun_altitude_angle, 2),
        "fog_density":           round(wp.fog_density, 2),
        "fog_distance":          round(wp.fog_distance, 2),
        "wetness":               round(wp.wetness, 2),
    }


@blueprint.route("/weather", methods=["GET"])
@require_carla
def weather_get():
    world = get_world()
    return jsonify({"success": True, "values": format_weather(world.get_weather())})


@blueprint.route("/weather", methods=["POST"])
@require_carla
def weather_set():
    world = get_world()
    world.set_weather(make_weather(request.json or {}))
    return jsonify({"success": True})


@blueprint.route("/weather/preset", methods=["POST"])
@require_carla
def weather_preset():
    """
    Fix 16: Return the preset dict directly instead of reading back from CARLA.
    This avoids a race condition where CARLA hasn't propagated the change yet.
    """
    preset = (request.json or {}).get("preset", "").strip()
    wp = _PRESET_MAP.get(preset) or _PRESET_MAP.get(preset.lower())
    if wp is None:
        return jsonify({"success": False, "error": f"Unknown preset '{preset}'"}), 400
    world = get_world()
    world.set_weather(wp)
    # Return values derived directly from the preset object — no re-read from CARLA
    return jsonify({"success": True, "values": _weather_to_dict(wp)})
