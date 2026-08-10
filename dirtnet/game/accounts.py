"""
Account store (SQLite): stable principal id (pid) per login username, persisted
so it survives restarts. pid keys leaderboards / prizes / tickets.
"""

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE_PID = 10000

_DB_PATH = Path(
    os.environ.get("DIRT2_ACCOUNTS_DB")
    or Path(__file__).resolve().parents[1] / "data" / "accounts.db"
)
_conn = None


def _db():
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts(
                username TEXT    PRIMARY KEY,
                pid      INTEGER NOT NULL UNIQUE
            )""")
        _conn.commit()
    return _conn


def find_or_create_account(username):
    """Return the stable pid for `username`, creating it on first login."""
    row = _db().execute("SELECT pid FROM accounts WHERE username=?", (username,)).fetchone()
    if row:
        return row[0]
    top = _db().execute("SELECT MAX(pid) FROM accounts").fetchone()[0]
    pid = (top if top is not None else _BASE_PID - 1) + 1
    _db().execute("INSERT INTO accounts(username, pid) VALUES(?, ?)", (username, pid))
    _db().commit()
    logger.info(f"accounts: new account '{username}' -> pid={pid}")
    return pid


def username_for(pid):
    """Login username (PSN online id) for a pid, or None."""
    row = _db().execute("SELECT username FROM accounts WHERE pid=?", (int(pid),)).fetchone()
    return row[0] if row else None
