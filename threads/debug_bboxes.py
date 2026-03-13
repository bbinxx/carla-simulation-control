"""
Debug bounding-box overlay thread.

Draws coloured boxes + labels around vehicles and traffic lights in the
CARLA world using the debug drawing API. Uses the WorldCache actor list
so it shares the same 2-second snapshot as all other consumers — no extra
get_actors() RPC per cycle.
"""
import threading
import time
import logging
import carla

from utils.cache import world_cache
from config.state import carla_state, state_lock

logger = logging.getLogger(__name__)

LIFE  = 0.8    # debug primitive lifetime (s) — must be > SLEEP
SLEEP = 0.5    # loop interval (was 0.35 — reduced to cut CARLA load)


def debug_bboxes_loop():
    while True:
        try:
            with state_lock:
                connected = carla_state.get("connected", False)
                enabled   = carla_state.get("debug_bboxes", False)

            if connected and enabled:
                world = world_cache.get_world()
                if world is None:
                    time.sleep(SLEEP)
                    continue

                debug  = world.debug
                # Single cached fetch — no extra RPC
                actors = world_cache.get_actors(world)

                for v in (a for a in actors if a.type_id.startswith("vehicle.")):
                    t = v.get_transform()
                    b = v.bounding_box
                    if b.extent.x > 0:
                        box = carla.BoundingBox(t.location + b.location, b.extent)
                        debug.draw_box(box, t.rotation, 0.05,
                                       carla.Color(255, 120, 0), LIFE)
                        loc = t.location + carla.Location(0, 0, b.extent.z + 1.2)
                        debug.draw_string(loc, f"ID:{v.id}", False,
                                          carla.Color(255, 200, 0), LIFE, True)

                for tl in (a for a in actors if "traffic_light" in a.type_id):
                    t = tl.get_transform()
                    s = str(tl.get_state()).split(".")[-1]
                    c = (carla.Color(0, 255, 0)   if s == "Green" else
                         carla.Color(255, 0,   0) if s == "Red"  else
                         carla.Color(255, 200, 0))
                    loc = t.location + carla.Location(0, 0, 1.0)
                    debug.draw_string(loc, f"TL:{tl.id} {s}", False, c, LIFE, True)

        except Exception as e:
            logger.debug(f"debug_bboxes_loop: {e}")

        time.sleep(SLEEP)


def start():
    """Start the debug bbox daemon thread."""
    threading.Thread(target=debug_bboxes_loop, daemon=True,
                     name="debug-bboxes").start()
    logger.info("Debug BBox thread started")
