# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\destroy.py
from flask import Blueprint, request, jsonify
from utils.helpers import get_world
from core.vehicles import destroy_actors

blueprint = Blueprint('destroy', __name__)

@blueprint.route("/destroy/actor", methods=["POST"])
def destroy_actor():
    try:
        actor_id = int((request.json or {}).get("id", 0))
        world = get_world()
        count = destroy_actors(world, actor_id=actor_id)
        if count: return jsonify({"success": True})
        return jsonify({"success": False, "error": f"Actor {actor_id} not found"})
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@blueprint.route("/destroy/all", methods=["POST"])
def destroy_all():
    try:
        filt = (request.json or {}).get("filter", "vehicle.*")
        world = get_world()
        count = destroy_actors(world, actor_filter=filt)
        return jsonify({"success": True, "destroyed": count})
    except Exception as e: return jsonify({"success": False, "error": str(e)})
