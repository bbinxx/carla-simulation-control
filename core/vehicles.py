# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\core\vehicles.py
import logging
import carla
import random
import time
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

# --- Behaviour Configuration ---
DRIVER_PROFILES = {
    "calm":       {"speed_diff": 5,  "distance": 3.0, "lane_change": 0},
    "normal":     {"speed_diff": 0,  "distance": 2.2, "lane_change": 5},
    "aggressive": {"speed_diff": -5, "distance": 1.5, "lane_change": 10},
}

def get_tm():
    with state_lock: return carla_state.get("tm")

def sync_global_tm(world):
    tm = get_tm()
    if not tm: return False
    tm.set_global_distance_to_leading_vehicle(2.5)
    tm.global_percentage_speed_difference(0.0)
    tm.set_hybrid_physics_mode(True)
    tm.set_hybrid_physics_radius(70.0)   # smooth physics-to-kinematic transition at 70 m
    tm.set_random_device_seed(42)         # deterministic TM decisions = smoother replanning
    return True


def enforce_traffic_rules(world, profile_name="normal"):
    tm = get_tm()
    if not tm:
        return 0
    applied = 0
    for actor in world.get_actors().filter("vehicle.*"):
        try:
            configure_tm(actor, profile_name)
            applied += 1
        except Exception:
            continue
    return applied


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
    tm.keep_right_rule_percentage(actor, 100)     # consistent lane discipline
    for side in ["left", "right"]:
        getattr(tm, f"random_{side}_lanechange_percentage")(actor, p["lane_change"])
    tm.ignore_lights_percentage(actor, 0)
    tm.ignore_signs_percentage(actor, 0)
    tm.ignore_road_signs_percentage(actor, 0) if hasattr(tm, 'ignore_road_signs_percentage') else None


# --- Blueprint & Filtering ---

def list_blueprints(world, filter_str="*"):
    """Returns sorted list of blueprint IDs matching the filter."""
    return sorted([bp.id for bp in world.get_blueprint_library().filter(filter_str)])


def list_emergency_blueprints(world):
    """Returns sorted list of emergency vehicle blueprint IDs."""
    return sorted([
        bp.id for bp in world.get_blueprint_library().filter("vehicle.*")
        if any(kw in bp.id.lower() for kw in ["police", "ambulance", "firetruck"])
    ])


# --- Spawning Logic ---

def try_spawn_actor_with_retries(world, bp, spawn_points, max_tries=5):
    """
    Attempt to spawn actor at up to max_tries spawn points.
    Brief pause between retries avoids flooding CARLA with rapid-fire calls.
    """
    for sp in spawn_points[:max_tries]:
        actor = world.try_spawn_actor(bp, sp)
        if actor:
            return actor
        time.sleep(0.05)
    return None


def get_ordered_spawn_points(world, origin=None):
    spawn_points = list(world.get_map().get_spawn_points())
    if origin:
        spawn_points.sort(key=lambda sp: sp.location.distance(origin))
    return spawn_points


def spawn_vehicle(world, bp_id="vehicle.tesla.model3", behavior="normal", transform=None):
    bpl = world.get_blueprint_library()
    bp = bpl.find(bp_id)
    if not bp: return None
    
    if not transform:
        origin = None
        try:
            origin = world.get_spectator().get_location()
        except Exception:
            origin = None
        spawn_points = get_ordered_spawn_points(world, origin)
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
    """Batch-spawns NPCs and enables autopilot via chained commands to avoid per-actor stall."""
    with state_lock:
        client = carla_state.get("client")
        tm_port = carla_state.get("tm_port", 8000)

    if not client:
        logger.error("Client not found in state. Falling back to sequential spawn.")
        return sum(1 for _ in range(count) if spawn_vehicle(world))

    vehicle_bps = [bp for bp in world.get_blueprint_library().filter("vehicle.*")
                   if not any(tag in bp.id.lower() for tag in ["motorcycle", "trailer", "ambulance", "police", "firetruck", "tanker", "bus", "rv"])]
    if not vehicle_bps:
        vehicle_bps = list(world.get_blueprint_library().filter("vehicle.*"))

    try:
        origin = world.get_spectator().get_location()
    except Exception:
        origin = None
    spawn_points = get_ordered_spawn_points(world, origin)

    # Chain SetAutoPilot so vehicles start moving immediately after spawn (no lag loop)
    batch = []
    for i in range(min(count, len(spawn_points))):
        bp = vehicle_bps[i % len(vehicle_bps)]
        batch.append(
            carla.command.SpawnActor(bp, spawn_points[i])
            .then(carla.command.SetAutopilot(carla.command.FutureActor, True, tm_port))
        )

    results = client.apply_batch_sync(batch, True)
    spawned_ids = [res.actor_id for res in results if not res.error]

    # Apply per-vehicle TM profile in one pass (actors already exist, no extra tick needed)
    actors = world.get_actors(spawned_ids)
    profile_names = list(DRIVER_PROFILES.keys())
    for i, actor in enumerate(actors):
        profile = profile_names[i % len(profile_names)]
        p = DRIVER_PROFILES[profile]
        tm = get_tm()
        if tm:
            tm.distance_to_leading_vehicle(actor, p["distance"])
            tm.vehicle_percentage_speed_difference(actor, p["speed_diff"])
            tm.auto_lane_change(actor, True)

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

    try:
        origin = world.get_spectator().get_location()
    except Exception:
        origin = None

    # Spawn Walkers
    for _ in range(count):
        loc = None
        # Try up to 20 times to find a navigation point within 50 meters of spectator
        if origin:
            for _attempt in range(20):
                l = world.get_random_location_from_navigation()
                if l and l.distance(origin) < 50.0:
                    loc = l
                    break
        
        # Fallback to any random location if no nearby one found or no origin
        if not loc:
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

# --- Red Light Precision Stop ---

def _stop_line_waypoint(vehicle):
    """Return the stop-line waypoint for a vehicle at a red light, or None."""
    try:
        tl = vehicle.get_traffic_light()
        if not tl:
            return None
        stop_wps = tl.get_stop_waypoints()
        if not stop_wps:
            return None
        veh_loc = vehicle.get_location()
        # pick the stop waypoint whose lane/road best matches this vehicle
        wp_map = vehicle.get_world().get_map()
        veh_wp = wp_map.get_waypoint(veh_loc, project_to_road=True, lane_type=carla.LaneType.Driving)
        if veh_wp:
            same_lane = [wp for wp in stop_wps
                         if wp.road_id == veh_wp.road_id and wp.lane_id == veh_wp.lane_id]
            if same_lane:
                return same_lane[0]
        # fallback: closest stop waypoint
        return min(stop_wps, key=lambda wp: wp.transform.location.distance(veh_loc))
    except Exception:
        return None

def precision_red_light_stop(world, actors=None):
    """
    Call once per tick. Snaps vehicles that have stopped for a red light
    to sit exactly at the stop line (zero gap).
    """
    try:
        target_actors = actors if actors is not None else world.get_actors()
        for v in target_actors:
            if not v.type_id.startswith("vehicle."):
                continue
            if v.get_traffic_light_state() != carla.TrafficLightState.Red:
                continue

            vel = v.get_velocity()
            speed = (vel.x**2 + vel.y**2 + vel.z**2) ** 0.5
            if speed > 0.3:          # still moving — let TM brake naturally
                continue

            stop_wp = _stop_line_waypoint(v)
            if not stop_wp:
                continue

            veh_loc = v.get_location()
            dist = veh_loc.distance(stop_wp.transform.location)

            # Only snap if there's a real gap (>0.3 m) and vehicle is close enough
            # to the intersection that it was clearly braking for this light
            if 0.3 < dist < 10.0:
                bb_len = v.bounding_box.extent.x   # half-length of vehicle
                # place front face of vehicle exactly on the stop line
                stop_loc = stop_wp.transform.location
                fwd = stop_wp.transform.get_forward_vector()
                snap_loc = carla.Location(
                    stop_loc.x - fwd.x * bb_len,
                    stop_loc.y - fwd.y * bb_len,
                    veh_loc.z,
                )
                v.set_transform(carla.Transform(snap_loc, v.get_transform().rotation))
    except Exception:
        pass

def handle_green_light_resume(world, actors=None):
    """
    Call once per tick. Gives vehicles a small nudge forward when traffic light turns green
    to help them resume movement if they were snapped to the stop line.
    """
    try:
        target_actors = actors if actors is not None else world.get_actors()
        for v in target_actors:
            if not v.type_id.startswith("vehicle."):
                continue
            tl_state = v.get_traffic_light_state()
            if tl_state != carla.TrafficLightState.Green:
                continue

            vel = v.get_velocity()
            speed = (vel.x**2 + vel.y**2 + vel.z**2) ** 0.5

            # If vehicle is stopped or moving very slowly at a green light
            if speed < 1.0:
                # Check if we're at a stop line
                stop_wp = _stop_line_waypoint(v)
                if not stop_wp:
                    continue

                veh_loc = v.get_location()
                dist = veh_loc.distance(stop_wp.transform.location)

                # If very close to stop line, give a small forward nudge
                if dist < 2.0:
                    fwd = v.get_transform().get_forward_vector()
                    nudge_loc = carla.Location(
                        veh_loc.x + fwd.x * 0.5,  # 0.5m forward nudge
                        veh_loc.y + fwd.y * 0.5,
                        veh_loc.z
                    )
                    v.set_transform(carla.Transform(nudge_loc, v.get_transform().rotation))

                    # Also apply a small velocity to get moving
                    v.set_velocity(carla.Vector3D(fwd.x * 2.0, fwd.y * 2.0, vel.z))
    except Exception:
        pass

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