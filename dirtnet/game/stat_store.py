"""Persistent statistics store (SQLite): one row per (principal, car, stat_id).
car = 0xFFFF is the global (car-less) bucket. The value goes in the column
matching its type; class_name preserves the AnyData type to echo back on read."""
import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CAR_GLOBAL = 0xFFFF

_DB_PATH = Path(os.environ.get("DIRT2_STATS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "stats.db")
_conn = None


def _db():
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS stats(
                principal  INTEGER NOT NULL,
                car        INTEGER NOT NULL,
                stat_id    INTEGER NOT NULL,
                class_name TEXT    NOT NULL,
                ival       INTEGER,
                fval       REAL,
                sval       TEXT,
                updated    REAL,
                PRIMARY KEY (principal, car, stat_id)
            )""")
        _conn.commit()
        logger.info(f"stat_store: {_DB_PATH}")
    return _conn


def put(principal, stat_id, class_name, value, car=CAR_GLOBAL):
    """Upsert one stat. value type is inferred from class_name."""
    ival = fval = sval = None
    if class_name == "FloatStatistic":
        fval = float(value)
    elif class_name == "StringStatistic":
        sval = str(value)
    else:  # UInt8/16/32Statistic, integer-like
        ival = int(value)
    db = _db()
    db.execute(
        "INSERT INTO stats(principal,car,stat_id,class_name,ival,fval,sval,updated)"
        " VALUES(?,?,?,?,?,?,?,?)"
        " ON CONFLICT(principal,car,stat_id) DO UPDATE SET"
        " class_name=excluded.class_name, ival=excluded.ival,"
        " fval=excluded.fval, sval=excluded.sval, updated=excluded.updated",
        (int(principal), int(car), int(stat_id), class_name,
         ival, fval, sval, time.time()))
    db.commit()


def put_many(principal, stats, car=CAR_GLOBAL):
    """stats = iterable of (stat_id, class_name, value)."""
    n = 0
    for stat_id, class_name, value in stats:
        put(principal, stat_id, class_name, value, car=car)
        n += 1
    return n


def _row_value(row):
    class_name = row[0]
    if class_name == "FloatStatistic":
        return class_name, row[2]
    if class_name == "StringStatistic":
        return class_name, row[3]
    return class_name, row[1]


def get(principal, stat_id, car=CAR_GLOBAL):
    """(class_name, value) for one stat, or None. Falls back to the global row
    if a car-specific one is absent."""
    db = _db()
    for c in (car, CAR_GLOBAL):
        r = db.execute(
            "SELECT class_name,ival,fval,sval FROM stats"
            " WHERE principal=? AND car=? AND stat_id=?",
            (int(principal), int(c), int(stat_id))).fetchone()
        if r:
            return _row_value(r)
    return None


def get_all(principal, car=None):
    """List of (stat_id, class_name, value) for a principal. car=None -> every
    row; else that car (+ global)."""
    db = _db()
    if car is None:
        rows = db.execute(
            "SELECT stat_id,class_name,ival,fval,sval FROM stats"
            " WHERE principal=?", (int(principal),)).fetchall()
    else:
        rows = db.execute(
            "SELECT stat_id,class_name,ival,fval,sval FROM stats"
            " WHERE principal=? AND car IN (?,?)",
            (int(principal), int(car), CAR_GLOBAL)).fetchall()
    out = []
    for r in rows:
        cn, val = _row_value((r[1], r[2], r[3], r[4]))
        out.append((r[0], cn, val))
    return out
