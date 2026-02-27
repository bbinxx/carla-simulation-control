from flask import Blueprint, request, jsonify

from utils.helpers import get_world

blueprint = Blueprint('blueprints_api', __name__)


@blueprint.route("/blueprints")
def blueprints_list():
    try:
        filt = request.args.get("filter", "*")
        world = get_world()
        bpl = world.get_blueprint_library()
        bps = sorted([bp.id for bp in bpl.filter(filt)])
        return jsonify({"success": True, "blueprints": bps})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
