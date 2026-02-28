# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\spectator.py
from flask import Blueprint, request, jsonify
import carla

from config.state import carla_state, state_lock
from utils.helpers import get_world, get_spectator_transform

blueprint = Blueprint('spectator', __name__)


@blueprint.route("/spectator/get")
def spectator_get():
    try:
        world = get_world()
        return jsonify({"success": True, **get_spectator_transform(world)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spectator/set", methods=["POST"])
def spectator_set():
    try:
        d = request.json
        world = get_world()
        t = carla.Transform(
            carla.Location(x=float(d.get("x", 0)), y=float(d.get("y", 0)), z=float(d.get("z", 0))),
            carla.Rotation(pitch=float(d.get("pitch", 0)), yaw=float(d.get("yaw", 0)), roll=float(d.get("roll", 0))),
        )
        world.get_spectator().set_transform(t)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
