from flask import Blueprint, request, jsonify

from utils.helpers import get_world, get_spectator_transform, TL_STATE_MAP

blueprint = Blueprint('traffic', __name__)


@blueprint.route("/traffic_lights")
def traffic_lights_get():
    try:
        radius = float(request.args.get("radius", 200))
        world = get_world()
        spec = get_spectator_transform(world)
        spec_loc = world.get_spectator().get_transform().location

        lights = []
        for tl in world.get_actors().filter("traffic.traffic_light*"):
            loc = tl.get_transform().location
            dist = spec_loc.distance(loc)
            if dist <= radius:
                state = str(tl.get_state()).split(".")[-1].lower()
                lights.append({
                    "id": tl.id,
                    "state": state,
                    "distance": round(dist, 1),
                    "x": round(loc.x, 2),
                    "y": round(loc.y, 2),
                    "z": round(loc.z, 2),
                })
        lights.sort(key=lambda l: l["distance"])
        return jsonify({"success": True, "lights": lights})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/traffic_light/set", methods=["POST"])
def traffic_light_set():
    try:
        d = request.json
        actor_id = int(d.get("id"))
        world = get_world()
        actor = world.get_actor(actor_id)
        if not actor:
            return jsonify({"success": False, "error": "Actor not found"})

        state_key = d.get("state", "").lower()
        if state_key in TL_STATE_MAP:
            actor.set_state(TL_STATE_MAP[state_key])

        freeze = d.get("freeze", False)
        if freeze:
            actor.freeze(True)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/traffic_light/freeze_all", methods=["POST"])
def traffic_light_freeze_all():
    try:
        d = request.json
        freeze = d.get("freeze", True)
        state_key = d.get("state", "").lower()
        world = get_world()
        for tl in world.get_actors().filter("traffic.traffic_light*"):
            if state_key in TL_STATE_MAP:
                tl.set_state(TL_STATE_MAP[state_key])
            tl.freeze(freeze)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
