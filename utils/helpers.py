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
    """Return the current CARLA world."""
    with state_lock:
        world = carla_state.get("world")
        if world:
            return world
        client = carla_state.get("client")
        connected = carla_state.get("connected")
    
    if client and connected:
        try:
            return client.get_world()
        except Exception:
            pass
            
    raise RuntimeError("Not connected to CARLA")

def get_spectator_transform(world=None):
    """Return spectator transform dict."""
    if world is None: world = get_world()
    t = world.get_spectator().get_transform()
    return {
        "x": round(t.location.x, 3), "y": round(t.location.y, 3), "z": round(t.location.z, 3),
        "pitch": round(t.rotation.pitch, 3), "yaw": round(t.rotation.yaw, 3), "roll": round(t.rotation.roll, 3),
    }

def format_weather(w):
    """Convert CARLA weather object to dict."""
    return {
        "cloudiness": round(w.cloudiness, 2), "precipitation": round(w.precipitation, 2),
        "precipitation_deposits": round(w.precipitation_deposits, 2), "wind_intensity": round(w.wind_intensity, 2),
        "sun_azimuth_angle": round(w.sun_azimuth_angle, 2), "sun_altitude_angle": round(w.sun_altitude_angle, 2),
        "fog_density": round(w.fog_density, 2), "fog_distance": round(w.fog_distance, 2), "wetness": round(w.wetness, 2),
    }

def make_weather(params: dict) -> carla.WeatherParameters:
    """Build a WeatherParameters object from a dict."""
    w = carla.WeatherParameters()
    fields = [
        "cloudiness", "precipitation", "precipitation_deposits",
        "wind_intensity", "sun_azimuth_angle", "sun_altitude_angle",
        "fog_density", "fog_distance", "wetness",
    ]
    for field in fields:
        if field in params: setattr(w, field, float(params[field]))
    return w

def get_actors_info(world):
    """Summary of all relevant actors."""
    actors = []
    all_actors = world.get_actors()

    for v in all_actors.filter("vehicle.*"):
        t = v.get_transform()
        actors.append({"id": v.id, "type": "vehicle", "type_id": v.type_id, "x": round(t.location.x, 2), "y": round(t.location.y, 2)})

    for w in all_actors.filter("walker.pedestrian.*"):
        t = w.get_transform()
        actors.append({"id": w.id, "type": "walker", "type_id": w.type_id, "x": round(t.location.x, 2), "y": round(t.location.y, 2)})

    for tl in all_actors.filter("traffic.traffic_light*"):
        t = tl.get_transform()
        state = str(tl.get_state()).split(".")[-1].lower()
        actors.append({"id": tl.id, "type": "traffic_light", "state": state, "x": round(t.location.x, 2), "y": round(t.location.y, 2)})

    for s in all_actors.filter("sensor.*"):
        t = s.get_transform()
        actors.append({"id": s.id, "type": "sensor", "type_id": s.type_id, "x": round(t.location.x, 2), "y": round(t.location.y, 2)})

    return actors
