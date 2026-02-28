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
    """
    Apply strict per-vehicle Traffic Manager rules for realistic behaviour.
    Implements driver personalities, emergency overrides, and junction safety.
    """
    if tm is None:
        return
    try:
        # ── 1. Basic Rule Obedience ────────────────────────────────────────
        # Emergency vehicles ignore lights; others obey them 100%
        light_ignore = 100.0 if is_emergency else 0.0
        tm.ignore_lights_percentage(actor,   light_ignore)
        tm.ignore_signs_percentage(actor,    0.0)
        tm.ignore_vehicles_percentage(actor, 0.0) # Always detect vehicles to avoid crashes
        tm.ignore_walkers_percentage(actor,  0.0)

        # ── 2. Dynamic Driver Personality ─────────────────────────────────
        if is_emergency:
            # Emergency vehicles drive 20% faster than traffic flow
            speed_diff = -20.0 
            gap = 3.0 # Tighter gap for weaves
        else:
            # Simulate driver personality: -10% (cautious) to +5% (aggressive)
            # CARLA uses negative for 'faster', positive for 'slower'
            # offset = random.uniform(-5.0, 10.0) # user asked: -10% to +5% speed relative to limit
            # If limit is 100, -10% speed offset means driving at 110? 
            # CARLA logic: -10% means driving 10% ABOVE. +10% means 10% BELOW.
            # User request: "deviation between -10% and +5%" 
            # Usually users mean -10% (slower) to +5% (faster).
            # But "driver personalities" often means some fast, some slow.
            # CARLA attribute: percentage_speed_difference
            # We'll use random.uniform(-5.0, 10.0) where -5 is 5% faster, 10 is 10% slower.
            speed_diff = random.uniform(-5.0, 10.0)
            gap = 5.0 # Recommended 5.0m to prevent jerky braking

        tm.vehicle_percentage_speed_difference(actor, speed_diff)
        tm.distance_to_leading_vehicle(actor, gap)

        # ── 3. Junction & Stop Line Logic ────────────────────────────────
        # Reduce distance to stop line (stop closer to the actual line)
        if hasattr(tm, 'distance_to_stop_line'):
            tm.distance_to_stop_line(actor, 1.0)

        # Disable automatic lane changes to prevent circular driving loops
        tm.auto_lane_change(actor, False)
        tm.random_left_lanechange_percentage(actor,  0.0)
        tm.random_right_lanechange_percentage(actor, 0.0)

        # Force keep-right rule
        if hasattr(tm, 'keep_right_rule_percentage'):
            tm.keep_right_rule_percentage(actor, 100.0)
            
        # Collision Detection
        tm.set_collision_detection(actor, carla.Actor, True)

    except Exception as e:
        logger.warning(f"Behaviour rules failed for actor {actor.id}: {e}")

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
            # Detect if it's an emergency vehicle for rule overrides
            is_emer = any(kw in v.type_id.lower() for kw in ["police", "ambulance", "firetruck", "fire"])
            
            v.set_autopilot(True, tm_port)
            apply_vehicle_behaviour(tm, v, is_emergency=is_emer)
            count += 1
        except Exception as e:
            logger.warning(f"Could not apply behaviour to {v.id}: {e}")
    return count, len(vehicles)
