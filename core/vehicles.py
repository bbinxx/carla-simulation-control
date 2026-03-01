# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\core\vehicles.py
import logging
import carla
import random
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

# --- Behaviour Configuration ---
DRIVER_PROFILES = {
    "calm": {"speed_diff": 10, "distance": 2.0, "lane_change": 0},
    "normal": {"speed_diff": 0, "distance": 1.0, "lane_change": 10},
    "aggressive": {"speed_diff": -15, "distance": 0.5, "lane_change": 50},
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
    with state_lock: 
        tm_port = carla_state.get("tm_port", 8000)
    
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
    """Fixed: Uses client from state for batching while accepting world."""
    with state_lock:
        client = carla_state.get("client")
    
    if not client:
        logger.error("Client not found in state. Falling back to sequential spawn.")
        return sum(1 for _ in range(count) if spawn_vehicle(world))

    vehicle_bps = world.get_blueprint_library().filter("vehicle.*")
    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)
    
    batch = []
    for i in range(min(count, len(spawn_points))):
        bp = random.choice(vehicle_bps)
        batch.append(carla.command.SpawnActor(bp, spawn_points[i]))
    
    results = client.apply_batch_sync(batch, True)
    spawned_ids = [res.actor_id for res in results if not res.error]
    
    for s_id in spawned_ids:
        actor = world.get_actor(s_id)
        if actor:
            configure_tm(actor, random.choice(list(DRIVER_PROFILES.keys())))
            
    return len(spawned_ids)

def spawn_walker_batch(world, count=5):
    """Fixed: Returns all IDs (walkers + controllers) for clean destruction."""
    with state_lock:
        client = carla_state.get("client")
        
    bpl = world.get_blueprint_library()
    walker_bps = bpl.filter("walker.pedestrian.*")
    controller_bp = bpl.find("controller.ai.walker")
    
    all_spawned_ids = []
    walkers_list = []

    # Spawn Walkers
    for _ in range(count):
        loc = world.get_random_location_from_navigation()
        if not loc: continue
        walker = world.try_spawn_actor(random.choice(walker_bps), carla.Transform(loc))
        if walker:
            walkers_list.append(walker)
            all_spawned_ids.append(walker.id)

    # Spawn Controllers via Client Batch
    if client:
        batch = [carla.command.SpawnActor(controller_bp, carla.Transform(), w.id) for w in walkers_list]
        results = client.apply_batch_sync(batch, True)
        for res in results:
            if not res.error:
                all_spawned_ids.append(res.actor_id)
                c = world.get_actor(res.actor_id)
                c.start()
                c.go_to_location(world.get_random_location_from_navigation())
    
    return all_spawned_ids

# --- Management & Cleanup ---

def get_lane_info(world, location):
    wp = world.get_map().get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving)
    if not wp: return None
    return {"road_id": wp.road_id, "lane_id": wp.lane_id, "width": wp.lane_width, "waypoint": wp}

def destroy_actors(world, actor_filter="*", actor_id=None):
    """Fixed: Uses world.get_actors() correctly to avoid 'no attribute get_world'."""
    with state_lock:
        client = carla_state.get("client")

    if actor_id:
        a = world.get_actor(actor_id)
        if a: 
            a.destroy()
            return 1
        return 0
    
    destroyed = 0
    spec_id = world.get_spectator().id
    
    # Get the target list
    if actor_filter in ["*", "all"]:
        actor_list = list(world.get_actors())
    else:
        actor_list = list(world.get_actors().filter(actor_filter))

    # If client is available, use fast batch destruction
    if client:
        batch = [carla.command.DestroyActor(a.id) for a in actor_list if a.id != spec_id]
        results = client.apply_batch_sync(batch, True)
        return len([res for res in results if not res.error])
    
    # Fallback to sequential destruction
    for a in actor_list:
        if a.id != spec_id:
            try:
                a.destroy()
                destroyed += 1
            except:
                pass
    return destroyed