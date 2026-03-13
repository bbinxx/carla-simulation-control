import sqlite3
import threading
import logging
from contextlib import contextmanager

DB_PATH = "history.db"
_local = threading.local()
logger = logging.getLogger(__name__)


@contextmanager
def get_db():
    """
    Thread-local SQLite connection with auto-commit/rollback.
    Usage:
        with get_db() as conn:
            conn.execute("SELECT ...")
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    conn = _local.conn
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS hosts (
                host TEXT, port INTEGER,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (host, port)
            );
            CREATE TABLE IF NOT EXISTS locations (
                name TEXT PRIMARY KEY,
                x REAL, y REAL, z REAL,
                pitch REAL, yaw REAL, roll REAL
            );
            CREATE TABLE IF NOT EXISTS last_connection (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                host TEXT, port INTEGER
            );
            CREATE TABLE IF NOT EXISTS camera_setups (
                name TEXT PRIMARY KEY,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    logger.info("Database initialized")
