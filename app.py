# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\app.py
from flask import Flask
import logging

from core.database import init_db
from core.background import start_background_tasks

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.secret_key = "carla_control_secret"

# Initialize Data
init_db()

# Start Simulation Threads (Simulation Tick & Debug BBoxes)
start_background_tasks()

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
from routes.lane import blueprint as bp_lane

app.register_blueprint(bp_main)
app.register_blueprint(bp_history)
app.register_blueprint(bp_spectator)
app.register_blueprint(bp_weather)
app.register_blueprint(bp_traffic)
app.register_blueprint(bp_environment)
app.register_blueprint(bp_blueprints)
app.register_blueprint(bp_spawner)
app.register_blueprint(bp_destroy)
app.register_blueprint(bp_lane)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
