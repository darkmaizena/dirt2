"""
Minimal common structures for Dirt 2 NEX server
"""
import struct
import time
from datetime import datetime


class RMCError(Exception):
    """RMC protocol error"""
    def __init__(self, message, code=0x80000000):
        super().__init__(message)
        self.code = code


class Structure:
    """Base class for data structures"""
    def load(self, stream, version):
        raise NotImplementedError

    def save(self, stream, version):
        raise NotImplementedError


# NP identity from SonyNPTicket (SecureConnection.RegisterEx), keyed by pid.
_NP_IDENTITY_BY_PID = {}


def set_np_identity(pid, online_id=None, account_id=None, region=None):
    """Record NP identity for a pid. Only non-None fields overwrite."""
    if pid is None:
        return
    ident = _NP_IDENTITY_BY_PID.setdefault(pid, {})
    if online_id is not None:
        ident["online_id"] = online_id
    if account_id is not None:
        ident["account_id"] = account_id
    if region is not None:
        ident["region"] = region


def get_np_identity(pid):
    """Return {online_id, account_id, region} for a pid (empty dict if none)."""
    return _NP_IDENTITY_BY_PID.get(pid, {})


class ClientContext:
    """Handler `client`: id string + authenticated pid (from secure CONNECT
    check data). str() yields id; handlers read `.pid`. np_online_id /
    np_account_id / np_region hydrated from the pid-keyed NP identity store."""
    def __init__(self, client_id, pid=None):
        self.id = client_id
        self.pid = pid
        ident = get_np_identity(pid)
        self.np_online_id = ident.get("online_id")
        self.np_account_id = ident.get("account_id")
        self.np_region = ident.get("region")

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"ClientContext({self.id!r}, pid={self.pid})"


class StreamOut:
    """Output stream for encoding data"""
    def __init__(self):
        self.data = b""

    def u8(self, value):
        self.data += struct.pack("<B", value)

    def u16(self, value):
        self.data += struct.pack("<H", value)

    def u32(self, value):
        self.data += struct.pack("<I", value)

    def u64(self, value):
        self.data += struct.pack("<Q", value)

    def string(self, value):
        encoded = value.encode('utf-8')
        self.u16(len(encoded) + 1)
        self.data += encoded + b'\x00'

    def buffer(self, value):
        self.u32(len(value))
        self.data += value

    def bool(self, value):
        self.u8(1 if value else 0)

    def float(self, value):
        self.data += struct.pack("<f", value)

    def add(self, structure):
        """Add a structure to the stream"""
        structure.save(self, version=0)

    def add_list(self, items):
        """qVector<Structure>: u32 count + each element."""
        self.u32(len(items))
        for item in items:
            self.add(item)

    def add_map(self, pairs):
        """qMap<u32, Structure>: u32 count + each (u32 key, value)."""
        self.u32(len(pairs))
        for key, value in pairs:
            self.u32(key)
            self.add(value)

    def get(self):
        return self.data

    def size(self):
        return len(self.data)


class StreamIn:
    """Input stream for decoding data"""
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def u8(self):
        if self.pos + 1 > len(self.data):
            raise ValueError("Not enough data")
        value = struct.unpack_from("<B", self.data, self.pos)[0]
        self.pos += 1
        return value

    def u16(self):
        if self.pos + 2 > len(self.data):
            raise ValueError("Not enough data")
        value = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return value

    def u32(self):
        if self.pos + 4 > len(self.data):
            raise ValueError("Not enough data")
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def u64(self):
        if self.pos + 8 > len(self.data):
            raise ValueError("Not enough data")
        value = struct.unpack_from("<Q", self.data, self.pos)[0]
        self.pos += 8
        return value

    def string(self):
        length = self.u16()
        if length == 0:
            return ""
        if self.pos + length > len(self.data):
            raise ValueError("Not enough data")
        value = self.data[self.pos:self.pos + length - 1].decode('utf-8')
        self.pos += length
        return value

    def buffer(self):
        length = self.u32()
        if self.pos + length > len(self.data):
            raise ValueError("Not enough data")
        value = self.data[self.pos:self.pos + length]
        self.pos += length
        return value

    def bool(self):
        return self.u8() != 0

    def float(self):
        if self.pos + 4 > len(self.data):
            raise ValueError("Not enough data")
        value = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return value

    def extract(self, structure_class):
        """Extract a structure from the stream"""
        structure = structure_class()
        structure.load(self, version=0)
        return structure

    def remaining(self):
        return len(self.data) - self.pos

    def eof(self):
        return self.pos >= len(self.data)


class DateTime:
    """DateTime utilities"""
    @staticmethod
    def now():
        return DateTime(time.time())

    def __init__(self, timestamp=None):
        self.timestamp = timestamp or time.time()

    def __str__(self):
        # Quazal DateTime is naive local wall-clock
        return datetime.fromtimestamp(self.timestamp).isoformat()  # noqa: DTZ006
