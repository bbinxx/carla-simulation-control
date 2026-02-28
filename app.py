from flask import Flask
import logging
import sqlite3
import threading
import time
import carla

from config.state import DB_PATH, carla_state, state_lock

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.secret_key = "carla_control_secret"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS hosts
                 (host TEXT, port INTEGER, last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (host, port))''')
    c.execute('''CREATE TABLE IF NOT EXISTS locations
                 (name TEXT PRIMARY KEY, x REAL, y REAL, z REAL, pitch REAL, yaw REAL, roll REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS last_connection
                 (id INTEGER PRIMARY KEY CHECK (id = 1), host TEXT, port INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def debug_bboxes_loop():
    # Tuned for high responsiveness and zero flicker
    LIFE = 0.25      # seconds each debug primitive stays visible
    SLEEP = 0.15    # loop interval
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

                # 1. Vehicles
                for v in world.get_actors().filter("vehicle.*"):
                    loc = v.get_location()
                    if loc.distance(spec_loc) > MAX_DIST:
                        continue
                    
                    t = v.get_transform()
                    b = v.bounding_box
                    if b.extent.x > 0:
                        # Draw Box
                        box_loc = t.location + t.get_forward_vector() * b.location.x + \
                                  t.get_right_vector() * b.location.y + \
                                  t.get_up_vector() * b.location.z
                                  
                        box = carla.BoundingBox(t.location + b.location, b.extent)
                        debug.draw_box(box, t.rotation, THICKNESS, carla.Color(0, 255, 255), LIFE)
                        
                        # Info Label: ID + Speed
                        vel = v.get_velocity()
                        speed = 3.6 * (vel.x**2 + vel.y**2 + vel.z**2)**0.5
                        label_loc = t.location + carla.Location(0, 0, b.extent.z + 1.0)
                        debug.draw_string(label_loc, f"V:{v.id} [{speed:.1f}kmh]", False, 
                                        carla.Color(255, 255, 0), LIFE, True)

                # 2. Walkers
                for w in world.get_actors().filter("walker.*"):
                    loc = w.get_location()
                    if loc.distance(spec_loc) > MAX_DIST:
                        continue
                    
                    t = w.get_transform()
                    b = w.bounding_box
                    box = carla.BoundingBox(t.location + b.location, b.extent)
                    debug.draw_box(box, t.rotation, THICKNESS, carla.Color(255, 0, 255), LIFE)
                    
                    label_loc = t.location + carla.Location(0, 0, b.extent.z + 0.5)
                    debug.draw_string(label_loc, f"P:{w.id}", False, carla.Color(255, 100, 255), LIFE, True)

                # 3. Traffic Lights
                for tl in world.get_actors().filter("traffic.traffic_light*"):
                    t = tl.get_transform()
                    if t.location.distance(spec_loc) > MAX_DIST:
                        continue
                        
                    s = str(tl.get_state()).split('.')[-1]
                    color = carla.Color(0, 255, 0) if s == "Green" else (
                            carla.Color(255, 0, 0) if s == "Red" else carla.Color(255, 200, 0))
                    
                    # Box around the light head area
                    debug.draw_box(
                        carla.BoundingBox(t.location + carla.Location(0,0,1.5), carla.Vector3D(0.4, 0.4, 1.2)),
                        t.rotation, THICKNESS, color, LIFE)
                    
                    label_loc = t.location + carla.Location(0, 0, 3.0)
                    debug.draw_string(label_loc, f"TL:{tl.id} {s}", False, color, LIFE, True)

        except Exception:
            pass
        time.sleep(SLEEP)


def carla_tick_loop():
    """Tick the CARLA world continuously for synchronous mode."""
    while True:
        try:
            with state_lock:
                connected = carla_state.get("connected")
                client = carla_state.get("client")
            
            if connected and client:
                world = client.get_world()
                world.tick()
        except Exception:
            pass
        time.sleep(0.005)


threading.Thread(target=debug_bboxes_loop, daemon=True).start()
threading.Thread(target=carla_tick_loop, daemon=True).start()

# Register Blueprints
from routes.main import blueprint as bp_main
from routes.history import blueprint as bp_history
from routes.spectator import blueprint as bp_spectator
from routes.weather import blueprint as bp_weather
from routes.traffic import blueprint as bp_traffic
from routes.environment import blueprint as bp_environment
from routes.blueprints_api import blueprint as bp_blueprints
from routes.spawner import blueprint as bp_spawner
from routes.destroy import blueprint as bp_destroy

app.register_blueprint(bp_main)
app.register_blueprint(bp_history)
app.register_blueprint(bp_spectator)
app.register_blueprint(bp_weather)
app.register_blueprint(bp_traffic)
app.register_blueprint(bp_environment)
app.register_blueprint(bp_blueprints)
app.register_blueprint(bp_spawner)
app.register_blueprint(bp_destroy)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
