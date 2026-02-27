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
}
state_lock = threading.Lock()
DB_PATH = "history.db"
