from flask import Blueprint, request, jsonify
import random
import logging

from utils.helpers import get_world, require_carla
from core.vehicles import (
    list_blueprints, 
    list_emergency_blueprints,
    try_spawn_actor_with_retries,
    configure_tm,
    spawn_npc_batch,
    spawn_walker_batch,
    destroy_actors
)

blueprint = Blueprint("vehicles", __name__)
logger = logging.getLogger(__name__)

# --- Blueprints ---

@blueprint.route("/blueprints")
@require_carla
def blueprints_list():
    filt = request.args.get("filter", "*")
    world = get_world()
    bps = list_blueprints(world, filt)
    return jsonify({"success": True, "blueprints": bps})


@blueprint.route("/blueprints/emergency")
@require_carla
def blueprints_emergency():
    world = get_world()
    bps = list_emergency_blueprints(world)
    return jsonify({"success": True, "blueprints": bps})


# --- Spawning ---

@blueprint.route("/spawn/vehicle", methods=["POST"])
@require_carla
def spawn_v():
    d = request.json or {}
    world = get_world()
    bp_id = d.get("blueprint", "vehicle.tesla.model3")
    
    try:
        bp = world.get_blueprint_library().find(bp_id)
    except Exception:
        return jsonify({"success": False, "error": f"Blueprint not found: {bp_id}"}), 404

    spawn_points = world.get_map().get_spawn_points()
    actor = try_spawn_actor_with_retries(world, bp, spawn_points)
    if actor:
        configure_tm(actor, d.get("behavior", "normal"))
        return jsonify({"success": True, "actor_id": actor.id})
    return jsonify({"success": False, "error": "Spawn failed — all points occupied"})


@blueprint.route("/spawn/npc", methods=["POST"])
@require_carla
def spawn_n():
    d = request.json or {}
    count = spawn_npc_batch(get_world(), int(d.get("count", 10)))
    return jsonify({"success": True, "spawned": count})


@blueprint.route("/spawn/emergency", methods=["POST"])
@require_carla
def spawn_e():
    d = request.json or {}
    world = get_world()
    emerg_ids = list_emergency_blueprints(world)
    
    if not emerg_ids:
        return jsonify({"success": False, "error": "No emergency vehicle blueprints found"})

    bp_id = d.get("blueprint") or emerg_ids[0]
    try:
        bp = world.get_blueprint_library().find(bp_id)
    except Exception:
        bp = world.get_blueprint_library().find(emerg_ids[0])

    spawn_points = world.get_map().get_spawn_points()
    actor = try_spawn_actor_with_retries(world, bp, spawn_points)
    if actor:
        configure_tm(actor, "aggressive")
        return jsonify({"success": True, "actor_id": actor.id, "blueprint": actor.type_id})
    return jsonify({"success": False, "error": "Emergency spawn failed"})


@blueprint.route("/spawn/walker", methods=["POST"])
@require_carla
def spawn_w():
    d = request.json or {}
    spawned_ids = spawn_walker_batch(get_world(), int(d.get("count", 5)))
    return jsonify({"success": True, "spawned": len(spawned_ids) if isinstance(spawned_ids, list) else spawned_ids})


# --- Destruction ---

@blueprint.route("/destroy/actor", methods=["POST"])
@require_carla
def destroy_actor():
    actor_id = int((request.json or {}).get("id", 0))
    world = get_world()
    count = destroy_actors(world, actor_id=actor_id)
    if count:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": f"Actor {actor_id} not found"}), 404


@blueprint.route("/destroy/all", methods=["POST"])
@require_carla
def destroy_all():
    filt = (request.json or {}).get("filter", "vehicle.*")
    world = get_world()
    count = destroy_actors(world, actor_filter=filt)
    return jsonify({"success": True, "destroyed": count})
