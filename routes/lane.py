# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\lane.py
from flask import Blueprint, request, jsonify
import carla
import random
from utils.helpers import get_world
from core.vehicles import get_tm, configure_tm # use direct tm for force_lane_change

blueprint = Blueprint('lane', __name__)

@blueprint.route("/lane/current")
def get_current_lane():
    try:
        world = get_world()
        spec_loc = world.get_spectator().get_location()
        wp = world.get_map().get_waypoint(spec_loc, project_to_road=True, lane_type=carla.LaneType.Any)
        if not wp: return jsonify({"success": False, "error": "No waypoint"})
        
        vehicles = []
        for v in world.get_actors().filter("vehicle.*"):
            v_wp = world.get_map().get_waypoint(v.get_location(), project_to_road=True, lane_type=carla.LaneType.Any)
            if v_wp and v_wp.road_id == wp.road_id and v_wp.lane_id == wp.lane_id:
                vel = v.get_velocity()
                speed = 3.6 * (vel.x**2 + vel.y**2 + vel.z**2)**0.5
                vehicles.append({"id": v.id, "type_id": v.type_id, "speed": round(speed, 1)})
        
        return jsonify({
            "success": True, "road_id": wp.road_id, "lane_id": wp.lane_id,
            "lane_width": round(wp.lane_width, 2), "vehicles": vehicles
        })
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@blueprint.route("/lane/spawn", methods=["POST"])
def spawn_in_lane():
    try:
        d = request.json or {}
        world = get_world()
        spec_loc = world.get_spectator().get_location()
        wp = world.get_map().get_waypoint(spec_loc, project_to_road=True)
        if not wp: return jsonify({"success": False, "error": "No road"})

        spawn_wp = wp.next(d.get("distance", 5.0))[0]
        transform = spawn_wp.transform
        transform.location.z += 0.5
        
        from core.vehicles import spawn_vehicle
        actor = spawn_vehicle(world, d.get("blueprint", "vehicle.tesla.model3"), d.get("behavior", "normal"), transform)
        if actor: return jsonify({"success": True, "id": actor.id, "type": actor.type_id})
        return jsonify({"success": False, "error": "Spawn blocked"})
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@blueprint.route("/lane/clear", methods=["POST"])
def clear_lane():
    try:
        world = get_world()
        spec_loc = world.get_spectator().get_location()
        wp = world.get_map().get_waypoint(spec_loc, project_to_road=True)
        if not wp: return jsonify({"success": False, "error": "No road"})
            
        count = 0
        from core.vehicles import destroy_actors
        for v in world.get_actors().filter("vehicle.*"):
            v_wp = world.get_map().get_waypoint(v.get_location(), project_to_road=True)
            if v_wp and v_wp.road_id == wp.road_id and v_wp.lane_id == wp.lane_id:
                destroy_actors(world, actor_id=v.id)
                count += 1
        return jsonify({"success": True, "cleared": count})
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@blueprint.route("/lane/change_lane", methods=["POST"])
def change_lane():
    try:
        d = request.json or {}
        world = get_world()
        actor = world.get_actor(int(d.get("id")))
        if not actor: return jsonify({"success": False, "error": "Vehicle not found"})
        direction = d.get("direction", "right") == "right"
        tm = get_tm()
        if tm: tm.force_lane_change(actor, direction); return jsonify({"success": True})
        return jsonify({"success": False, "error": "TM not found"})
    except Exception as e: return jsonify({"success": False, "error": str(e)})
