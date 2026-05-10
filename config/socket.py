from flask_socketio import SocketIO

# We use threading async_mode as eventlet monkey patching can interfere with CARLA threads.
# cors_allowed_origins="*" allows connection from frontend without cross-origin issues
socketio = SocketIO(async_mode='threading', cors_allowed_origins="*")
