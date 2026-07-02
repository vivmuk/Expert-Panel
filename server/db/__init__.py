import os
import sqlite3

from ..config import Config

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def _db_path():
    return os.path.join(Config.DATA_DIR, "engagements.db")


def connect():
    """Short-lived connection with WAL + busy timeout; caller closes."""
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    with open(_SCHEMA_PATH) as f:
        schema = f.read()
    conn = connect()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
