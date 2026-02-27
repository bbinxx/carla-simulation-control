from flask import Blueprint, request, jsonify, current_app
import carla
import random

from config.state import carla_state, state_lock
from utils.helpers import get_world

blueprint = Blueprint('spawner', __name__)


def _parse_color(color_str):
    try:
        parts = [int(x.strip()) for x in color_str.split(",")]
        if len(parts) == 3:
            return carla.Color(*parts)
    except Exception:
        pass
    return None


@blueprint.route("/spawn/vehicle", methods=["POST"])
def spawn_vehicle():
    try:
        d = request.json
        world = get_world()
        bpl = world.get_blueprint_library()
        bp_id = d.get("blueprint", "vehicle.tesla.model3")
        bp = bpl.find(bp_id)
        if not bp:
            return jsonify({"success": False, "error": f"Blueprint {bp_id} not found"})

        color = _parse_color(d.get("color", ""))
        if color and bp.has_attribute("color"):
            bp.set_attribute("color", f"{color.r},{color.g},{color.b}")

        at_spectator = d.get("at_spectator", False)
        if at_spectator:
            transform = world.get_spectator().get_transform()
            transform.location.z += 2.0
        else:
            spawn_points = world.get_map().get_spawn_points()
            if not spawn_points:
                return jsonify({"success": False, "error": "No spawn points"})
            transform = random.choice(spawn_points)

        actor = world.try_spawn_actor(bp, transform)
        if not actor:
            return jsonify({"success": False, "error": "Spawn failed (collision?)"})

        if d.get("autopilot", True):
            with state_lock:
                tm_port = carla_state.get("tm_port", 8000)
            actor.set_autopilot(True, tm_port)

        current_app.logger.info(f"Spawned vehicle {bp_id} ID:{actor.id}")
        return jsonify({"success": True, "actor_id": actor.id, "blueprint": bp_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/npc", methods=["POST"])
def spawn_npc():
    try:
        d = request.json
        count = int(d.get("count", 10))
        world = get_world()
        bpl = world.get_blueprint_library()
        vehicle_bps  = list(bpl.filter("vehicle.*"))
        spawn_points = world.get_map().get_spawn_points()
        random.shuffle(spawn_points)

        with state_lock:
            tm_port = carla_state.get("tm_port", 8000)

        spawned = 0
        for sp in spawn_points[:count]:
            bp = random.choice(vehicle_bps)
            actor = world.try_spawn_actor(bp, sp)
            if actor:
                actor.set_autopilot(True, tm_port)
                spawned += 1

        return jsonify({"success": True, "spawned": spawned})
    except Exception as e:
        current_app.logger.error(f"spawn_npc error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/walker", methods=["POST"])
def spawn_walker():
    try:
        d = request.json
        count = int(d.get("count", 5))
        world = get_world()
        bpl = world.get_blueprint_library()
        walker_bps = list(bpl.filter("walker.pedestrian.*"))
        if not walker_bps:
            return jsonify({"success": False, "error": "No walker blueprints found"})

        spawned = 0
        for _ in range(count):
            bp = random.choice(walker_bps)
            loc = world.get_random_location_from_navigation()
            if not loc:
                continue
            transform = carla.Transform(loc)
            actor = world.try_spawn_actor(bp, transform)
            if actor:
                spawned += 1

        return jsonify({"success": True, "spawned": spawned})
    except Exception as e:
        current_app.logger.error(f"spawn_walker error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/any", methods=["POST"])
def spawn_any():
    try:
        d = request.json
        world = get_world()
        bpl = world.get_blueprint_library()
        bp_id = d.get("blueprint")
        if not bp_id:
            return jsonify({"success": False, "error": "No blueprint specified"})
        bp = bpl.find(bp_id)
        if not bp:
            return jsonify({"success": False, "error": f"Blueprint '{bp_id}' not found"})

        z_offset = float(d.get("z_offset", 1.0))
        transform = world.get_spectator().get_transform()
        transform.location.z += z_offset

        actor = world.try_spawn_actor(bp, transform)
        if not actor:
            return jsonify({"success": False, "error": "Spawn failed (collision at spectator?)"})

        # check tags list, not has_tag method
        if d.get("autopilot", False) and "vehicle" in bp.tags:
            with state_lock:
                tm_port = carla_state.get("tm_port", 8000)
            actor.set_autopilot(True, tm_port)

        current_app.logger.info(f"Spawned any: {bp_id} ID:{actor.id}")
        return jsonify({"success": True, "actor_id": actor.id, "blueprint": bp_id})
    except Exception as e:
        current_app.logger.error(f"spawn_any error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/camera", methods=["POST"])
def spawn_camera():
    try:
        d = request.json
        width = int(d.get("width", 1280))
        height = int(d.get("height", 720))
        fov = int(d.get("fov", 90))
        world = get_world()
        bpl = world.get_blueprint_library()
        bp = bpl.find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(width))
        bp.set_attribute("image_size_y", str(height))
        bp.set_attribute("fov", str(fov))
        transform = world.get_spectator().get_transform()
        actor = world.spawn_actor(bp, transform)
        return jsonify({"success": True, "actor_id": actor.id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
