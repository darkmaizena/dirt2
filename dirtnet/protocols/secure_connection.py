"""
Quazal SecureConnectionService (protocol 11) for Dirt 2 PS3.
Secure connection registration.
"""
import logging

from quazal.common import RMCError, Structure, set_np_identity
from quazal.rmc import ProtocolHandler

logger = logging.getLogger(__name__)

# ErrorCode.Core_NoError serialized retVal
CORE_NO_ERROR = 0x10001


class RegisterResult(Structure):
    """retVal, pidConnectionID, urlPublic (StationURL)."""
    def __init__(self, connection_id=0, url=""):
        self.connection_id = connection_id
        self.url = url

    def save(self, out, version):
        out.u32(CORE_NO_ERROR)
        out.u32(self.connection_id)
        out.string(self.url)

# SonyNPTicket TLV: every field is big-endian type(u16) len(u16) value(len).
# Sections (containers whose value is itself a run of fields) use types in
# 0x3000..0x30FF; leaf fields carry the actual identity. Field types:
#   0x0002 len 8  -> NP Account ID (u64)
#   0x0004 len 32 -> NP Online ID  (ASCII, null-padded) == Login username
#   0x0004 len 4  -> region/domain code (ASCII, null-padded)
#   0x0008 len 24 -> service / title id
_NP_SECTION_LO = 0x3000
_NP_SECTION_HI = 0x30FF


def _walk_np_tlv(buf, start, end, leaves, depth=0):
    """Walk big-endian type/len/value TLVs in buf[start:end], descending into
    section containers (0x30xx) and appending (type, len, value) leaf tuples."""
    pos = start
    while pos + 4 <= end and depth < 8:
        typ = int.from_bytes(buf[pos:pos + 2], "big")
        ln = int.from_bytes(buf[pos + 2:pos + 4], "big")
        pos += 4
        if ln > end - pos:
            break
        if _NP_SECTION_LO <= typ <= _NP_SECTION_HI:
            _walk_np_tlv(buf, pos, pos + ln, leaves, depth + 1)
        else:
            leaves.append((typ, ln, buf[pos:pos + ln]))
        pos += ln


def _find_np_ticket_body(buf):
    """Find the first 0x30xx section header whose declared length fits — the
    ticket body start, past the String("SonyNPTicket") + DataHolder length
    wrapper and the SceNpTicket version header."""
    n = len(buf)
    i = 0
    while i + 4 <= n:
        typ = int.from_bytes(buf[i:i + 2], "big")
        ln = int.from_bytes(buf[i + 2:i + 4], "big")
        if _NP_SECTION_LO <= typ <= _NP_SECTION_HI and 0 < ln <= n - (i + 4):
            return i
        i += 1
    return -1


def parse_np_ticket(raw):
    """Extract (np_online_id: str|None, np_account_id: int|None, region: str|None)
    from the RegisterEx customData tail (SonyNPTicket blob). Returns whatever
    fields were found, never raises."""
    online_id = account_id = region = None
    leaves = []
    start = _find_np_ticket_body(raw)
    if start >= 0:
        _walk_np_tlv(raw, start, len(raw), leaves)
    for typ, ln, val in leaves:
        if typ == 0x0002 and ln == 8 and account_id is None:
            account_id = int.from_bytes(val, "big")
        elif typ == 0x0004:
            text = val.split(b"\x00", 1)[0]
            try:
                text = text.decode("ascii")
            except UnicodeDecodeError:
                continue
            if not text.isprintable():
                continue
            if len(text) >= 3 and online_id is None:
                online_id = text
            elif ln == 4 and region is None:
                region = text
    return online_id, account_id, region


def _dump_remaining(input, tag):
    """Log the unread tail of a request body: length, ASCII runs, and hex."""
    raw = bytes(input.data[input.pos:])
    if not raw:
        logger.info(f"  [{tag}] no trailing custom data")
        return
    runs = []
    cur = b""
    for c in raw:
        if 32 <= c < 127:
            cur += bytes([c])
        else:
            if len(cur) >= 3:
                runs.append(cur.decode())
            cur = b""
    if len(cur) >= 3:
        runs.append(cur.decode())
    logger.info(f"  [{tag}] {len(raw)} trailing bytes; ascii runs={runs}")
    logger.info(f"  [{tag}] hex={raw.hex()}")


class SecureConnectionService(ProtocolHandler):
    """Protocol 11 - secure connection registration (secure server)."""

    PROTOCOL_ID = 11

    def __init__(self):
        super().__init__()
        self.next_connection_id = 1
        self.methods = {
            1: self.handle_register,
            4: self.handle_register_ex,
        }

    def _write_register_result(self, client, output, urls):
        connection_id = self.next_connection_id
        self.next_connection_id += 1

        # Echo the client's last URL, filling the standard Quazal StationURL
        # params (CID/PID/RVCID/stream).
        url = urls[-1] if urls else "prudp:/"
        pid = getattr(client, "pid", None) or connection_id
        if url != "prudp:/":
            params = dict(
                p.split("=", 1)
                for p in url.split(":/", 1)[1].split(";")
                if "=" in p
            )
            params.setdefault("sid", "15")
            params["CID"] = str(connection_id)
            params["PID"] = str(pid)
            params["RVCID"] = str(connection_id)
            params.setdefault("stream", "3")
            params["type"] = "3"
            params.setdefault("RVCS", "1")
            url = "prudp:/" + ";".join(f"{k}={v}" for k, v in params.items())

        output.add(RegisterResult(connection_id, url))
        logger.info(f"Registered secure connection {connection_id}: {url}")

    def handle_register(self, client, input, output):
        count = input.u32()
        urls = [input.string() for _ in range(count)]
        logger.info(f"Register({urls})")
        self._write_register_result(client, output, urls)

    def handle_register_ex(self, client, input, output):
        count = input.u32()
        urls = [input.string() for _ in range(count)]
        logger.info(f"RegisterEx({urls})")
        custom_data = bytes(input.data[input.pos:])
        _dump_remaining(input, "RegisterEx.customData")
        self._extract_np_identity(client, custom_data)
        self._write_register_result(client, output, urls)

    def _extract_np_identity(self, client, custom_data):
        """Parse the SonyNPTicket customData for the player's NP identity and
        store it (client attrs + pid-keyed store) for later RMC calls."""
        try:
            online_id, account_id, region = parse_np_ticket(custom_data)
            if online_id is None and account_id is None:
                logger.warning("RegisterEx: no NP identity found in customData")
                return
            # Persist by pid so rebuilt ClientContexts can restore it.
            client.np_online_id = online_id
            client.np_account_id = account_id
            client.np_region = region
            set_np_identity(getattr(client, "pid", None),
                            online_id=online_id, account_id=account_id,
                            region=region)
            logger.info(
                f"RegisterEx NP identity: onlineId={online_id!r} "
                f"accountId={account_id:#x} region={region!r}"
                if account_id is not None else
                f"RegisterEx NP identity: onlineId={online_id!r} "
                f"region={region!r}")
        except Exception as e:
            logger.warning(f"RegisterEx: NP identity parse failed: {e}")

    async def handle(self, client, method_id, input_stream, output_stream):
        if method_id not in self.methods:
            raise RMCError(f"Unknown SecureConnection method {method_id}",
                           0x80010001)
        self.methods[method_id](client, input_stream, output_stream)
