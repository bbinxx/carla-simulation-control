import threading

DEFAULT_TM_PORT = 8000

carla_state = {
    "client":       None,
    "connected":    False,
    "host":         "",
    "port":         2000,
    "map":          "",
    "tm":           None,
    "tm_port":      DEFAULT_TM_PORT,
    "debug_bboxes": False,
    "stream_width":  640,
    "stream_height": 360,
    "stream_quality": 80,
    "control_enabled": True,
    "agents": {}
}

state_lock = threading.Lock()
