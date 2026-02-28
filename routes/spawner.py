# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\spawner.py
from flask import Blueprint, request, jsonify, current_app
import carla
import random
import logging

from config.state import carla_state, state_lock
from utils.helpers import get_world

blueprint = Blueprint('spawner', __name__)
logger = logging.getLogger(__name__)

from utils.behaviour import get_tm, apply_behaviour_to_all

# Emergency vehicle keywords in CARLA blueprint IDs
_EMERGENCY_KEYWORDS = ["police", "ambulance", "firetruck", "fire_truck", "fire"]

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
        d     = request.json or {}
        world = get_world()
        bpl   = world.get_blueprint_library()

        bp_id = d.get("blueprint", "vehicle.tesla.model3")
        bp    = bpl.find(bp_id)
        if not bp:
            return jsonify({"success": False, "error": f"Blueprint '{bp_id}' not found"})

        color = _parse_color(d.get("color", ""))
        if color and bp.has_attribute("color"):
            bp.set_attribute("color", f"{color.r},{color.g},{color.b}")

        # ── Always spawn ON the road ─────────────────────────────────────────
        spawn_points = world.get_map().get_spawn_points()
        if not spawn_points:
            return jsonify({"success": False, "error": "No road spawn points on this map"})

        transform = random.choice(spawn_points)

        actor = world.try_spawn_actor(bp, transform)
        if not actor:
            # Retry with all spawn points until one works
            random.shuffle(spawn_points)
            for sp in spawn_points[:10]:
                actor = world.try_spawn_actor(bp, sp)
                if actor:
                    break
        if not actor:
            return jsonify({"success": False, "error": "All spawn points blocked"})

        try:
            if d.get("autopilot", True):
                tm, tm_port = get_tm()
                actor.set_autopilot(True, tm_port)

            logger.info(f"Spawned vehicle {bp_id} ID:{actor.id}")
            return jsonify({"success": True, "actor_id": actor.id, "blueprint": bp_id})
        except Exception as e:
            if actor:
                actor.destroy()
            raise e
    except Exception as e:
        logger.error(f"spawn_vehicle error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/npc", methods=["POST"])
def spawn_npc():
    try:
        d            = request.json or {}
        count        = int(d.get("count", 10))
        radius       = float(d.get("radius", 0.0))
        world        = get_world()
        bpl          = world.get_blueprint_library()
        vehicle_bps  = list(bpl.filter("vehicle.*"))
        spawn_points = world.get_map().get_spawn_points()


        random.shuffle(spawn_points)
        tm, tm_port = get_tm()

        spawned = 0
        actors_to_cleanup = []
        try:
            for sp in spawn_points[:count]:
                bp    = random.choice(vehicle_bps)
                actor = world.try_spawn_actor(bp, sp)
                if actor:
                    actors_to_cleanup.append(actor)
                    actor.set_autopilot(True, tm_port)
                    spawned += 1
                    # Successfully initialized, remove from cleanup list
                    actors_to_cleanup.remove(actor)

            logger.info(f"NPC spawn: {spawned}/{count}")
            return jsonify({"success": True, "spawned": spawned})
        except Exception as e:
            for a in actors_to_cleanup:
                a.destroy()
            raise e
    except Exception as e:
        logger.error(f"spawn_npc error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/walker", methods=["POST"])
def spawn_walker():
    try:
        d          = request.json or {}
        count      = int(d.get("count", 5))
        world      = get_world()
        bpl        = world.get_blueprint_library()
        walker_bps = list(bpl.filter("walker.pedestrian.*"))
        if not walker_bps:
            return jsonify({"success": False, "error": "No walker blueprints found"})

        spawned = 0
        for _ in range(count):
            bp    = random.choice(walker_bps)
            loc   = world.get_random_location_from_navigation()
            if not loc:
                continue
            actor = world.try_spawn_actor(bp, carla.Transform(loc))
            if actor:
                spawned += 1

        logger.info(f"Walker spawn: {spawned}/{count}")
        return jsonify({"success": True, "spawned": spawned})
    except Exception as e:
        logger.error(f"spawn_walker error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/emergency", methods=["POST"])
def spawn_emergency():
    """Spawn an emergency vehicle (police/ambulance/firetruck) on road."""
    try:
        d     = request.json or {}
        world = get_world()
        bpl   = world.get_blueprint_library()

        bp_id = d.get("blueprint", "")
        if bp_id:
            bp = bpl.find(bp_id)
            if not bp:
                return jsonify({"success": False, "error": f"Blueprint '{bp_id}' not found"})
        else:
            # Pick a random emergency blueprint
            emerg = [bp for bp in bpl.filter("vehicle.*")
                     if any(kw in bp.id.lower() for kw in _EMERGENCY_KEYWORDS)]
            if not emerg:
                return jsonify({"success": False, "error": "No emergency vehicles in blueprint library"})
            bp = random.choice(emerg)
            bp_id = bp.id

        spawn_points = world.get_map().get_spawn_points()
        if not spawn_points:
            return jsonify({"success": False, "error": "No road spawn points"})

        transform = random.choice(spawn_points)

        actor = world.try_spawn_actor(bp, transform)
        if not actor:
            random.shuffle(spawn_points)
            for sp in spawn_points[:10]:
                actor = world.try_spawn_actor(bp, sp)
                if actor:
                    break
        if not actor:
            return jsonify({"success": False, "error": "All spawn points blocked"})

        try:
            if d.get("autopilot", True):
                tm, tm_port = get_tm()
                actor.set_autopilot(True, tm_port)

            logger.info(f"Emergency vehicle spawned: {bp_id} ID:{actor.id}")
            return jsonify({"success": True, "actor_id": actor.id, "blueprint": bp_id})
        except Exception as e:
            if actor:
                actor.destroy()
            raise e
    except Exception as e:
        logger.error(f"spawn_emergency error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/any", methods=["POST"])
def spawn_any():
    """Spawn any blueprint — vehicles always placed on nearest road spawn point."""
    try:
        d     = request.json or {}
        world = get_world()
        bpl   = world.get_blueprint_library()
        bp_id = d.get("blueprint")
        if not bp_id:
            return jsonify({"success": False, "error": "No blueprint specified"})
        bp = bpl.find(bp_id)
        if not bp:
            return jsonify({"success": False, "error": f"Blueprint '{bp_id}' not found"})

        is_vehicle = "vehicle" in bp.tags

        if is_vehicle:
            # Always use road spawn points for vehicles
            spawn_points = world.get_map().get_spawn_points()
            if not spawn_points:
                return jsonify({"success": False, "error": "No spawn points on map"})
            transform = random.choice(spawn_points)
        else:
            # Non-vehicles (props, sensors) can spawn at spectator
            z_offset   = float(d.get("z_offset", 1.0))
            transform  = world.get_spectator().get_transform()
            transform.location.z += z_offset

        actor = world.try_spawn_actor(bp, transform)
        if not actor:
            return jsonify({"success": False, "error": "Spawn failed (collision?)"})

        try:
            if d.get("autopilot", False) and is_vehicle:
                tm, tm_port = get_tm()
                actor.set_autopilot(True, tm_port)

            logger.info(f"Spawned any: {bp_id} ID:{actor.id}")
            return jsonify({"success": True, "actor_id": actor.id, "blueprint": bp_id})
        except Exception as e:
            if actor:
                actor.destroy()
            raise e
    except Exception as e:
        logger.error(f"spawn_any error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/spawn/camera", methods=["POST"])
def spawn_camera():
    try:
        d      = request.json or {}
        width  = int(d.get("width",  1280))
        height = int(d.get("height", 720))
        fov    = int(d.get("fov",    90))
        world  = get_world()
        bpl    = world.get_blueprint_library()
        bp     = bpl.find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(width))
        bp.set_attribute("image_size_y", str(height))
        bp.set_attribute("fov",          str(fov))
        transform = world.get_spectator().get_transform()
        actor = world.spawn_actor(bp, transform)
        logger.info(f"Camera spawned ID:{actor.id}")
        return jsonify({"success": True, "actor_id": actor.id})
    except Exception as e:
        logger.error(f"spawn_camera error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/blueprints/emergency")
def emergency_blueprints():
    """List all emergency vehicle blueprints available."""
    try:
        world  = get_world()
        bpl    = world.get_blueprint_library()
        result = sorted([bp.id for bp in bpl.filter("vehicle.*")
                         if any(kw in bp.id.lower() for kw in _EMERGENCY_KEYWORDS)])
        return jsonify({"success": True, "blueprints": result})
    except Exception as e:
        logger.error(f"emergency_blueprints error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/tm/fix_all", methods=["POST"])
def tm_fix_all():
    """
    Apply strict TM lane/behaviour rules to ALL vehicles currently in the world.
    Use this to fix vehicles that are already spawned and driving in circles.
    """
    try:
        world = get_world()
        fixed, total = apply_behaviour_to_all(world)
        logger.info(f"TM fix applied to {fixed}/{total} vehicles")
        return jsonify({"success": True, "fixed": fixed, "total": total})
    except Exception as e:
        logger.error(f"tm_fix_all error: {e}")
        return jsonify({"success": False, "error": str(e)})
