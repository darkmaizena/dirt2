"""
RaceReport protocol (102) for DiRT 2 PS3.

Methods:
  1 end-of-race report — u8 category + qVector<AnyObjectHolder> (~108 stats),
    a fragmented ~3 KB message. Persisted to stat_store (proto 101 read path
    echoes real values) and fed to the tournament leaderboard
    (game.tournament.submit_race).

Each upload is also dumped as JSON under logs/race_reports/ (one file per race)
to diff per-race vs cumulative stats.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from game import stat_store, stat_types
from game.tournament import submit_race
from quazal.rmc import ProtocolHandler

from .statistics import parse_submit_statistics

logger = logging.getLogger(__name__)

_REPORT_DIR = Path(__file__).resolve().parents[1] / "logs" / "race_reports"

# Stats logged per lap to spot per-race vs cumulative behaviour.
_SUMMARY_IDS = (0x01, 0x02, 0x03, 0x04, 0x06, 0x07, 0x09, 0x0a, 0x0b)


class RaceReportService(ProtocolHandler):
    """Protocol 102 - end-of-race bulk stats upload."""

    PROTOCOL_ID = 102

    def __init__(self):
        super().__init__()
        self.methods = {
            1: self.end_of_race_report,
        }

    def end_of_race_report(self, client, input, output):
        """Method 1: parse the ~108-stat profile, persist it, dump it as JSON,
        and post the tournament result. Void response."""
        n = input.remaining()
        try:
            stats, category = parse_submit_statistics(input)
            pid = getattr(client, "pid", None) or 0
            stat_store.put_many(pid, stats)
            self._dump_json(pid, category, stats)
            name = getattr(client, "np_online_id", None)
            stat_bag = {sid: v for (sid, _cls, v) in stats}
            r = submit_race(pid, name, stat_bag)
            if r.get("qualified"):
                logger.info(f"  -> QUALIFIED: score={r['score']} "
                            f"{'(new best)' if r.get('improved') else '(kept best)'}")
            else:
                logger.info(f"  -> DID NOT QUALIFY: {r.get('reason')}")
        except Exception as e:
            logger.warning(f"RaceReport(102) parse/store failed ({n} bytes): {e}")

    def _dump_json(self, pid, category, stats):
        """Write this race's stats to a sequential JSON file and log a one-line
        summary of the key metrics."""
        entries = [{"id": f"0x{sid:02x}",
                    "name": stat_types.STAT_NAME.get(sid, "?"),
                    "type": cls, "value": val}
                   for sid, cls, val in sorted(stats, key=lambda s: s[0])]
        bag = {sid: val for sid, _cls, val in stats}
        report = {
            "race": None,  # sequential index, set below
            "utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",  # noqa: DTZ003
            "pid": pid, "category": category, "count": len(stats),
            "stats": entries,
        }
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        idx = len(list(_REPORT_DIR.glob("race_*.json"))) + 1
        report["race"] = idx
        path = _REPORT_DIR / f"race_{idx:03d}_pid{pid}.json"
        path.write_text(json.dumps(report, indent=2))
        summary = ", ".join(
            f"{stat_types.STAT_NAME.get(sid, hex(sid))}={bag[sid]}"
            for sid in _SUMMARY_IDS if sid in bag)
        logger.info(f"RaceReport(102) race #{idx}: {len(stats)} stats pid={pid} "
                    f"cat={category} -> {path.name}")
        logger.info(f"  key stats: {summary}")

    async def handle(self, client, method_id, input_stream, output_stream):
        handler = self.methods.get(method_id)
        if handler is None:
            logger.info(f"RaceReport method {method_id} "
                        f"({input_stream.remaining()} bytes) -> ack")
            return
        handler(client, input_stream, output_stream)
