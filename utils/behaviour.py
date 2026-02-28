# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\utils\behaviour.py
import logging
import carla
import random
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

def get_tm():
    """Return (tm_object, tm_port) from shared state."""
    with state_lock:
        tm      = carla_state.get("tm")
        tm_port = carla_state.get("tm_port", 8000)
    return tm, tm_port

def sync_global_tm(world):
    """Apply global Traffic Manager settings for deterministic and safe behavior."""
    try:
        tm, tm_port = get_tm()
        if tm is None:
            return False
            
        # Global Rule: 5.0m default gap to prevent jerky stops
        tm.set_global_distance_to_leading_vehicle(5.0)
        
        # Ensure synchronous mode matches world
        tm.set_synchronous_mode(True)
        
        logger.info("Global TM settings applied: Synchronous=True, Gap=5.0m")
        return True
    except Exception as e:
        logger.error(f"Global TM sync failed: {e}")
        return False

def apply_vehicle_behaviour(tm, actor, is_emergency=False):
    pass

def apply_behaviour_to_all(world):
    """Apply behaviour rules to all vehicles in the world."""
    tm, tm_port = get_tm()
    if not tm:
        return 0, 0
        
    sync_global_tm(world)
    vehicles = world.get_actors().filter("vehicle.*")
    count = 0
    for v in vehicles:
        try:
            v.set_autopilot(True, tm_port)
            count += 1
        except Exception as e:
            logger.warning(f"Could not apply behaviour to {v.id}: {e}")
    return count, len(vehicles)
