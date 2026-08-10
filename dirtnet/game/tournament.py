"""
Tournament domain layer: tournament definitions, time-based rotation windows,
and leaderboard storage (SQLite).

Each tournament names the stat it ranks by, the sort direction, and an optional
eligibility gate. Scores come from the end-of-race stat bag.
"""
import contextlib
import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from game import accounts
from game.enums import PrizeGroupWire, RewardKind

logger = logging.getLogger(__name__)

# --- Rotation config ---------------------------------------------------------
TOURNAMENT_DURATION_SECONDS = 7 * 24 * 3600

# A Wednesday, so weekly windows run Wed 00:00 -> Wed 00:00 (tournaments end Wed).
_EPOCH = datetime(2025, 12, 31)  # noqa: DTZ001 - naive local wall-clock

# --- Tournament model --------------------------------------------------------
_UINT = "UInt32Statistic"
_FLOAT = "FloatStatistic"

# Display labels for ranked-score / criteria stat ids.
_STAT_LABEL = {
    0x01: "distance", 0x02: "lap time", 0x04: "wrecks",
    0x06: "longest slide", 0x07: "longest jump",
    0x0a: "finish position",
}

_OPS = {
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,  "<":  lambda a, b: a < b,
}


@dataclass(frozen=True)
class Eligibility:
    """Gate a race must pass to count toward a tournament (e.g. 0 wrecks)."""
    stat: int
    op: str
    threshold: float

    def met(self, stats):
        """(ok, reason)."""
        val = stats.get(self.stat)
        label = _STAT_LABEL.get(self.stat, f"0x{self.stat:02x}")
        if val is None:
            return False, f"{label} missing"
        ok = _OPS[self.op](val, self.threshold)
        return ok, f"{label}({val}) {self.op} {self.threshold} -> " \
                   f"{'PASS' if ok else 'FAIL'}"

    def text(self):
        return f"{_STAT_LABEL.get(self.stat, f'0x{self.stat:02x}')} " \
               f"{self.op} {self.threshold}"


@dataclass(frozen=True)
class Tournament:
    """One tournament definition, scored off the end-of-race stat bag."""
    tid: int              # persistent leaderboard key
    title: str            # display title
    rules: str            # rules text shown to players
    score: int            # ranked stat id
    cls: str = _UINT      # that stat's concrete type
    low: bool = True      # lower is better
    display_mul: float = 1.0   # display-only unit scale (e.g. m/s->km/h = 3.6)
    elig: "Eligibility | None" = None
    score_fn: "object | None" = None  # derive score from the bag, e.g. dist/time

    @property
    def score_label(self):
        return _STAT_LABEL.get(self.score, f"0x{self.score:02x}")

    def score_of(self, stats):
        """Ranked score from the end-of-race bag: derived via score_fn, else the
        single ranked stat's value (None if absent)."""
        if self.score_fn is not None:
            return self.score_fn(stats)
        return stats.get(self.score)

    @property
    def sort_text(self):
        return "lowest wins" if self.low else "highest wins"

    @property
    def is_float(self):
        return self.cls == _FLOAT

    def criteria_text(self):
        return self.elig.text() if self.elig else "any race counts"

    def check(self, stats):
        """(ok, reason) — does this race meet the criteria?"""
        return self.elig.met(stats) if self.elig else (True, "no criteria")

    def cast(self, value):
        """Coerce stored score to display type (floats to 2 dp). Display only;
        ranking uses the full-precision stored value."""
        return round(float(value), 2) if self.is_float else int(value)

    def leaderboard_value(self, raw):
        """Leaderboard cell value: unit-scaled for display. Scaled stats (e.g.
        top speed m/s->km/h) show as a whole number; others use cast()."""
        if self.display_mul != 1.0:
            return int(round(float(raw) * self.display_mul))
        return self.cast(raw)


# Fixed-id pool. featured() picks the active one per time window; tid never
# changes. `score` is the per-race stat id each tournament ranks by.
_POOL = [
    Tournament(1, "Longest Drift",      "Hang the tail out. Biggest slide takes it.",
               0x4a, _FLOAT, False),
    Tournament(2, "Biggest Jump",       "Send it. Get the most air.",
               0x4b, _FLOAT, False),
    Tournament(3, "Two-Wheel Master",   "Tip it up and hold on. Longest time on two wheels.",
               0x4c, _FLOAT, False),
    Tournament(4, "Average Speed", "Keep it flat out. Fastest average wins (km/h).",
               0x46, _FLOAT, False, display_mul=3.6, score_fn=lambda s: _avg_speed(s)),
    Tournament(5, "Most Rolls", "Barrel roll bonanza. Most rolls in a race wins.",
               0x4d, _UINT, False),  # 0x4d = per-race rolls
]


def _avg_speed(stats):
    """Per-race average speed (m/s) = distanceTravelled(0x46, m) / raceTime(0x47,
    ms). None if either is missing/zero."""
    dist = stats.get(0x46)
    t_ms = stats.get(0x47)
    if not dist or not t_ms:
        return None
    return dist / (t_ms / 1000.0)

def featured(window) -> Tournament:
    """Template tournament (definition) for a rotation window."""
    return _POOL[window % len(_POOL)]


def instance_id(window):
    """Unique DB id for the tournament instance at `window`, created on first
    use. Monotonic autoincrement id — the tid and leaderboard key, so each run
    of a repeating template gets its own board and prizes."""
    win = int(window)
    db = _db()
    row = db.execute(
        "SELECT id FROM tournament_instance WHERE window=?", (win,)).fetchone()
    if row:
        return row[0]
    # OR IGNORE + re-select: race-safe when the game and dashboard both create.
    db.execute(
        "INSERT OR IGNORE INTO tournament_instance(window, pool_idx) VALUES(?,?)",
        (win, win % len(_POOL)))
    db.commit()
    return db.execute(
        "SELECT id FROM tournament_instance WHERE window=?", (win,)).fetchone()[0]


def tournament(tid) -> Tournament:
    """Template definition behind an instance tid (via its stored pool_idx)."""
    row = _db().execute(
        "SELECT pool_idx FROM tournament_instance WHERE id=?", (tid,)).fetchone()
    return _POOL[row[0]] if row else _POOL[0]


# Prize tier templates: (group_type, group_size, reward_kind, amount_lo,
# amount_hi). group_type: ORDINAL -> "1st"/"2nd", PERCENT -> "TOP N%".
_PRIZE_TIERS = [
    (PrizeGroupWire.ORDINAL, 1, RewardKind.XP,  2000, 2500),  # 1st
    (PrizeGroupWire.ORDINAL, 2, RewardKind.XP,  1400, 1800),  # 2nd
    (PrizeGroupWire.ORDINAL, 3, RewardKind.XP,   900, 1300),  # 3rd
    (PrizeGroupWire.PERCENT, 10, RewardKind.XP,  500,  800),  # top 10%
    (PrizeGroupWire.PERCENT, 25, RewardKind.XP,  300,  450),  # top 25%
    (PrizeGroupWire.PERCENT, 50, RewardKind.XP,  150,  250),  # top 50%
]


def prizes_for(tid):
    """Prize tiers: (group_type, group_size, amount, kind). Amounts
    deterministic per tid (multiples of 100 in each range)."""
    rng = random.Random(tid)  # noqa: S311 - stable variety, not security
    return [(gt, gs, rng.randrange(lo, hi + 1, 100), kind)
            for gt, gs, kind, lo, hi in _PRIZE_TIERS]


def _ordinal(n):
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def prize_rows(tid):
    """Prizes for display: [{"place","amount","kind"}] (place = "1st"/"TOP 10%")."""
    out = []
    for gt, gs, amount, kind in prizes_for(tid):
        place = _ordinal(gs) if gt == PrizeGroupWire.ORDINAL else f"top {gs}%"
        out.append({"place": place, "amount": amount,
                    "kind": "XP" if kind == RewardKind.XP else "cash"})
    return out


# --- Rotation (wall-clock windows) -------------------------------------------
def current_window(now=None):
    """Absolute window index since _EPOCH (increments every DURATION seconds)."""
    now = now or datetime.now()  # noqa: DTZ005 - naive local wall-clock
    return int((now - _EPOCH).total_seconds() // TOURNAMENT_DURATION_SECONDS)


def active_tid(now=None):
    """Instance id of the currently-featured tournament."""
    return instance_id(current_window(now))


def window_start(win):
    return _EPOCH + timedelta(seconds=win * TOURNAMENT_DURATION_SECONDS)


def window_end(win):
    return window_start(win) + timedelta(seconds=TOURNAMENT_DURATION_SECONDS)


def seconds_until_change(win=None, now=None):
    now = now or datetime.now()  # noqa: DTZ005 - local wall-clock
    win = current_window(now) if win is None else win
    return max(0, int((window_end(win) - now).total_seconds()))


# --- Leaderboard data (persisted to SQLite) ----------------------------------
# One row per (tournament_id, principal): a player's best posted score.
_DB_PATH = Path(os.environ.get("DIRT2_TOURNAMENTS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "tournaments.db")
_conn = None


def _db():
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")   # concurrent reader + writer
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS tournament_board(
                tournament_id INTEGER NOT NULL,
                principal     INTEGER NOT NULL,
                name          TEXT    NOT NULL,
                score         REAL    NOT NULL,
                PRIMARY KEY (tournament_id, principal)
            )""")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS prize_claimed(
                tournament_id INTEGER NOT NULL,
                principal     INTEGER NOT NULL,
                PRIMARY KEY (tournament_id, principal)
            )""")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS tournament_instance(
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                window   INTEGER NOT NULL UNIQUE,
                pool_idx INTEGER NOT NULL
            )""")
        # Add timestamp columns to older DBs in place, seeding `now` for
        # pre-existing rows. suppress() ignores the error when they already exist.
        now = time.time()
        with contextlib.suppress(sqlite3.OperationalError):
            _conn.execute("ALTER TABLE tournament_board ADD COLUMN updated REAL")
        _conn.execute("UPDATE tournament_board SET updated=? WHERE updated IS NULL", (now,))
        with contextlib.suppress(sqlite3.OperationalError):
            _conn.execute("ALTER TABLE prize_claimed ADD COLUMN claimed REAL")
        _conn.execute("UPDATE prize_claimed SET claimed=? WHERE claimed IS NULL", (now,))
        _conn.commit()
    return _conn


def _posted_score(tid, pid):
    row = _db().execute(
        "SELECT score FROM tournament_board WHERE tournament_id=? AND principal=?",
        (tid, pid)).fetchone()
    return row[0] if row else None


def _upsert(tid, pid, name, score):
    _db().execute(
        "INSERT INTO tournament_board(tournament_id,principal,name,score,updated) "
        "VALUES(?,?,?,?,?) ON CONFLICT(tournament_id,principal) "
        "DO UPDATE SET name=excluded.name, score=excluded.score, updated=excluded.updated",
        (tid, pid, name, float(score), time.time()))
    _db().commit()


def _posted_rows(tid):
    """{principal: {"name","score"}} of posted results."""
    out = {}
    for pid, name, score in _db().execute(
            "SELECT principal,name,score FROM tournament_board "
            "WHERE tournament_id=?", (tid,)):
        out[pid] = {"name": name, "score": score}
    return out


def _better(new, old, low):
    """Is `new` better than `old` for this sort direction?"""
    if old is None:
        return True
    return new < old if low else new > old


def submit_race(pid, name, stats, tid=None):
    """Post an end-of-race result. `stats` is {stat_id: value}. Qualifies if the
    ranked stat is positive; posts when it beats the player's best. Returns an
    outcome dict including `qualified`."""
    if not pid:
        return {"qualified": False, "reason": "no pid"}
    if tid is None:
        tid = active_tid()
    tdef = tournament(tid)
    score = tdef.score_of(stats)
    if score is None or score <= 0:
        logger.info(f"leaderboard[tid={tid}] '{tdef.title}': pid={pid} DID NOT "
                    f"QUALIFY (stat 0x{tdef.score:02x}={score})")
        return {"qualified": False, "reason": "no qualifying result", "score": score}
    prev = _posted_score(tid, pid)
    improved = _better(score, prev, tdef.low)
    if improved:
        _upsert(tid, pid, name or f"Player{pid}", score)
    logger.info(f"leaderboard[tid={tid}] '{tdef.title}': pid={pid} name={name} "
                f"QUALIFIED score(0x{tdef.score:02x})={score} "
                f"{'POSTED (new best)' if improved else f'kept (best {prev})'}")
    return {"qualified": True, "score": score, "improved": improved}


# --- Prizes ------------------------------------------------------------------
def final_position(tid, pid):
    """1-based finishing position among posted entrants, or None if the player
    didn't post a qualifying result."""
    posted = _posted_rows(tid)
    if pid not in posted:
        return None
    low = tournament(tid).low
    order = sorted(posted.items(),
                   key=lambda kv: kv[1]["score"] if low else -kv[1]["score"])
    for pos, (p, _) in enumerate(order, start=1):
        if p == pid:
            return pos
    return None


def _prize_claimed(tid, pid):
    return _db().execute(
        "SELECT 1 FROM prize_claimed WHERE tournament_id=? AND principal=?",
        (tid, pid)).fetchone() is not None


def mark_prize_claimed(pid, tid):
    if not pid:
        return
    _db().execute("INSERT OR IGNORE INTO prize_claimed(tournament_id,principal,claimed) "
                  "VALUES(?,?,?)", (tid, pid, time.time()))
    _db().commit()


def _prize_for_position(tid, pos):
    """Exact-position (1st..3rd) prize tier, or None. Percentile tiers need the
    field size, so aren't auto-awarded."""
    for gt, gs, amount, kind in prizes_for(tid):
        if gt == PrizeGroupWire.ORDINAL and gs == pos:
            return amount, kind
    return None


def unclaimed_prize(pid, tid=None):
    """A collectable prize: player placed in the exact-position bracket
    (1st..3rd) and hasn't claimed. Skips the featured tournament (standings not
    settled). Returns {tournament_id, position, amount, kind} or None. `tid`
    checks one specific tournament."""
    if not pid:
        return None
    active = active_tid()
    if tid is not None:
        tids = [tid]
    else:
        tids = [r[0] for r in _db().execute(
            "SELECT DISTINCT tournament_id FROM tournament_board "
            "WHERE principal=? AND tournament_id!=? ORDER BY tournament_id",
            (pid, active))]
    for t in tids:
        if _prize_claimed(t, pid):
            continue
        pos = final_position(t, pid)
        if pos is None:
            continue
        prize = _prize_for_position(t, pos)
        if prize:
            amount, kind = prize
            return {"tournament_id": t, "position": pos, "amount": amount,
                    "kind": kind}
    return None


def board_rows(tid):
    """Ranked leaderboard rows, best first: [{"rank","principal","name",
    "score"}]. Only entrants who posted a score appear. `score` is cast to the
    tournament's type."""
    tdef = tournament(tid)
    rows = _posted_rows(tid)
    low = tdef.low
    ordered = sorted(rows.items(),
                     key=lambda kv: kv[1]["score"] if low else -kv[1]["score"])
    return [{"rank": rank, "principal": pid, "name": _display_name(pid, rec["name"]),
             "score": tdef.leaderboard_value(rec["score"])}
            for rank, (pid, rec) in enumerate(ordered, start=1)]


def _display_name(pid, stored):
    """PSN name when available: the posted name, else the login username, else
    a Player<pid> fallback."""
    if stored and not stored.startswith("Player"):
        return stored
    return accounts.username_for(pid) or stored or f"Player{pid}"


def participation(limit=10):
    """Players ranked by tournaments participated in (distinct posted instances)."""
    rows = _db().execute(
        "SELECT principal, COUNT(DISTINCT tournament_id) c FROM tournament_board "
        "GROUP BY principal ORDER BY c DESC, principal LIMIT ?", (limit,)).fetchall()
    return [{"principal": pid, "name": _display_name(pid, None), "count": c}
            for pid, c in rows]


# --- Dashboard view ----------------------------------------------------------
def _tour_info(win, now):
    td = featured(win)
    iid = instance_id(win)
    start, end = window_start(win), window_end(win)
    return {
        "window": win, "id": iid, "title": td.title, "rules": td.rules,
        "score_label": td.score_label, "sort": td.sort_text,
        "criteria": td.criteria_text(),
        "started": start.strftime("%m-%d %H:%M"),
        "ended": end.strftime("%m-%d %H:%M"),
        "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M"),
        "remaining_s": max(0, int((end - now).total_seconds())),
        "prizes": prize_rows(iid),
        "board": board_rows(iid),
    }


_HISTORY_LEN = 4


def state_snapshot():
    """Live dashboard state (JSON-able): active, upcoming, and recently-ended
    runs (newest first)."""
    now = datetime.now()  # noqa: DTZ005
    w = current_window(now)
    return {
        "now": now.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_s": TOURNAMENT_DURATION_SECONDS,
        "pool_size": len(_POOL),
        "active": _tour_info(w, now),
        "upcoming": _tour_info(w + 1, now),
        "history": [_tour_info(w - i, now) for i in range(1, _HISTORY_LEN + 1)],
        "participation": participation(),
        "pool": [{"idx": i, "title": t.title, "rules": t.rules,
                  "score_label": t.score_label, "sort": t.sort_text,
                  "criteria": t.criteria_text()}
                 for i, t in enumerate(_POOL)],
    }
