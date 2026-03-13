import threading
import time
import logging

logger = logging.getLogger(__name__)


class WorldCache:
    """
    Caches the CARLA world object and actor snapshots.
    - World is invalidated on map load or disconnect.
    - Actors are refreshed at most once per ACTOR_TTL seconds.
    - All access is thread-safe.
    """
    ACTOR_TTL = 2.0   # seconds between full actor list refreshes

    def __init__(self):
        self._lock = threading.Lock()
        self._world = None
        self._actors = []
        self._actors_ts = 0.0

    def set_world(self, world):
        """Cache a freshly obtained world object; clears the actor cache."""
        with self._lock:
            self._world = world
            self._actors = []
            self._actors_ts = 0.0

    def invalidate(self):
        """Evict all cached data (call on disconnect / map reload)."""
        with self._lock:
            self._world = None
            self._actors = []
            self._actors_ts = 0.0

    def get_world(self):
        """Return the cached world, or None if not connected."""
        with self._lock:
            return self._world

    def get_actors(self, world=None, force=False):
        """
        Return cached actor list or refresh if stale.
        If world is omitted, uses the cached world.
        Returns an empty list if neither is available.
        """
        now = time.monotonic()
        with self._lock:
            if not force and (now - self._actors_ts) < self.ACTOR_TTL:
                return self._actors
            w = world or self._world

        if w is None:
            return []

        # Refresh outside lock to avoid blocking other threads
        try:
            actors = list(w.get_actors())
            with self._lock:
                self._actors = actors
                self._actors_ts = time.monotonic()
            return actors
        except Exception as e:
            logger.warning(f"WorldCache actor refresh failed: {e}")
            with self._lock:
                return self._actors


# Module-level singleton used by all routes and threads
world_cache = WorldCache()
