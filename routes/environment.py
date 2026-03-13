from flask import Blueprint, request, jsonify
import carla
import logging

from utils.helpers import get_world, require_carla

blueprint = Blueprint("environment", __name__)
logger    = logging.getLogger(__name__)


def _build_label_map():
    label_names = [
        "NONE", "Buildings", "Fences", "Other", "Pedestrians", "Poles",
        "RoadLines", "Roads", "Sidewalks", "Vegetation", "Car", "Walls",
        "TrafficSigns", "Sky", "Ground", "Bridge", "RailTrack", "GuardRail",
        "TrafficLight", "Static", "Dynamic", "Water", "Terrain",
        "Truck", "Motorcycle", "Bicycle", "Bus",
    ]
    m = {}
    for name in label_names:
        val = getattr(carla.CityObjectLabel, name, None)
        if val is not None:
            m[name] = val
    m["None"] = m.get("NONE")
    m["Any"]  = None
    return m


_LABEL_MAP = _build_label_map()


@blueprint.route("/env_objects/toggle", methods=["POST"])
@require_carla
def env_objects_toggle():
    d         = request.json or {}
    label_str = d.get("label", "Any")
    enable    = bool(d.get("enable", True))
    world     = get_world()

    if label_str == "Any" or label_str not in _LABEL_MAP or _LABEL_MAP[label_str] is None:
        env_objs = []
        for lbl_val in _LABEL_MAP.values():
            if lbl_val is None:
                continue
            try:
                env_objs.extend(world.get_environment_objects(lbl_val))
            except Exception:
                pass
        ids = {o.id for o in env_objs}
    else:
        env_objs = world.get_environment_objects(_LABEL_MAP[label_str])
        ids      = {o.id for o in env_objs}

    if ids:
        world.enable_environment_objects(ids, enable)

    logger.info(f"Env objects {'shown' if enable else 'hidden'}: {label_str} ({len(ids)})")
    return jsonify({"success": True, "count": len(ids)})
