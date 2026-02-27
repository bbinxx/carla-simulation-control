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
    LIFE = 1.0      # seconds each debug primitive stays visible
    SLEEP = 0.35    # loop interval — must be << LIFE to prevent gap-flicker
    while True:
        try:
            with state_lock:
                connected = carla_state.get("connected")
                enabled   = carla_state.get("debug_bboxes", False)
                client    = carla_state.get("client")

            if connected and enabled and client:
                world = client.get_world()
                debug = world.debug

                for v in world.get_actors().filter("vehicle.*"):
                    t = v.get_transform()
                    b = v.bounding_box
                    if b.extent.x > 0:
                        box = carla.BoundingBox(t.location + b.location, b.extent)
                        debug.draw_box(box, t.rotation, 0.05, carla.Color(255, 120, 0), LIFE)
                        loc = t.location + carla.Location(0, 0, b.extent.z + 1.2)
                        debug.draw_string(loc, f"ID:{v.id}", False, carla.Color(255, 200, 0), LIFE, True)

                for tl in world.get_actors().filter("traffic.traffic_light*"):
                    t = tl.get_transform()
                    s = str(tl.get_state()).split('.')[-1]
                    c = carla.Color(0, 255, 0) if s == "Green" else (
                        carla.Color(255, 0, 0) if s == "Red" else carla.Color(255, 200, 0))
                    loc = t.location + carla.Location(0, 0, 1.0)
                    debug.draw_string(loc, f"TL:{tl.id} {s}", False, c, LIFE, True)
                    debug.draw_box(
                        carla.BoundingBox(t.location, carla.Vector3D(0.5, 0.5, 2.0)),
                        t.rotation, 0.05, c, LIFE)

        except Exception as e:
            pass   # world may not be ready yet
        time.sleep(SLEEP)


threading.Thread(target=debug_bboxes_loop, daemon=True).start()

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
    app.run(host='0.0.0.0', port=5000)
