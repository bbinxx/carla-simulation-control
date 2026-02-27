import os
import re

app_content = open("d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/app.py", "r", encoding="utf-8").read()

def create_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")

# Extract imports and init
os.makedirs("d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/config", exist_ok=True)
os.makedirs("d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/utils", exist_ok=True)
os.makedirs("d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/routes", exist_ok=True)

# we will just do this a safer way: we will read specific parts.
# Let's extract by sections delimited by `# ─── ` comments.

sections = re.split(r'\n# ─── (.*?) ────────────────────────────────────────────────────────────(?:──)*\n', app_content)

header_and_state = sections[0]
parsed_sections = {sections[i].strip(): sections[i+1] for i in range(1, len(sections), 2)}

core_state = """
import threading

carla_state = {
    "client": None,
    "world": None,
    "connected": False,
    "host": "",
    "port": 2000,
    "map": "",
    "tm_port": 8000,
    "debug_bboxes": False,
}
state_lock = threading.Lock()
DB_PATH = "history.db"
"""
create_file("d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/config/state.py", core_state)

utils_content = """
import carla
from config.state import carla_state, state_lock

TL_STATE_MAP = {
    "red":    carla.TrafficLightState.Red,
    "green":  carla.TrafficLightState.Green,
    "yellow": carla.TrafficLightState.Yellow,
    "off":    carla.TrafficLightState.Off,
}

""" + parsed_sections.get("Helpers", "").replace("""
TL_STATE_MAP = {
    "red":    carla.TrafficLightState.Red,
    "green":  carla.TrafficLightState.Green,
    "yellow": carla.TrafficLightState.Yellow,
    "off":    carla.TrafficLightState.Off,
}""", "")

create_file("d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/utils/helpers.py", utils_content)

# We will put all routes into routes/ with Blueprints
route_template = """
from flask import Blueprint, request, jsonify, render_template, current_app
import carla
import sqlite3
import random
import time
import base64
import numpy as np
import cv2

from config.state import carla_state, state_lock, DB_PATH
from utils.helpers import get_world, get_actors_info, get_spectator_transform, make_weather, TL_STATE_MAP, WEATHER_PRESETS

blueprint = Blueprint('{name}', __name__)
"""

def make_route_file(name, code, replace_app=True):
    content = route_template.format(name=name) + "\n"
    if replace_app:
        content += code.replace("@app.route", "@blueprint.route").replace("app.logger", "current_app.logger")
    else:
        content += code
    create_file(f"d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/routes/{name}.py", content)

make_route_file("main", parsed_sections.get("Routes", ""))
make_route_file("history", parsed_sections.get("DB & History", ""))
make_route_file("spectator", parsed_sections.get("Spectator API", ""))
make_route_file("weather", parsed_sections.get("Weather API", ""))
make_route_file("traffic", parsed_sections.get("Traffic Lights API", ""))
make_route_file("environment", parsed_sections.get("Environment Objects API", ""))
make_route_file("blueprints_api", parsed_sections.get("Blueprints", ""))

# Some sections might not exist exactly, check spawning
spawn_code = parsed_sections.get("Spawn API", "")
make_route_file("spawner", spawn_code)

destroy_code = parsed_sections.get("Destroy API", "")
make_route_file("destroy", destroy_code)


app_py_new = """
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
    while True:
        try:
            with state_lock:
                connected = carla_state.get("connected")
                enabled = carla_state.get("debug_bboxes", False)
                client = carla_state.get("client")
            
            if connected and enabled and client:
                world = client.get_world()
                debug = world.debug
                
                # Vehicles
                for v in world.get_actors().filter("vehicle.*"):
                    t = v.get_transform()
                    b = v.bounding_box
                    if b.extent.x > 0:
                        box = carla.BoundingBox(t.location + b.location, b.extent)
                        debug.draw_box(box, t.rotation, 0.05, carla.Color(255, 120, 0), 0.6)
                        
                        z_val = b.extent.z + 1.2
                        loc = t.location + carla.Location(0, 0, z_val)
                        debug.draw_string(loc, f"ID:{v.id}", False, carla.Color(255, 120, 0), 0.6, True)
                
                # Traffic Lights
                for tl in world.get_actors().filter("traffic.traffic_light*"):
                    t = tl.get_transform()
                    s = str(tl.get_state()).split('.')[-1]
                    c = carla.Color(0,255,0) if s == "Green" else (carla.Color(255,0,0) if s == "Red" else carla.Color(255,255,0))
                    
                    loc = t.location + carla.Location(0, 0, 1.0)
                    debug.draw_string(loc, f"TL:{tl.id} {s}", False, c, 0.6, True)
                    
                    # Draw subtle box for TL
                    debug.draw_box(carla.BoundingBox(t.location, carla.Vector3D(0.5, 0.5, 2.0)), t.rotation, 0.05, c, 0.6)
                    
        except Exception:
            pass
        time.sleep(0.5)

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
"""
create_file("d:/DEV/CodeBase/MAIN_PRO/AI_TRAFFIC/CARLA_CONTROL/app.py", app_py_new)
print("Modularization complete!")
