"""
core/database.py  — legacy shim
================================
Kept for routes/camera.py compatibility. Delegates to config/db.py so there
is a single source of truth for the DB path and connection management.
"""
from config.db import get_db, DB_PATH, init_db   # re-export for legacy callers
import sqlite3


def get_connection(use_row_factory=True):
    """
    Legacy helper used by routes/camera.py.
    Returns a *new* sqlite3 connection (caller must close it).
    Prefer the `get_db()` context manager for new code.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    if use_row_factory:
        conn.row_factory = sqlite3.Row
    return conn
