from flask import Blueprint, request, jsonify

from utils.helpers import get_world, TL_STATE_MAP, ensure_control, require_carla
from utils.cache import world_cache

blueprint = Blueprint("traffic", __name__)


@blueprint.route("/traffic_lights")
@require_carla
def traffic_lights_get():
    """
    Fix 19: Single spectator fetch, cached actors — eliminates double spectator
    RPC and replaces world.get_actors().filter() with the WorldCache list.
    """
    radius   = float(request.args.get("radius", 200))
    world    = get_world()
    spec_loc = world.get_spectator().get_transform().location   # single call

    actors = world_cache.get_actors(world)
    lights = []
    for tl in (a for a in actors if "traffic_light" in a.type_id):
        loc  = tl.get_transform().location
        dist = spec_loc.distance(loc)
        if dist <= radius:
            state = str(tl.get_state()).split(".")[-1].lower()
            lights.append({
                "id":       tl.id,
                "state":    state,
                "distance": round(dist, 1),
                "x":        round(loc.x, 2),
                "y":        round(loc.y, 2),
                "z":        round(loc.z, 2),
            })
    lights.sort(key=lambda l: l["distance"])
    return jsonify({"success": True, "lights": lights})


@blueprint.route("/traffic_light/set", methods=["POST"])
@ensure_control
@require_carla
def traffic_light_set():
    d        = request.json or {}
    actor_id = int(d.get("id"))
    world    = get_world()
    actor    = world.get_actor(actor_id)
    if not actor:
        return jsonify({"success": False, "error": "Actor not found"}), 404

    state_key = d.get("state", "").lower()
    if state_key in TL_STATE_MAP:
        actor.set_state(TL_STATE_MAP[state_key])

    if d.get("freeze", False):
        actor.freeze(True)

    return jsonify({"success": True})


@blueprint.route("/traffic_light/<int:tl_id>/set/<string:state>", methods=["GET", "POST"])
@ensure_control
@require_carla
def traffic_light_set_by_url(tl_id, state):
    world = get_world()
    actor = world.get_actor(tl_id)
    if not actor or "traffic_light" not in actor.type_id:
        return jsonify({"success": False, "error": "Traffic light not found"}), 404

    state_key = state.lower()
    valid_states = {"red", "yellow", "green"}
    if state_key not in valid_states:
        return jsonify({"success": False, "error": f"Invalid state. Use one of: {', '.join(valid_states)}"}), 400

    if state_key in TL_STATE_MAP:
        actor.set_state(TL_STATE_MAP[state_key])
        # Freeze the light so it stays in the requested state, as is typical when manually overriding
        actor.freeze(True)

    return jsonify({
        "success": True, 
        "id": tl_id, 
        "state": state_key, 
        "message": f"Traffic light {tl_id} successfully set to {state_key}"
    })


@blueprint.route("/traffic_light/freeze_all", methods=["POST"])
@ensure_control
@require_carla
def traffic_light_freeze_all():
    d         = request.json or {}
    freeze    = d.get("freeze", True)
    state_key = d.get("state", "").lower()
    world     = get_world()
    # Use cached actors instead of world.get_actors().filter()
    actors    = world_cache.get_actors(world)
    for tl in (a for a in actors if "traffic_light" in a.type_id):
        if state_key in TL_STATE_MAP:
            tl.set_state(TL_STATE_MAP[state_key])
        tl.freeze(freeze)
    return jsonify({"success": True})
