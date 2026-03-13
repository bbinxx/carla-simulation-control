from flask import Blueprint, request, jsonify
import carla

from utils.helpers import get_world, ensure_control, require_carla
from utils.cache import world_cache
from core.vehicles import get_tm, configure_tm, spawn_vehicle, destroy_actors

blueprint = Blueprint("lane", __name__)


@blueprint.route("/lane/current")
@require_carla
def get_current_lane():
    world    = get_world()
    spec_loc = world.get_spectator().get_location()
    m        = world.get_map()
    wp       = m.get_waypoint(spec_loc, project_to_road=True, lane_type=carla.LaneType.Any)
    if not wp:
        return jsonify({"success": False, "error": "No waypoint"}), 404

    def get_lane_data(w):
        return {
            "lane_id":   w.lane_id,
            "type":      str(w.lane_type).split(".")[-1],
            "width":     round(w.lane_width, 2),
            "is_current": (w.lane_id == wp.lane_id),
        }

    lanes = [get_lane_data(wp)]

    l = wp.get_left_lane()
    while l and l.lane_type != carla.LaneType.NONE:
        lanes.append(get_lane_data(l))
        l = l.get_left_lane()

    r = wp.get_right_lane()
    while r and r.lane_type != carla.LaneType.NONE:
        lanes.append(get_lane_data(r))
        r = r.get_right_lane()

    lanes.sort(key=lambda x: x["lane_id"])

    # Use cached actors for vehicles on road
    actors   = world_cache.get_actors(world)
    vehicles = []
    for v in (a for a in actors if a.type_id.startswith("vehicle.")):
        v_wp = m.get_waypoint(v.get_location(), project_to_road=True,
                              lane_type=carla.LaneType.Any)
        if v_wp and v_wp.road_id == wp.road_id:
            vel   = v.get_velocity()
            speed = 3.6 * (vel.x**2 + vel.y**2 + vel.z**2) ** 0.5
            vehicles.append({
                "id":      v.id,
                "type_id": v.type_id,
                "speed":   round(speed, 1),
                "lane_id": v_wp.lane_id,
            })

    return jsonify({
        "success":     True,
        "road_id":    wp.road_id,
        "section_id": wp.section_id,
        "is_junction": wp.is_junction,
        "junction_id": wp.junction_id if wp.is_junction else -1,
        "s":          round(wp.s, 2),
        "lanes":      lanes,
        "vehicles":   vehicles,
    })


@blueprint.route("/lane/spawn", methods=["POST"])
@ensure_control
@require_carla
def spawn_in_lane():
    d        = request.json or {}
    world    = get_world()
    spec_loc = world.get_spectator().get_location()
    wp       = world.get_map().get_waypoint(spec_loc, project_to_road=True)
    if not wp:
        return jsonify({"success": False, "error": "No road"}), 404

    spawn_wp  = wp.next(d.get("distance", 5.0))[0]
    transform = spawn_wp.transform
    transform.location.z += 0.5

    actor = spawn_vehicle(world, d.get("blueprint", "vehicle.tesla.model3"),
                          d.get("behavior", "normal"), transform)
    if actor:
        return jsonify({"success": True, "id": actor.id, "type": actor.type_id})
    return jsonify({"success": False, "error": "Spawn blocked"})


@blueprint.route("/lane/clear", methods=["POST"])
@ensure_control
@require_carla
def clear_lane():
    world    = get_world()
    spec_loc = world.get_spectator().get_location()
    m        = world.get_map()
    wp       = m.get_waypoint(spec_loc, project_to_road=True)
    if not wp:
        return jsonify({"success": False, "error": "No road"}), 404

    actors  = world_cache.get_actors(world)
    count   = 0
    for v in (a for a in actors if a.type_id.startswith("vehicle.")):
        v_wp = m.get_waypoint(v.get_location(), project_to_road=True,
                              lane_type=carla.LaneType.Any)
        if v_wp and v_wp.road_id == wp.road_id:
            destroy_actors(world, actor_id=v.id)
            count += 1
    return jsonify({"success": True, "cleared": count})


@blueprint.route("/lane/change_lane", methods=["POST"])
@ensure_control
@require_carla
def change_lane():
    d      = request.json or {}
    world  = get_world()
    actor  = world.get_actor(int(d.get("id")))
    if not actor:
        return jsonify({"success": False, "error": "Vehicle not found"}), 404
    direction = d.get("direction", "right") == "right"
    tm = get_tm()
    if tm:
        tm.force_lane_change(actor, direction)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "TM not available"})
