from flask import Blueprint, request, jsonify
import carla

from utils.helpers import get_world, get_spectator_transform, require_carla

blueprint = Blueprint("spectator", __name__)


@blueprint.route("/spectator/get")
@blueprint.route("/api/spectator/position")   # Fix 6: alias — was causing 503 in logs
@require_carla
def spectator_get():
    world = get_world()
    return jsonify({"success": True, **get_spectator_transform(world)})


@blueprint.route("/spectator/set", methods=["POST"])
@require_carla
def spectator_set():
    d = request.json or {}
    world = get_world()
    t = carla.Transform(
        carla.Location(
            x=float(d.get("x",     0)),
            y=float(d.get("y",     0)),
            z=float(d.get("z",     0)),
        ),
        carla.Rotation(
            pitch=float(d.get("pitch", 0)),
            yaw=  float(d.get("yaw",   0)),
            roll= float(d.get("roll",  0)),
        ),
    )
    world.get_spectator().set_transform(t)
    return jsonify({"success": True})
