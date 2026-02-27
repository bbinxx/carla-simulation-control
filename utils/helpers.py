import carla
from config.state import carla_state, state_lock

TL_STATE_MAP = {
    "red":    carla.TrafficLightState.Red,
    "green":  carla.TrafficLightState.Green,
    "yellow": carla.TrafficLightState.Yellow,
    "off":    carla.TrafficLightState.Off,
}
