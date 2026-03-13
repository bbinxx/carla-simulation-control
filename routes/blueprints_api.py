from flask import Blueprint, request, jsonify

from utils.helpers import get_world, require_carla

blueprint = Blueprint("blueprints_api", __name__)


@blueprint.route("/blueprints")
@require_carla
def blueprints_list():
    filt  = request.args.get("filter", "*")
    world = get_world()
    bps   = sorted([bp.id for bp in world.get_blueprint_library().filter(filt)])
    return jsonify({"success": True, "blueprints": bps})


@blueprint.route("/blueprints/emergency")
@require_carla
def blueprints_emergency():
    world = get_world()
    emerg = sorted([
        bp.id for bp in world.get_blueprint_library().filter("vehicle.*")
        if any(kw in bp.id.lower() for kw in ["police", "ambulance", "firetruck"])
    ])
    return jsonify({"success": True, "blueprints": emerg})
