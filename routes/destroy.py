# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\routes\destroy.py
from flask import Blueprint, request, jsonify
import logging

from utils.helpers import get_world

blueprint = Blueprint('destroy', __name__)
logger = logging.getLogger(__name__)


@blueprint.route("/destroy/actor", methods=["POST"])
def destroy_actor():
    try:
        actor_id = int((request.json or {}).get("id", 0))
        world  = get_world()
        actor  = world.get_actor(actor_id)
        if not actor:
            return jsonify({"success": False, "error": f"Actor {actor_id} not found"})
        actor.destroy()
        logger.info(f"Destroyed actor {actor_id}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"destroy_actor error: {e}")
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/destroy/all", methods=["POST"])
def destroy_all():
    try:
        filt  = (request.json or {}).get("filter", "vehicle.*")
        world = get_world()

        # CARLA filter('*') is not universal — get_actors() for all, else filter normally
        if filt in ("*", "all"):
            actor_list = list(world.get_actors())
        else:
            actor_list = list(world.get_actors().filter(filt))

        # Never destroy the spectator
        spectator_id = world.get_spectator().id
        destroyed = 0
        for a in actor_list:
            if a.id == spectator_id:
                continue
            try:
                a.destroy()
                destroyed += 1
            except Exception as de:
                logger.warning(f"Could not destroy {a.id}: {de}")

        logger.info(f"Destroyed {destroyed} actors (filter: {filt})")
        return jsonify({"success": True, "destroyed": destroyed})
    except Exception as e:
        logger.error(f"destroy_all error: {e}")
        return jsonify({"success": False, "error": str(e)})
