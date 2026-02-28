# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\core\vehicles.py
import logging
import carla
import random
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

# --- Behaviour Configuration ---
DRIVER_PROFILES = {
    "calm": {"speed_diff": 5, "distance": 1.2, "lane_change": 2},
    "normal": {"speed_diff": 0, "distance": 1.0, "lane_change": 10},
    "aggressive": {"speed_diff": -10, "distance": 0.8, "lane_change": 30},
}

def get_tm():
    with state_lock: return carla_state.get("tm")

def sync_global_tm(world):
    tm = get_tm()
    if not tm: return False
    tm.set_global_distance_to_leading_vehicle(0.8)
    tm.set_synchronous_mode(True)
    tm.set_hybrid_physics_mode(True)
    tm.global_percentage_speed_difference(0.0)
    return True

def configure_tm(actor, profile_name="normal"):
    tm = get_tm()
    if not tm: return
    with state_lock: tm_port = carla_state.get("tm_port", 8000)
    actor.set_autopilot(True, tm_port)
    p = DRIVER_PROFILES.get(profile_name, DRIVER_PROFILES["normal"])
    tm.distance_to_leading_vehicle(actor, p["distance"])
    tm.vehicle_percentage_speed_difference(actor, p["speed_diff"])
    tm.auto_lane_change(actor, True)
    for side in ["left", "right"]:
        getattr(tm, f"random_{side}_lanechange_percentage")(actor, p["lane_change"])
    tm.ignore_lights_percentage(actor, 0)
    tm.ignore_signs_percentage(actor, 0)

# --- Spawning Logic ---
def spawn_vehicle(world, bp_id="vehicle.tesla.model3", behavior="normal", transform=None):
    bpl = world.get_blueprint_library()
    bp = bpl.find(bp_id)
    if not bp: return None
    
    if not transform:
        spawn_points = world.get_map().get_spawn_points()
        random.shuffle(spawn_points)
        for sp in spawn_points[:20]:
            actor = world.try_spawn_actor(bp, sp)
            if actor:
                configure_tm(actor, behavior)
                return actor
    else:
        actor = world.try_spawn_actor(bp, transform)
        if actor:
            configure_tm(actor, behavior)
            return actor
    return None

def spawn_npc_batch(world, count=10):
    bpl = world.get_blueprint_library()
    vehicle_bps = list(bpl.filter("vehicle.*"))
    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)
    
    spawned = 0
    for sp in spawn_points[:count]:
        bp = random.choice(vehicle_bps)
        actor = world.try_spawn_actor(bp, sp)
        if actor:
            configure_tm(actor, random.choice(list(DRIVER_PROFILES.keys())))
            spawned += 1
    return spawned

def spawn_walker_batch(world, count=5):
    bpl = world.get_blueprint_library()
    walker_bps = list(bpl.filter("walker.pedestrian.*"))
    controller_bp = bpl.find("controller.ai.walker")
    spawned = 0
    for _ in range(count):
        loc = world.get_random_location_from_navigation()
        if not loc: continue
        walker = world.try_spawn_actor(random.choice(walker_bps), carla.Transform(loc))
        if not walker: continue
        c = world.spawn_actor(controller_bp, carla.Transform(), walker)
        c.start()
        c.go_to_location(world.get_random_location_from_navigation())
        c.set_max_speed(random.uniform(1.2, 1.8))
        spawned += 1
    return spawned

# --- Lane & Actor Management ---
def get_lane_info(world, location):
    wp = world.get_map().get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Any)
    if not wp: return None
    return {"road_id": wp.road_id, "lane_id": wp.lane_id, "width": wp.lane_width, "waypoint": wp}

def destroy_actors(world, actor_filter="*", actor_id=None):
    if actor_id:
        a = world.get_actor(actor_id)
        if a: a.destroy(); return 1
        return 0
    
    destroyed = 0
    spec_id = world.get_spectator().id
    actor_list = list(world.get_actors()) if actor_filter in ["*", "all"] else list(world.get_actors().filter(actor_filter))
    for a in actor_list:
        if a.id != spec_id:
            try: a.destroy(); destroyed += 1
            except: pass
    return destroyed
