# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\utils\behaviour.py
import logging
import carla
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

def get_tm():
    """Return (tm_object, tm_port) from shared state."""
    with state_lock:
        tm      = carla_state.get("tm")
        tm_port = carla_state.get("tm_port", 8000)
    return tm, tm_port

def apply_vehicle_behaviour(tm, actor):
    """
    Apply strict per-vehicle Traffic Manager rules for realistic behaviour.
    Vehicle must already have autopilot enabled before calling this.
    """
    if tm is None:
        return
    try:
        # ── Strict rule obedience ─────────────────────────────────────────
        # 100% obey traffic lights, stop/yield signs, other vehicles, walkers
        tm.ignore_lights_percentage(actor,   0.0)
        tm.ignore_signs_percentage(actor,    0.0)
        tm.ignore_vehicles_percentage(actor, 0.0)
        tm.ignore_walkers_percentage(actor,  0.0)

        # ── Lane discipline ──────────────────────────────────────────────
        # Disable TM's automatic lane-change decisions at junctions.
        # This prevents vehicles from driving in circles on small networks.
        tm.auto_lane_change(actor, False)

        # No random lane changes
        tm.random_left_lanechange_percentage(actor,  0.0)
        tm.random_right_lanechange_percentage(actor, 0.0)

        # Force keep-right discipline
        if hasattr(tm, 'keep_right_rule_percentage'):
            tm.keep_right_rule_percentage(actor, 100.0)

        # Per-vehicle following distance matches global safe gap
        tm.distance_to_leading_vehicle(actor, 4.0)

        # Inherit global speed (20% under limit)
        tm.vehicle_percentage_speed_difference(actor, 20.0)
        
    except Exception as e:
        logger.warning(f"Behaviour rules failed for actor {actor.id}: {e}")

def apply_behaviour_to_all(world):
    """Apply behaviour rules to all vehicles in the world."""
    tm, tm_port = get_tm()
    vehicles = world.get_actors().filter("vehicle.*")
    count = 0
    for v in vehicles:
        try:
            v.set_autopilot(True, tm_port)
            apply_vehicle_behaviour(tm, v)
            count += 1
        except Exception as e:
            logger.warning(f"Could not apply behaviour to {v.id}: {e}")
    return count, len(vehicles)
