"""
core/background.py
==================
Simulation tick loop (synchronous mode keepalive + precision red-light stop).

The debug bbox overlay loop has been moved to threads/debug_bboxes.py and
now uses the WorldCache actor list — this file only manages world.tick().
"""
import threading
import time
import logging
import carla

from config.state import carla_state, state_lock
from core.vehicles import precision_red_light_stop, handle_green_light_resume
from utils.cache import world_cache

logger = logging.getLogger(__name__)


def simulation_loop():
    """
    Calls world.tick() in synchronous mode at ~30 Hz.
    Runs precision_red_light_stop every 10 ticks to reduce RPC overhead.
    """
    tick_count: int = 0
    while True:
        with state_lock:
            world     = carla_state.get("world")
            connected = carla_state.get("connected")

        # Prefer world from WorldCache if state doesn't have it (migrating)
        if connected and world is None:
            world = world_cache.get_world()

        if world and connected:
            try:
                world.tick()
                tick_count += 1

                if tick_count % 10 == 0:
                    # Fetch actors once per cycle for all logic functions
                    actors = list(world.get_actors())
                    precision_red_light_stop(world, actors)
                    handle_green_light_resume(world, actors)

            except carla.client.TimeoutException:
                logger.warning("CARLA tick timeout — simulator is slow or network is saturated")
            except Exception as e:
                logger.error(f"Simulation loop error: {e}")

            time.sleep(0.02)   # ~50 Hz cap — provides breathing room
        else:
            time.sleep(0.5)


def start_background_tasks():
    """Start the simulation tick loop daemon thread."""
    threading.Thread(target=simulation_loop, daemon=True,
                     name="sim-loop").start()
    logger.info("Simulation loop started")
