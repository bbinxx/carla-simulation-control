# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\utils\helpers.py
import carla
from config.state import carla_state, state_lock

TL_STATE_MAP = {
    "red":    carla.TrafficLightState.Red,
    "green":  carla.TrafficLightState.Green,
    "yellow": carla.TrafficLightState.Yellow,
    "off":    carla.TrafficLightState.Off,
}

WEATHER_PRESETS = {
    "ClearNoon":        carla.WeatherParameters.ClearNoon,
    "CloudyNoon":       carla.WeatherParameters.CloudyNoon,
    "WetNoon":          carla.WeatherParameters.WetNoon,
    "WetCloudyNoon":    carla.WeatherParameters.WetCloudyNoon,
    "MidRainyNoon":     carla.WeatherParameters.MidRainyNoon,
    "HardRainNoon":     carla.WeatherParameters.HardRainNoon,
    "SoftRainNoon":     carla.WeatherParameters.SoftRainNoon,
    "ClearSunset":      carla.WeatherParameters.ClearSunset,
    "CloudySunset":     carla.WeatherParameters.CloudySunset,
    "WetSunset":        carla.WeatherParameters.WetSunset,
    "WetCloudySunset":  carla.WeatherParameters.WetCloudySunset,
    "MidRainSunset":    carla.WeatherParameters.MidRainSunset,
    "HardRainSunset":   carla.WeatherParameters.HardRainSunset,
    "SoftRainSunset":   carla.WeatherParameters.SoftRainSunset,
}


def get_world():
    """Return the current CARLA world or raise RuntimeError if not connected."""
    with state_lock:
        client = carla_state.get("client")
        connected = carla_state.get("connected")
    if not connected or client is None:
        raise RuntimeError("Not connected to CARLA")
    return client.get_world()


def get_actors_info(world):
    """Return a list of dicts describing all actors (vehicles, walkers, sensors, traffic lights)."""
    actors = []
    all_actors = world.get_actors()

    for v in all_actors.filter("vehicle.*"):
        t = v.get_transform()
        actors.append({
            "id": v.id,
            "type": "vehicle",
            "type_id": v.type_id,
            "x": round(t.location.x, 2),
            "y": round(t.location.y, 2),
            "z": round(t.location.z, 2),
            "yaw": round(t.rotation.yaw, 2),
        })

    for w in all_actors.filter("walker.pedestrian.*"):
        t = w.get_transform()
        actors.append({
            "id": w.id,
            "type": "walker",
            "type_id": w.type_id,
            "x": round(t.location.x, 2),
            "y": round(t.location.y, 2),
            "z": round(t.location.z, 2),
            "yaw": round(t.rotation.yaw, 2),
        })

    for s in all_actors.filter("sensor.*"):
        t = s.get_transform()
        actors.append({
            "id": s.id,
            "type": "sensor",
            "type_id": s.type_id,
            "x": round(t.location.x, 2),
            "y": round(t.location.y, 2),
            "z": round(t.location.z, 2),
            "yaw": round(t.rotation.yaw, 2),
        })

    for tl in all_actors.filter("traffic.traffic_light*"):
        t = tl.get_transform()
        state = str(tl.get_state()).split(".")[-1].lower()
        actors.append({
            "id": tl.id,
            "type": "traffic_light",
            "type_id": tl.type_id,
            "state": state,
            "x": round(t.location.x, 2),
            "y": round(t.location.y, 2),
            "z": round(t.location.z, 2),
        })

    return actors


def get_spectator_transform(world):
    """Return the spectator transform as a dict."""
    t = world.get_spectator().get_transform()
    return {
        "x":     round(t.location.x, 4),
        "y":     round(t.location.y, 4),
        "z":     round(t.location.z, 4),
        "pitch": round(t.rotation.pitch, 4),
        "yaw":   round(t.rotation.yaw, 4),
        "roll":  round(t.rotation.roll, 4),
    }


def make_weather(params: dict) -> carla.WeatherParameters:
    """Build a WeatherParameters object from a dict of field values."""
    w = carla.WeatherParameters()
    fields = [
        "cloudiness", "precipitation", "precipitation_deposits",
        "wind_intensity", "sun_azimuth_angle", "sun_altitude_angle",
        "fog_density", "fog_distance", "wetness",
    ]
    for field in fields:
        if field in params:
            setattr(w, field, float(params[field]))
    return w

