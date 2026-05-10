import sqlite3
import threading
import logging
from contextlib import contextmanager
from typing import Optional

DB_PATH = "history.db"
logger = logging.getLogger(__name__)


class DBLocal(threading.local):
    conn: Optional[sqlite3.Connection]

    def __init__(self):
        self.conn = None


_local = DBLocal()


def create_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row

    # Sync settings for easier git version control
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA temp_store=MEMORY")

    return conn


@contextmanager
def get_db():
    if _local.conn is None:
        _local.conn = create_connection()
        logger.info("SQLite connection created")

    conn: sqlite3.Connection = _local.conn

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_db():
    if _local.conn is not None:
        _local.conn.close()
        _local.conn = None
        logger.info("SQLite connection closed")


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS hosts (
            host TEXT,
            port INTEGER,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (host, port)
        );

        CREATE TABLE IF NOT EXISTS locations (
            name TEXT PRIMARY KEY,
            x REAL,
            y REAL,
            z REAL,
            pitch REAL,
            yaw REAL,
            roll REAL
        );

        CREATE TABLE IF NOT EXISTS last_connection (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            host TEXT,
            port INTEGER
        );

        CREATE TABLE IF NOT EXISTS camera_setups (
            name TEXT PRIMARY KEY,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS camera_metadata (
            actor_id INTEGER PRIMARY KEY,
            name TEXT
        );
        """)

    logger.info("Database initialized")