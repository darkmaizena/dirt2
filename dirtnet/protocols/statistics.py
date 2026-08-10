"""
Statistics Protocol (101) - Dirt 2 PS3.

Method IDs/signatures from DIRT_2_DEBUG.ELF DWARF (StatisticsProtocolDDL.cpp):

    1 submitStatistics(u8 category, qVector<AnyObjectHolder> stats)      -> void
    2 getPrincipalStatistics(u32 pid)                                    -> qVector<AnyObjectHolder>
    3 getPrincipalCarStatistics(u32 pid, u8 car)                         -> qVector<AnyObjectHolder>
    4 getSingleStatisticForManyPrincipals(u8 stat, qVector<u32> pids)    -> qMap<u32, AnyObjectHolder>
    5 getSingleStatisticForManyPrincipalsCar(u8 stat, qVector<u32> pids, u8 car) -> qMap<u32, AnyObjectHolder>

AnyObjectHolder<Data,String> (AnyData) wire format — TWO size u32s in both
directions (dump-proven, see AnyStat):

    className : String(u16 len incl NUL)
    u32 payloadSize                 (= 4 + statSize)
    u32 statSize                    (= 1 + sizeof(value))
    u8  statId
    typed value                     (UInt8=1, UInt16=2, UInt32=4, Float=4, String)

Concrete class per stat id from stat_types.py.
"""

import logging
import struct

from game import stat_store, stat_types
from quazal.common import RMCError, StreamOut, Structure
from quazal.rmc import ProtocolHandler

logger = logging.getLogger(__name__)


def _append_value(stream, class_name, value):
    if class_name == "UInt8Statistic":
        stream.u8(int(value) & 0xFF)
    elif class_name == "UInt16Statistic":
        stream.u16(int(value) & 0xFFFF)
    elif class_name == "UInt24Statistic":
        stream.data += (int(value) & 0xFFFFFF).to_bytes(3, "little")
    elif class_name == "UInt32Statistic":
        stream.u32(int(value) & 0xFFFFFFFF)
    elif class_name == "FloatStatistic":
        stream.float(float(value))
    elif class_name == "StringStatistic":
        stream.string(str(value))
    else:  # unknown -> u32
        stream.u32(int(value) & 0xFFFFFFFF)


class AnyStat(Structure):
    """AnyObjectHolder<Data,String>: className(String) + u32 payloadSize + u32
    innerSize + statId + value. TWO u32s: payloadSize = 4 + innerSize; innerSize
    = statId + value. class_name None -> stat_types.class_for(stat_id)."""
    def __init__(self, stat_id, value, class_name=None):
        self.stat_id = stat_id
        self.value = value
        self.class_name = class_name

    def save(self, out, version):
        class_name = self.class_name or stat_types.class_for(self.stat_id)
        body = StreamOut()  # statId + value
        body.u8(self.stat_id & 0xFF)
        _append_value(body, class_name, self.value)
        stat_body = body.data
        out.string(class_name)
        out.u32(4 + len(stat_body))  # payloadSize = 4 + innerSize
        out.u32(len(stat_body))      # innerSize = statId + value
        out.data += stat_body


class StatisticsService(ProtocolHandler):
    PROTOCOL_ID = 101

    # Method 4/5 (friend/leaderboard read) response. False -> empty qMap (stable);
    # True -> populated map (count-first, per-id type). True triggers an in-game
    # "version mismatch"/disconnect on device; root cause unpinned. An empty
    # map (count=0) creates zero holders, so it is not the tournament crash source;
    # any populate must send a non-empty className per entry.
    POPULATE_STATS = False

    # True -> RMC error for method 4/5 (breaks connect: client requires success
    # here); False -> answer normally (empty or populated per POPULATE_STATS).
    ERROR_FRIEND_STAT_READ = False

    def __init__(self):
        super().__init__()
        self.methods = {
            1: self.submit_statistics,
            2: self.get_principal_statistics,
            3: self.get_principal_car_statistics,
            4: self.get_single_statistic_for_many_principals,
            5: self.get_single_statistic_for_many_principals_car,
        }

    # -- writes (end-race bulk upload is proto 102 RaceReportService) --
    def submit_statistics(self, client, input, output):
        # Proto 101 method 1 body = qVector<String> of friend gamertags
        # (name->pid), not the stat blob (proto 102). Ack void.
        try:
            count = input.u32()
            names = [input.string() for _ in range(count)]
            logger.info(f"submitStatistics(101/m1) = friend list ({count}): {names}")
        except Exception as e:
            logger.warning(f"submitStatistics(101/m1) parse failed: {e}")

    # -- reads --
    def _write_stats_vector(self, output, pid, car=None):
        """qVector<AnyObjectHolder>: u32 count + AnyData[]. From the store."""
        rows = stat_store.get_all(pid, car=car) if pid else []
        output.add_list([AnyStat(stat_id, value, class_name)
                         for stat_id, class_name, value in rows])
        if rows:
            logger.info(f"  -> {len(rows)} stored stats for pid={pid} car={car}")

    def get_principal_statistics(self, client, input, output):
        pid = input.u32()
        logger.info(f"getPrincipalStatistics(pid={pid})")
        self._write_stats_vector(output, pid, car=None)

    def get_principal_car_statistics(self, client, input, output):
        pid = input.u32()
        car = input.u8()
        logger.info(f"getPrincipalCarStatistics(pid={pid}, car={car})")
        self._write_stats_vector(output, pid, car=car)

    def _parse_stat_request(self, input, has_car):
        """Body (method 5) = u8 statId + u32 principal[...] (e.g. `0b 0a000000` =
        stat 0x0b for principal 10); no count prefix. A lone trailing byte (odd
        remainder) is the car id."""
        raw = input.data[input.pos :]
        stat_type = raw[0] if raw else 0
        body = raw[1:]
        car = None
        if has_car and (len(body) % 4) == 1:
            car = body[-1]
            body = body[:-1]
        n = len(body) // 4
        pids = [int.from_bytes(body[i * 4 : i * 4 + 4], "little") for i in range(n)]
        logger.info(f"  raw={raw.hex()} stat=0x{stat_type:02x} pids={pids} car={car}")
        return stat_type, pids, car

    def _write_stat_map(self, output, stat_type, pids, car=None):
        """qMap<u32, AnyObjectHolder>: u32 count + count*(u32 principal +
        AnyData). Value uses the concrete type for this stat id, stored value
        if present else 0."""
        if not self.POPULATE_STATS:
            output.add_map([])  # empty qMap
            return
        # read_class_for = client resolveRendezVousDataType table, not the submit
        # table. Wrong class (UInt32 for String-typed stat 0x00) reads garbage.
        class_name = stat_types.read_class_for(stat_type)
        default = "" if class_name == "StringStatistic" else 0
        pairs = []
        for pid in pids:
            stored = stat_store.get(
                pid, stat_type, car=car if car is not None else stat_store.CAR_GLOBAL
            )
            value = stored[1] if stored else default
            pairs.append((pid, AnyStat(stat_type, value, class_name)))
        output.add_map(pairs)

    def get_single_statistic_for_many_principals(self, client, input, output):
        if self.ERROR_FRIEND_STAT_READ:
            logger.info("getSingleStatisticForManyPrincipals -> RMC error (diag)")
            raise RMCError("no stats", 0x80010001)
        logger.info("getSingleStatisticForManyPrincipals")
        stat_type, pids, _ = self._parse_stat_request(input, has_car=False)
        self._write_stat_map(output, stat_type, pids)

    def get_single_statistic_for_many_principals_car(self, client, input, output):
        if self.ERROR_FRIEND_STAT_READ:
            _ = self._parse_stat_request(input, has_car=True)
            logger.info("getSingleStatisticForManyPrincipalsCar -> RMC error (diag)")
            raise RMCError("no stats", 0x80010001)
        stat_type, pids, car = self._parse_stat_request(input, has_car=True)
        if not self.POPULATE_STATS:
            logger.info("getSingleStatisticForManyPrincipalsCar -> empty (connect probe)")
            output.add_map([])
            return
        logger.info(
            f"getSingleStatisticForManyPrincipalsCar -> populated "
            f"stat=0x{stat_type:02x} pids={pids} car={car}"
        )
        self._write_stat_map(output, stat_type, pids, car=car)

    async def handle(self, client, method_id, input_stream, output_stream):
        if method_id not in self.methods:
            logger.warning(f"Unknown statistics method {method_id}")
            raise RMCError(f"Unknown method {method_id}", 0x80010001)
        self.methods[method_id](client, input_stream, output_stream)


def parse_submit_statistics(input):
    """Parse submitStatistics body: u8 category + qVector<AnyObjectHolder>.
    Returns list of (stat_id, class_name, value). Shared by proto 101 method 1
    and proto 102 RaceReportService."""
    data = input.data
    pos = input.pos
    category = data[pos]
    pos += 1
    count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    out = []
    for _ in range(count):
        clen = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        class_name = data[pos : pos + clen - 1].decode("latin1")
        pos += clen
        # AnyData framing = className + u32 payloadSize + u32 innerSize +
        # [statId(u8) + value]. TWO u32, per RaceReport capture
        # (1000"UInt32Statistic"00 09000000 05000000 46 66090000).
        payload_size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        end = pos + payload_size  # payloadSize spans innerSize + inner
        pos += 4  # innerSize u32
        stat_id = data[pos]
        pos += 1
        if class_name == "UInt8Statistic":
            value = data[pos]
        elif class_name == "UInt16Statistic":
            value = struct.unpack_from("<H", data, pos)[0]
        elif class_name == "UInt24Statistic":
            value = int.from_bytes(data[pos : pos + 3], "little")
        elif class_name == "UInt32Statistic":
            value = struct.unpack_from("<I", data, pos)[0]
        elif class_name == "FloatStatistic":
            value = struct.unpack_from("<f", data, pos)[0]
        elif class_name == "StringStatistic":
            sl = struct.unpack_from("<H", data, pos)[0]
            value = data[pos + 2 : pos + 2 + sl - 1].decode("latin1")
        else:
            value = 0
        out.append((stat_id, class_name, value))
        pos = end  # declared element end
    input.pos = pos
    return out, category
