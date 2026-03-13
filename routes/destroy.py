from flask import Blueprint, request, jsonify

from utils.helpers import get_world, require_carla
from core.vehicles import destroy_actors

blueprint = Blueprint("destroy", __name__)


@blueprint.route("/destroy/actor", methods=["POST"])
@require_carla
def destroy_actor():
    actor_id = int((request.json or {}).get("id", 0))
    world    = get_world()
    count    = destroy_actors(world, actor_id=actor_id)
    if count:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": f"Actor {actor_id} not found"}), 404


@blueprint.route("/destroy/all", methods=["POST"])
@require_carla
def destroy_all():
    filt  = (request.json or {}).get("filter", "vehicle.*")
    world = get_world()
    count = destroy_actors(world, actor_filter=filt)
    return jsonify({"success": True, "destroyed": count})
