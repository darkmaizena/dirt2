"""
PRUDP (Quazal RendezVous flavor) protocol. Port of QNetZ QPacket.cs /
QPacketHandlerPRUDP.cs.

Wire format (old Quazal, 1-byte type/flags):
    u8  source vport   (type << 4 | port)
    u8  dest vport
    u8  type_flags     (type = low 3 bits, flags = high 5 bits, i.e. flags << 3)
    u8  session id
    u32 signature      (peer connection id; 0 during SYN)
    u16 sequence id
    [u32 connection signature]   if SYN or CONNECT
    [u8  part number]            if DATA
    [u16 payload size]           if FLAG_HAS_SIZE
    payload
    u8  checksum       (word-sum + access key base)

Non-SYN payloads carry a 1-byte compression prefix (0 = raw, N = zlib);
on RVSecure streams (vport type 3) also RC4-encrypted with "CD&ML".
"""
import logging
import struct
import zlib

logger = logging.getLogger(__name__)

# Dirt 2 PS3 access key ("tFkQh5ds"), checksum base = sum of bytes & 0xFF
ACCESS_KEY = b"tFkQh5ds"
ACCESS_KEY_SUM = sum(ACCESS_KEY) & 0xFF  # 0xEA

RC4_KEY_DATA = b"CD&ML"  # Quazal default RC4 key

MAX_FRAGMENT_SIZE = 963  # QNetZ Constants.PacketFragmentMaxSize


def rc4(key, data):
    """Plain RC4 (same for encrypt/decrypt)."""
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + key[i % len(key)] + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
    out = bytearray()
    i = j = 0
    for b in data:
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out.append(b ^ s[(s[i] + s[j]) & 0xFF])
    return bytes(out)


def calc_checksum(data, base=None):
    """QNetZ QPacket.MakeChecksum: sum as little-endian u32 words, fold to a
    byte, add up to 2 leftover bytes and (base + optional 3rd leftover byte)."""
    if base is None:
        # access key checksum base for vport type 3
        base = ACCESS_KEY_SUM if (data[0] >> 4) == 3 else 0

    words = 0
    for i in range(len(data) // 4):
        words = (words + struct.unpack_from("<I", data, i * 4)[0]) & 0xFFFFFFFF

    leftover = len(data) & 3
    pos = len(data) - leftover
    tmp2 = tmp3 = 0
    processed = 0
    if leftover >= 2:
        processed = 2
        tmp2 = data[pos]
        tmp3 = data[pos + 1]
        pos += 2

    tmp4 = base if processed >= leftover else base + data[pos]

    return ((words >> 24) + (words >> 16) + (words >> 8) + words
            + tmp2 + tmp3 + tmp4) & 0xFF


class PRUDPPacket:
    """One Quazal PRUDP packet (QNetZ QPacket port)."""

    # Packet types (low 3 bits)
    TYPE_SYN = 0
    TYPE_CONNECT = 1
    TYPE_DATA = 2
    TYPE_DISCONNECT = 3
    TYPE_PING = 4
    TYPE_NATPING = 5

    # Flags (after >> 3)
    FLAG_ACK = 0x01
    FLAG_RELIABLE = 0x02
    FLAG_NEED_ACK = 0x04
    FLAG_HAS_SIZE = 0x08
    FLAG_FLOODED = 0x10

    # VPort stream types (high nibble of vport byte)
    STREAM_DO = 1
    STREAM_RV_AUTH = 2
    STREAM_RV_SECURE = 3
    STREAM_NAT = 5

    def __init__(self):
        self.source_vport = 0        # raw byte: type << 4 | port
        self.dest_vport = 0
        self.type = 0
        self.flags = 0
        self.session_id = 0
        self.signature = 0
        self.sequence_id = 0
        self.connection_signature = 0
        self.part_number = 0
        self.payload = b""           # decrypted + decompressed
        self.uses_compression = False
        self.checksum = 0

    @property
    def source_stream(self):
        return self.source_vport >> 4

    def has_flag(self, flag):
        return bool(self.flags & flag)

    @staticmethod
    def parse(data):
        # min packet = 2 vports + type/flags + session + u32 sig + u16 seq
        # + checksum = 11 bytes
        if len(data) < 11:
            raise ValueError(f"Packet too small: {len(data)} bytes")

        # Checksum covers everything except the final byte
        expected = calc_checksum(data[:-1])
        if data[-1] != expected:
            raise ValueError(
                f"Bad checksum: got {data[-1]:02x}, expected {expected:02x}")

        p = PRUDPPacket()
        offset = 0
        p.source_vport = data[offset]
        offset += 1
        p.dest_vport = data[offset]
        offset += 1

        type_flags = data[offset]
        offset += 1
        p.type = type_flags & 0x7
        p.flags = type_flags >> 3

        p.session_id = data[offset]
        offset += 1
        p.signature = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        p.sequence_id = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        if p.type in (PRUDPPacket.TYPE_SYN, PRUDPPacket.TYPE_CONNECT):
            p.connection_signature = struct.unpack_from("<I", data, offset)[0]
            offset += 4

        if p.type == PRUDPPacket.TYPE_DATA:
            p.part_number = data[offset]
            offset += 1

        if p.has_flag(PRUDPPacket.FLAG_HAS_SIZE):
            size = struct.unpack_from("<H", data, offset)[0]
            offset += 2
        else:
            size = len(data) - offset - 1  # rest minus checksum

        payload = data[offset:offset + size]
        p.checksum = data[-1]

        # decrypt + decompress non-SYN payloads
        if payload and p.type != PRUDPPacket.TYPE_SYN \
                and p.source_stream != PRUDPPacket.STREAM_NAT:
            if p.source_stream == PRUDPPacket.STREAM_RV_SECURE:
                payload = rc4(RC4_KEY_DATA, payload)
            p.uses_compression = payload[0] != 0
            body = payload[1:]
            payload = zlib.decompress(body) if p.uses_compression else body

        p.payload = payload
        return p

    def encode(self):
        data = bytearray()
        data.append(self.source_vport)
        data.append(self.dest_vport)
        data.append((self.type & 0x7) | ((self.flags & 0x1F) << 3))
        data.append(self.session_id)
        data.extend(struct.pack("<I", self.signature))
        data.extend(struct.pack("<H", self.sequence_id))

        if self.type in (PRUDPPacket.TYPE_SYN, PRUDPPacket.TYPE_CONNECT):
            data.extend(struct.pack("<I", self.connection_signature))

        if self.type == PRUDPPacket.TYPE_DATA:
            data.append(self.part_number)

        payload = self._processed_payload()

        if self.has_flag(PRUDPPacket.FLAG_HAS_SIZE):
            data.extend(struct.pack("<H", len(payload)))

        data.extend(payload)

        self.checksum = calc_checksum(bytes(data))
        data.append(self.checksum)
        return bytes(data)

    def _processed_payload(self):
        """Compression prefix + RC4, mirroring QPacket.getProcessedPayload."""
        payload = self.payload
        if not payload or self.type == PRUDPPacket.TYPE_SYN \
                or self.source_stream == PRUDPPacket.STREAM_NAT:
            return payload

        if self.uses_compression:
            compressed = zlib.compress(payload)
            count = len(payload) // len(compressed)
            if len(payload) % len(compressed):
                count += 1
            payload = bytes([count]) + compressed
        else:
            payload = b"\x00" + payload

        if self.source_stream == PRUDPPacket.STREAM_RV_SECURE:
            payload = rc4(RC4_KEY_DATA, payload)
        return payload

    def __str__(self):
        names = {0: "SYN", 1: "CONNECT", 2: "DATA", 3: "DISCONNECT",
                 4: "PING", 5: "NATPING"}
        flag_names = []
        for bit, name in ((0x01, "ACK"), (0x02, "RELIABLE"), (0x04, "NEED_ACK"),
                          (0x08, "HAS_SIZE"), (0x10, "FLOODED")):
            if self.flags & bit:
                flag_names.append(name)
        return (f"PRUDP({names.get(self.type, self.type)}"
                f" [{'|'.join(flag_names)}]"
                f" src={self.source_vport:02x} dst={self.dest_vport:02x}"
                f" session={self.session_id:02x} sig={self.signature:08x}"
                f" seq={self.sequence_id}"
                f" connsig={self.connection_signature:08x}"
                f" payload={len(self.payload)}b)")


class PRUDPSession:
    """Per-client connection state (QNetZ QClient + handler logic).

    handle_packet() returns packets to send back. RMC payloads from DATA
    packets go to `data_callback(payload)`; any response bytes are sent back
    as reliable DATA packets.
    """

    _next_client_id = 0x12345678  # QNetZ ClientIdCounter

    def __init__(self, addr, data_callback=None):
        self.addr = addr
        self.data_callback = data_callback

        PRUDPSession._next_client_id += 1
        self.id_recv = PRUDPSession._next_client_id  # our signature for client
        self.id_send = 0        # client's connection signature (from CONNECT)
        self.session_id = 0
        self.seq_out = 1        # our DATA sequence counter
        self.seq_in_expected = 1
        self.connected = False
        self.pid = None         # authenticated principal id (from secure CONNECT)
        self._fragments = []    # reassembly buffer for fragmented DATA
        self._reorder = {}      # out-of-order DATA held (seq -> packet) until the gap fills
        self._recv_synced = False  # latch seq_in_expected to the first DATA seq seen

    async def handle_packet(self, packet):
        replies = []
        t = packet.type

        if t == PRUDPPacket.TYPE_SYN:
            replies.append(self._handle_syn(packet))
        elif t == PRUDPPacket.TYPE_CONNECT:
            if not packet.has_flag(PRUDPPacket.FLAG_ACK):
                replies.append(self._handle_connect(packet))
        elif t == PRUDPPacket.TYPE_DATA:
            replies.extend(await self._handle_data(packet))
        elif t == PRUDPPacket.TYPE_DISCONNECT:
            replies.append(self._handle_disconnect(packet))
        elif t == PRUDPPacket.TYPE_PING:
            replies.append(self._make_ack(packet))
        else:
            logger.warning(f"Unhandled PRUDP type {t}")

        return [r for r in replies if r is not None]

    # -- handshake ---------------------------------------------------------

    def _make_ack(self, packet):
        """QNetZ MakeACK: echo the packet, set ACK|HAS_SIZE, swap vports."""
        ack = PRUDPPacket()
        ack.source_vport = packet.dest_vport
        ack.dest_vport = packet.source_vport
        ack.type = packet.type
        ack.flags = PRUDPPacket.FLAG_ACK | PRUDPPacket.FLAG_HAS_SIZE
        ack.session_id = packet.session_id
        ack.signature = self.id_send
        ack.sequence_id = packet.sequence_id       # echo, do not increment
        ack.connection_signature = packet.connection_signature
        ack.payload = b""
        return ack

    def _handle_syn(self, packet):
        logger.info(f"SYN from {self.addr}")
        self.seq_out = 1
        self.seq_in_expected = 1
        self._recv_synced = False
        self._reorder = {}
        self._fragments = []
        self.id_send = 0
        # our connection signature -> client via SYN ACK
        packet.connection_signature = self.id_recv
        return self._make_ack(packet)

    def _handle_connect(self, packet):
        logger.info(f"CONNECT from {self.addr}")
        self.id_send = packet.connection_signature
        self.session_id = packet.session_id
        self.connected = True

        ack = self._make_ack(packet)
        if packet.payload:
            # secure CONNECT: kerberos ticket + check data; reply Buffer(u32 responseCode + 1)
            try:
                ack.payload = self._make_connect_payload(packet.payload)
            except Exception as e:
                logger.error(f"CONNECT payload parse failed: {e}")
                ack.payload = b""
        return ack

    def _make_connect_payload(self, payload):
        from .kerberos import decrypt_connect_check_data
        response_code, user_pid = decrypt_connect_check_data(payload)
        self.pid = user_pid
        return struct.pack("<II", 4, (response_code + 1) & 0xFFFFFFFF)

    def _handle_disconnect(self, packet):
        logger.info(f"DISCONNECT from {self.addr}")
        self.connected = False
        ack = self._make_ack(packet)
        ack.signature = self.id_send
        return ack

    # -- data --------------------------------------------------------------

    async def _handle_data(self, packet):
        # ACK-of-our-DATA from client: nothing to do
        if packet.has_flag(PRUDPPacket.FLAG_ACK):
            return []

        replies = []
        if packet.has_flag(PRUDPPacket.FLAG_NEED_ACK):
            replies.append(self._make_ack(packet))  # always ACK, even out-of-order/dupe

        # Latch the in-order cursor to the first DATA sequence we see.
        if not self._recv_synced:
            self.seq_in_expected = packet.sequence_id
            self._recv_synced = True

        diff = (packet.sequence_id - self.seq_in_expected) & 0xFFFF
        if diff != 0:
            if diff < 0x8000:
                self._reorder[packet.sequence_id] = packet  # future: hold until the gap fills
            # else: already processed (re-ACKed above); drop
            return replies

        # In-order: process this packet and any now-contiguous buffered ones.
        # part_number > 0 means more fragments follow; part 0 is the last.
        pkt = packet
        while True:
            self._fragments.append(pkt.payload)
            self.seq_in_expected = (self.seq_in_expected + 1) & 0xFFFF
            if pkt.part_number == 0:
                rmc_payload = b"".join(self._fragments)
                self._fragments = []
                if self.data_callback and rmc_payload:
                    response = await self.data_callback(self, rmc_payload)
                    if response:
                        replies.extend(self.build_data_packets(pkt, response))
            pkt = self._reorder.pop(self.seq_in_expected, None)
            if pkt is None:
                break
        return replies

    def build_data_packets(self, request_packet, data):
        """Wrap response bytes into (possibly fragmented) DATA packets."""
        fragments = [data[i:i + MAX_FRAGMENT_SIZE]
                     for i in range(0, len(data), MAX_FRAGMENT_SIZE)] or [b""]
        packets = []
        for idx, frag in enumerate(fragments):
            p = PRUDPPacket()
            p.source_vport = request_packet.dest_vport
            p.dest_vport = request_packet.source_vport
            p.type = PRUDPPacket.TYPE_DATA
            p.flags = (PRUDPPacket.FLAG_RELIABLE | PRUDPPacket.FLAG_NEED_ACK
                       | PRUDPPacket.FLAG_HAS_SIZE)
            p.session_id = self.session_id
            p.signature = self.id_send
            p.sequence_id = self.seq_out
            self.seq_out = (self.seq_out + 1) & 0xFFFF
            # last fragment: part 0; earlier fragments from 1
            p.part_number = 0 if idx == len(fragments) - 1 else idx + 1
            p.payload = frag
            packets.append(p)
        return packets
