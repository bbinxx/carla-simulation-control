# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\spawner.py
from flask import Blueprint, request, jsonify
import carla
import logging
from utils.helpers import get_world
from core.vehicles import spawn_vehicle, spawn_npc_batch, spawn_walker_batch

blueprint = Blueprint('spawner', __name__)
logger = logging.getLogger(__name__)

@blueprint.route("/spawn/vehicle", methods=["POST"])
def spawn_v():
    try:
        d = request.json or {}
        world = get_world()
        actor = spawn_vehicle(world, d.get("blueprint", "vehicle.tesla.mod3"), d.get("behavior", "normal"))
        if actor: return jsonify({"success": True, "actor_id": actor.id})
        return jsonify({"success": False, "error": "Spawn failed"})
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@blueprint.route("/spawn/npc", methods=["POST"])
def spawn_n():
    try:
        d = request.json or {}
        count = spawn_npc_batch(get_world(), int(d.get("count", 10)))
        return jsonify({"success": True, "spawned": count})
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@blueprint.route("/spawn/emergency", methods=["POST"])
def spawn_e():
    try:
        world = get_world()
        # Simple emergency filter
        emerg = [bp for bp in world.get_blueprint_library().filter("vehicle.*") if any(kw in bp.id.lower() for kw in ["police", "ambulance", "firetruck"])]
        if not emerg: return jsonify({"success": False, "error": "No emergency vehicles"})
        import random
        actor = spawn_vehicle(world, random.choice(emerg).id, "aggressive")
        if actor: return jsonify({"success": True, "actor_id": actor.id})
        return jsonify({"success": False, "error": "Spawn failed"})
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@blueprint.route("/spawn/walker", methods=["POST"])
def spawn_w():
    try:
        d = request.json or {}
        count = spawn_walker_batch(get_world(), int(d.get("count", 5)))
        return jsonify({"success": True, "spawned": count})
    except Exception as e: return jsonify({"success": False, "error": str(e)})