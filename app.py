"""
app.py — CARLA Control Panel application factory
"""
import os
import logging
from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    # Secret key — set CARLA_SECRET_KEY env var in production
    app.secret_key = os.environ.get("CARLA_SECRET_KEY", "carla_control_dev_secret")

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # suppress request logs
    app.logger.setLevel(logging.INFO)

    # Database
    from config.db import init_db
    init_db()

    # Background threads
    from threads.debug_bboxes import start as start_bboxes
    start_bboxes()

    # NOTE: simulation_loop (world.tick) kept in core/background.py for now;
    # it requires synchronous mode and is separate from the bbox overlay.
    from core.background import start_background_tasks
    start_background_tasks()

    # Blueprints
    from routes.main            import blueprint as bp_main
    from routes.connection      import blueprint as bp_connection
    from routes.history         import blueprint as bp_history
    from routes.spectator       import blueprint as bp_spectator
    from routes.weather         import blueprint as bp_weather
    from routes.traffic         import blueprint as bp_traffic
    from routes.environment     import blueprint as bp_environment
    from routes.vehicles        import blueprint as bp_vehicles
    from routes.lane            import blueprint as bp_lane
    from routes.camera          import blueprint as bp_camera

    for bp in [
        bp_main, bp_connection, bp_history, bp_spectator,
        bp_weather, bp_traffic, bp_environment,
        bp_vehicles, bp_lane, bp_camera,
    ]:
        app.register_blueprint(bp)

    app.logger.info("CARLA Control Panel ready")
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
