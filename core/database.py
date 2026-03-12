# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\core\database.py
import sqlite3
from config.state import DB_PATH

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

def get_connection(use_row_factory=True):
    """Return a database connection, optionally with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    if use_row_factory:
        conn.row_factory = sqlite3.Row
    return conn
