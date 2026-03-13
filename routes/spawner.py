from flask import Blueprint, request, jsonify
import carla
import random
import time
import logging

from utils.helpers import get_world, require_carla
from core.vehicles import spawn_npc_batch, spawn_walker_batch

blueprint = Blueprint("spawner", __name__)
logger    = logging.getLogger(__name__)


# ── Fix 15: reliable spawn with delay between retries ────────────────────────

def _try_spawn(world, bp, spawn_points, max_tries=5):
    """
    Attempt to spawn actor at up to max_tries spawn points.
    Brief pause between retries avoids flooding CARLA with rapid-fire calls.
    """
    for sp in spawn_points[:max_tries]:
        actor = world.try_spawn_actor(bp, sp)
        if actor:
            return actor
        time.sleep(0.05)
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@blueprint.route("/spawn/vehicle", methods=["POST"])
@require_carla
def spawn_v():
    d     = request.json or {}
    world = get_world()
    bpl   = world.get_blueprint_library()
    bp_id = d.get("blueprint", "vehicle.tesla.model3")
    try:
        bp = bpl.find(bp_id)
    except Exception:
        return jsonify({"success": False, "error": f"Blueprint not found: {bp_id}"}), 404

    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)
    actor = _try_spawn(world, bp, spawn_points)
    if actor:
        from core.vehicles import configure_tm
        configure_tm(actor, d.get("behavior", "normal"))
        return jsonify({"success": True, "actor_id": actor.id})
    return jsonify({"success": False, "error": "Spawn failed — all points occupied"})


@blueprint.route("/spawn/npc", methods=["POST"])
@require_carla
def spawn_n():
    d     = request.json or {}
    count = spawn_npc_batch(get_world(), int(d.get("count", 10)))
    return jsonify({"success": True, "spawned": count})


@blueprint.route("/spawn/emergency", methods=["POST"])
@require_carla
def spawn_e():
    d     = request.json or {}
    world = get_world()
    emerg = [b for b in world.get_blueprint_library().filter("vehicle.*")
             if any(kw in b.id.lower() for kw in ["police", "ambulance", "firetruck"])]
    if not emerg:
        return jsonify({"success": False, "error": "No emergency vehicle blueprints found"})

    bp_id = d.get("blueprint") or random.choice(emerg).id
    try:
        bp = world.get_blueprint_library().find(bp_id)
    except Exception:
        bp = random.choice(emerg)

    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)
    actor = _try_spawn(world, bp, spawn_points)
    if actor:
        from core.vehicles import configure_tm
        configure_tm(actor, "aggressive")
        return jsonify({"success": True, "actor_id": actor.id, "blueprint": actor.type_id})
    return jsonify({"success": False, "error": "Emergency spawn failed"})


@blueprint.route("/spawn/walker", methods=["POST"])
@require_carla
def spawn_w():
    d     = request.json or {}
    count = spawn_walker_batch(get_world(), int(d.get("count", 5)))
    return jsonify({"success": True, "spawned": count})