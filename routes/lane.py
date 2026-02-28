# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\lane.py
from flask import Blueprint, request, jsonify, current_app
import carla
import random
import logging
from utils.helpers import get_world
from utils.behaviour import get_tm

blueprint = Blueprint('lane', __name__)
logger = logging.getLogger(__name__)

@blueprint.route("/lane/current")
def get_current_lane():
    try:
        world = get_world()
        spec_loc = world.get_spectator().get_location()
        waypoint = world.get_map().get_waypoint(spec_loc, project_to_road=True, lane_type=carla.LaneType.Any)
        
        if not waypoint:
            return jsonify({"success": False, "error": "No waypoint found near spectator"})
            
        lane_id = waypoint.lane_id
        road_id = waypoint.road_id
        section_id = waypoint.section_id
        
        vehicles_in_lane = []
        for v in world.get_actors().filter("vehicle.*"):
            v_wp = world.get_map().get_waypoint(v.get_location(), project_to_road=True, lane_type=carla.LaneType.Any)
            if v_wp and v_wp.road_id == road_id and v_wp.lane_id == lane_id:
                vel = v.get_velocity()
                speed = 3.6 * (vel.x**2 + vel.y**2 + vel.z**2)**0.5
                vehicles_in_lane.append({
                    "id": v.id,
                    "type_id": v.type_id,
                    "speed": round(speed, 1)
                })
        
        return jsonify({
            "success": True,
            "road_id": road_id,
            "lane_id": lane_id,
            "section_id": section_id,
            "lane_type": str(waypoint.lane_type),
            "lane_width": round(waypoint.lane_width, 2),
            "vehicles": vehicles_in_lane
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/lane/spawn", methods=["POST"])
def spawn_in_lane():
    try:
        d = request.json or {}
        world = get_world()
        spec_loc = world.get_spectator().get_location()
        waypoint = world.get_map().get_waypoint(spec_loc, project_to_road=True)
        
        if not waypoint:
            return jsonify({"success": False, "error": "Not near a valid road lane"})

        bpl = world.get_blueprint_library()
        bp_id = d.get("blueprint", "vehicle.tesla.model3")
        bp = bpl.find(bp_id)
        
        is_emergency = d.get("emergency", False)
        if is_emergency:
            emergencies = [b for b in bpl.filter("vehicle.*") if any(kw in b.id.lower() for kw in ["police", "ambulance", "fire"])]
            bp = random.choice(emergencies) if emergencies else bp

        # Spawn slightly ahead of spectator current waypoint
        spawn_wp = waypoint.next(d.get("distance", 5.0))[0]
        transform = spawn_wp.transform
        transform.location.z += 0.5
        
        actor = world.try_spawn_actor(bp, transform)
        if not actor:
            return jsonify({"success": False, "error": "Spawn blocked (collision?)"})
            
        if d.get("autopilot", True):
            tm, tm_port = get_tm()
            actor.set_autopilot(True, tm_port)
            
        return jsonify({"success": True, "id": actor.id, "type": actor.type_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@blueprint.route("/lane/clear", methods=["POST"])
def clear_lane():
    try:
        world = get_world()
        spec_loc = world.get_spectator().get_location()
        waypoint = world.get_map().get_waypoint(spec_loc, project_to_road=True)
        
        if not waypoint:
            return jsonify({"success": False, "error": "Not near a valid road lane"})
            
        road_id = waypoint.road_id
        lane_id = waypoint.lane_id
        
        count = 0
        for v in world.get_actors().filter("vehicle.*"):
            v_wp = world.get_map().get_waypoint(v.get_location(), project_to_road=True)
            if v_wp and v_wp.road_id == road_id and v_wp.lane_id == lane_id:
                v.destroy()
                count += 1
                
        return jsonify({"success": True, "cleared": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
@blueprint.route("/lane/change_lane", methods=["POST"])
def change_lane():
    try:
        d = request.json or {}
        actor_id = int(d.get("id"))
        direction = d.get("direction", "right") == "right" # True = right, False = left
        
        world = get_world()
        actor = world.get_actor(actor_id)
        if not actor or not actor.type_id.startswith("vehicle"):
             return jsonify({"success": False, "error": "Vehicle not found"})
             
        tm, _ = get_tm()
        if tm:
            tm.force_lane_change(actor, direction)
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "TM not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
