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

    # Disable static file caching for development
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Logging with Rich
    from rich.logging import RichHandler
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)]
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

    # SocketIO
    from config.socket import socketio
    import routes.socket  # register handlers
    socketio.init_app(app)

    # app.logger.info("CARLA Control Panel ready")
    return app


app = create_app()

if __name__ == "__main__":
    import os
    import webbrowser
    from threading import Timer
    from config.socket import socketio

    # Gather extra files (HTML/JS/CSS) to trigger auto-reloads when changed
    extra_dirs = ['templates', 'static']
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)

    Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    # Draw beautiful startup panel (only in the actual reloader child process to avoid printing twice)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        console = Console()
        txt = Text()
        txt.append(" CARLA Control Panel Backend\n", style="bold cyan")
        txt.append("=============================\n\n", style="dim")
        txt.append(" State      : ", style="bold")
        txt.append("ONLINE\n", style="bold green")
        txt.append(" Address    : ", style="bold")
        txt.append("http://127.0.0.1:5000\n", style="yellow")
        txt.append(" Stream     : ", style="bold")
        txt.append("Socket.IO (Raw Binary)\n", style="bold magenta")
        txt.append(" Watcher    : ", style="bold")
        txt.append("Active (Watchdog)\n", style="bold blue")
        
        console.print(Panel(txt, title="🚀 Server Ready", border_style="green", expand=False))
        console.print("[dim]Listening for connections and file changes...[/dim]\n")

    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True, extra_files=extra_files)
