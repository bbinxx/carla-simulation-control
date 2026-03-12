# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\config\state.py
import threading

carla_state = {
    "client": None,
    "world": None,
    "connected": False,
    "host": "",
    "port": 2000,
    "map": "",
    "tm": None,
    "tm_port": 8000,
    "debug_bboxes": False,
    "stream_width": 640,
    "stream_height": 360,
    "agents": {}
}
state_lock = threading.Lock()
DB_PATH = "history.db"
