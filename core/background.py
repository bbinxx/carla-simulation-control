import threading
import time
import carla
import logging
from config.state import carla_state, state_lock
from core.vehicles import precision_red_light_stop

logger = logging.getLogger(__name__)

def debug_bboxes_loop():
    LIFE = 0.6      # seconds each debug primitive stays visible
    SLEEP = 0.5     # loop interval
    THICKNESS = 0.1 # line thickness
    MAX_DIST = 100  # meters from spectator to render
    
    while True:
        try:
            with state_lock:
                connected = carla_state.get("connected")
                enabled   = carla_state.get("debug_bboxes", False)
                client    = carla_state.get("client")

            if connected and enabled and client:
                world = client.get_world()
                debug = world.debug
                spec_loc = world.get_spectator().get_location()
                
                # Single robust fetch
                all_actors = world.get_actors()

                for a in all_actors:
                    loc = a.get_location()
                    if loc.distance(spec_loc) > MAX_DIST:
                        continue
                        
                    t = a.get_transform()
                    typ = a.type_id
                    
                    if typ.startswith("vehicle"):
                        b = a.bounding_box
                        if b.extent.x > 0:
                            box = carla.BoundingBox(t.location + b.location, b.extent)
                            debug.draw_box(box, t.rotation, THICKNESS, carla.Color(0, 255, 255), LIFE)
                            vel = a.get_velocity()
                            speed = 3.6 * (vel.x**2 + vel.y**2 + vel.z**2)**0.5
                            debug.draw_string(t.location + carla.Location(0, 0, b.extent.z + 1.0), 
                                            f"V:{a.id} [{speed:.1f}kmh]", False, carla.Color(255, 255, 0), LIFE, True)
                                            
                    elif typ.startswith("walker"):
                        b = a.bounding_box
                        box = carla.BoundingBox(t.location + b.location, b.extent)
                        debug.draw_box(box, t.rotation, THICKNESS, carla.Color(255, 0, 255), LIFE)
                        debug.draw_string(t.location + carla.Location(0, 0, b.extent.z + 0.5), 
                                        f"P:{a.id}", False, carla.Color(255, 100, 255), LIFE, True)
                                        
                    elif typ.startswith("traffic.traffic_light"):
                        s = str(a.get_state()).split('.')[-1]
                        color = carla.Color(0, 255, 0) if s == "Green" else (carla.Color(255, 0, 0) if s == "Red" else carla.Color(255, 200, 0))
                        debug.draw_box(carla.BoundingBox(t.location + carla.Location(0,0,1.5), carla.Vector3D(0.4, 0.4, 1.2)),
                                    t.rotation, THICKNESS, color, LIFE)
                        debug.draw_string(t.location + carla.Location(0, 0, 3.0), f"TL:{a.id} {s}", False, color, LIFE, True)

        except Exception:
            pass
        time.sleep(SLEEP)

def simulation_loop():
    tick_count = 0
    while True:
        with state_lock:
            world = carla_state.get("world")
            connected = carla_state.get("connected")

        if world and connected:
            try:
                world.tick()
                tick_count += 1
                
                # Only run precision stop every 10 ticks to save heavy RPC overhead
                if tick_count % 10 == 0:
                    precision_red_light_stop(world)
            except Exception:
                pass
            time.sleep(0.005)
        else:
            time.sleep(0.5)

def start_background_tasks():
    threading.Thread(target=debug_bboxes_loop, daemon=True).start()
    threading.Thread(target=simulation_loop, daemon=True).start()
    logger.info("Background tasks started")
