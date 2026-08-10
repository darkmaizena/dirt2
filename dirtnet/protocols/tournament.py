"""Tournament protocol (103): encodes tournament/leaderboard data to the wire and
dispatches its methods. Domain data lives in game/tournament.py."""

import logging
import struct
from datetime import datetime

from game import tournament as game
from game.enums import PrizeGroupWire, RewardKind
from quazal.common import RMCError, Structure
from quazal.rmc import ProtocolHandler

logger = logging.getLogger(__name__)

# Leaderboard ranked-value display type (Float, rendered as a decimal).
DISPLAY_STAT_ID = 0x4A
DISPLAY_CLASS = "FloatStatistic"


def quazal_datetime(dt):
    """Quazal DateTime u64: sec|min<<6|hour<<12|day<<17|month<<22|year<<26."""
    return (
        dt.second
        | (dt.minute << 6)
        | (dt.hour << 12)
        | (dt.day << 17)
        | (dt.month << 22)
        | (dt.year << 26)
    )


def write_any_statistic(stream, inner, class_name="UInt32Statistic"):
    """AnyData response wire: className(String) + u32 payloadSize + u32 innerSize
    + object bytes (statId + value).
    payloadSize = 4 + innerSize; innerSize = statId + value."""
    stream.string(class_name)
    stream.u32(4 + len(inner))  # payloadSize = 4 + innerSize
    stream.u32(len(inner))  # innerSize = statId + value
    stream.data += inner


def write_any_uint(stream, value, key=0):
    """UInt32Statistic AnyData: inner = statId(1) + u32 value(4) -> size 5."""
    write_any_statistic(stream, struct.pack("<BI", key, value), "UInt32Statistic")


def write_any_stat(stream, stat_id, value, class_name="UInt32Statistic"):
    """Type-aware AnyData: inner = statId(1) + value, encoded per concrete type.
    Leaderboard ranked values: Float tournament sends FloatStatistic, int sends
    UInt*Statistic."""
    if class_name == "FloatStatistic":
        inner = struct.pack("<Bf", stat_id, float(value))
    elif class_name == "UInt8Statistic":
        inner = struct.pack("<BB", stat_id, int(value) & 0xFF)
    elif class_name == "UInt16Statistic":
        inner = struct.pack("<BH", stat_id, int(value) & 0xFFFF)
    else:  # UInt32Statistic (default)
        inner = struct.pack("<BI", stat_id, int(value) & 0xFFFFFFFF)
    write_any_statistic(stream, inner, class_name)


class PrizeGroup(Structure):
    # group_type = PrizeGroupWire: ORDINAL=3 -> "1st", PERCENT=2 -> "TOP N%".
    # group_size = position/percent. data_id = RewardKind (MONEY=1, XP=2).
    def __init__(
        self, group_type=PrizeGroupWire.ORDINAL, group_size=0, reward=0, data_id=RewardKind.MONEY
    ):
        self.group_type = int(group_type)
        self.group_size = group_size
        self.reward = reward  # cash/xp amount
        self.data_id = int(data_id)

    def save(self, out, version):
        out.u8(self.group_type)
        out.u32(self.group_size)
        write_any_uint(out, self.reward, key=self.data_id)


class TournamentDetails(Structure):
    # TWO strings + trailing u32 — see module docstring.
    def __init__(self):
        self.tournament_id = 0
        self.start_time = datetime.now()  # noqa: DTZ005 - Quazal DateTime = local wall-clock
        self.end_time = datetime.now()  # noqa: DTZ005
        self.title = ""
        self.subtitle = ""
        self.rules = ""
        self.prizes = []

    def save(self, out, version):
        out.u32(self.tournament_id)
        out.u64(quazal_datetime(self.start_time))
        out.u64(quazal_datetime(self.end_time))
        out.string(self.title)
        out.string(self.subtitle)
        out.add_list(self.prizes)
        out.u32(0)  # trailing u32


class LeaderboardEntry(Structure):
    def __init__(self, principal=0, rank=0, value=0, stat_id=0, class_name="UInt32Statistic"):
        self.principal = principal
        self.rank = rank
        self.value = value
        self.stat_id = stat_id  # which statistic this ranked value is
        self.class_name = class_name  # its concrete AnyData type

    def save(self, out, version):
        out.u32(self.principal)
        out.u32(self.rank)
        write_any_stat(out, self.stat_id, self.value, self.class_name)


class XuidEntry(Structure):
    """XuidDetails: u32 principal, u64 xuid, String gamertag."""

    def __init__(self, principal=0, xuid=0, name=""):
        self.principal = principal
        self.xuid = xuid
        self.name = name

    def save(self, out, version):
        out.u32(self.principal)
        out.u64(self.xuid)
        out.string(self.name)


class PsnEntry(Structure):
    """PsnDetails: u32 principal, String psnName."""

    def __init__(self, principal=0, name=""):
        self.principal = principal
        self.name = name

    def save(self, out, version):
        out.u32(self.principal)
        out.string(self.name)


class UnclaimedPrize(Structure):
    """u32 tournamentId, u32 finalPosition, PrizeGroup reward."""

    def __init__(self, tournament_id=0, position=0, reward=None):
        self.tournament_id = tournament_id
        self.position = position
        self.reward = reward

    def save(self, out, version):
        out.u32(self.tournament_id)
        out.u32(self.position)
        out.add(self.reward)


class ActiveTournamentResponse(Structure):
    """TournamentDetails + u32 secondsRemaining."""

    def __init__(self, details=None, seconds=0):
        self.details = details
        self.seconds = seconds

    def save(self, out, version):
        out.add(self.details)
        out.u32(self.seconds)


class TournamentService(ProtocolHandler):
    """Protocol 103. Reads tournament/leaderboard data from game.tournament
    and encodes it to the wire."""

    PROTOCOL_ID = 103

    def __init__(self):
        super().__init__()
        self.methods = {
            1: self.get_previous_tournament,
            2: self.get_active_tournament,
            3: self.get_upcoming_tournament,
            4: self.get_top_of_leaderboard,
            5: self.get_top_of_leaderboard_with_gamertags,
            6: self.get_top_of_leaderboard_with_psn_names,
            7: self.get_my_entry,
            8: self.get_unclaimed_prize,
            9: self.mark_prize_as_claimed,
        }

    # -- TournamentDetails (wire) from a domain window ----------------------
    def _make_details(self, tdef, tid, start, end):
        t = TournamentDetails()
        t.tournament_id = tid
        t.start_time = start
        t.end_time = end
        t.title = tdef.title
        t.subtitle = tdef.rules
        t.rules = tdef.rules
        t.prizes = [
            PrizeGroup(group_type=gt, group_size=gs, reward=amount, data_id=kind)
            for gt, gs, amount, kind in game.prizes_for(tid)
        ]
        return t

    def _make_window(self, window):
        return self._make_details(
            game.featured(window), game.instance_id(window),
            game.window_start(window), game.window_end(window))

    @property
    def active(self):
        return self._make_window(game.current_window())

    def get_previous_tournament(self, client, input, output):
        t = self._make_window(game.current_window() - 1)
        logger.info(f"getPreviousTournament -> id={t.tournament_id} '{t.title}'")
        output.add(t)

    def get_active_tournament(self, client, input, output):
        t = self._make_window(game.current_window())
        secs = game.seconds_until_change()
        logger.info(f"getActiveTournament -> id={t.tournament_id} '{t.title}' ({secs}s left)")
        output.add(ActiveTournamentResponse(t, secs))

    def get_upcoming_tournament(self, client, input, output):
        t = self._make_window(game.current_window() + 1)
        logger.info(f"getUpcomingTournament -> id={t.tournament_id} '{t.title}'")
        output.add(t)

    @staticmethod
    def _req_tid_count(input, default_count=64):
        tid = input.u32()
        count = input.u32() if input.remaining() >= 4 else default_count
        return tid, count

    @staticmethod
    def _entry(row):
        score = row["score"] if row["score"] is not None else 0
        return LeaderboardEntry(
            principal=row["principal"],
            rank=row["rank"],
            value=float(score),
            stat_id=DISPLAY_STAT_ID,
            class_name=DISPLAY_CLASS,
        )

    def _write_leaderboard(self, rows, output):
        output.add_list([self._entry(r) for r in rows])

    def _row_name(self, row):
        return row["name"] or f"Player{row['principal']}"

    def _local_xuid(self, client, principal):
        account_id = getattr(client, "np_account_id", None)
        if account_id is not None and principal == getattr(client, "pid", None):
            return account_id
        return principal

    def get_top_of_leaderboard(self, client, input, output):
        tid, count = self._req_tid_count(input)
        logger.info(f"getTopOfLeaderboard(tid={tid}, count={count})")
        self._write_leaderboard(game.board_rows(tid)[:count], output)

    def get_top_of_leaderboard_with_gamertags(self, client, input, output):
        tid, count = self._req_tid_count(input)
        logger.info(f"getTopOfLeaderboardWithGamertags(tid={tid}, count={count})")
        rows = game.board_rows(tid)[:count]
        self._write_leaderboard(rows, output)
        output.add_list(
            [
                XuidEntry(
                    r["principal"], self._local_xuid(client, r["principal"]), self._row_name(r)
                )
                for r in rows
            ]
        )

    def get_top_of_leaderboard_with_psn_names(self, client, input, output):
        tid, count = self._req_tid_count(input)
        logger.info(f"getTopOfLeaderboardWithPsnNames(tid={tid}, count={count})")
        rows = game.board_rows(tid)[:count]
        self._write_leaderboard(rows, output)
        output.add_list([PsnEntry(r["principal"], self._row_name(r)) for r in rows])

    def get_my_entry(self, client, input, output):
        tournament_id = input.u32()
        pid = getattr(client, "pid", None) or 2
        row = next((r for r in game.board_rows(tournament_id) if r["principal"] == pid), None)
        if row is None:
            # Not posted: FE "no entry" needs RMC success + empty entry (callback
            # tests principal at entry+4 == 0); an RMC error hits generic-failure.
            logger.info(f"getMyEntry({tournament_id}) -> empty entry (not posted) pid={pid}")
            output.add(
                LeaderboardEntry(
                    principal=0, rank=0, value=0, stat_id=0, class_name="UInt32Statistic"
                )
            )
            return
        entry = self._entry(row)
        logger.info(
            f"getMyEntry({tournament_id}) -> principal={pid} rank={entry.rank} score={entry.value}"
        )
        output.add(entry)

    # -- prizes ------------------------------------------------------------
    # UnclaimedPrize DDL: u32 tournamentId, u32 finalPosition, PrizeGroup reward.
    # Delivered when the player finished an ended tournament inside the prize
    # bracket (position <= len(game.PRIZES)) and hasn't claimed it.
    def get_unclaimed_prize(self, client, input, output):
        pid = getattr(client, "pid", None)
        prize = game.unclaimed_prize(pid)
        if not prize:
            logger.info(f"getUnclaimedPrize -> none for pid={pid}")
            raise RMCError("no unclaimed prize", 0x80010001)
        logger.info(
            f"getUnclaimedPrize -> tid={prize['tournament_id']} "
            f"pos={prize['position']} amount={prize['amount']}"
        )
        output.add(
            UnclaimedPrize(
                prize["tournament_id"],
                prize["position"],
                PrizeGroup(
                    group_type=PrizeGroupWire.ORDINAL,
                    group_size=prize["position"],
                    reward=prize["amount"],
                    data_id=prize["kind"],
                ),
            )
        )

    def mark_prize_as_claimed(self, client, input, output):
        tournament_id = input.u32()
        pid = getattr(client, "pid", None)
        game.mark_prize_claimed(pid, tournament_id)
        logger.info(f"markPrizeAsClaimed({tournament_id}) pid={pid}")

    async def handle(self, client, method_id, input_stream, output_stream):
        if method_id not in self.methods:
            logger.warning(f"Unknown tournament method {method_id}")
            raise RMCError(f"Unknown method {method_id}", 0x80010001)
        self.methods[method_id](client, input_stream, output_stream)
