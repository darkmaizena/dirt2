"""
Quazal kerberos-style ticketing, ported from QNetZ
(KerberosTicket.cs, Helper.cs, Constants.cs, QPacketHandlerPRUDP.cs).
"""

import hashlib
import hmac
import logging
import struct

from .prudp import rc4

logger = logging.getLogger(__name__)

# Ticket derive-key password (KerberosTicket.ToBuffer); PS3 console login path.
# Client derives same key from pidPrincipal + this to decrypt pbufResponse;
# must match or login loops.
DIRT2_PASSWORD = b"PS3NPDummyPwd"
GUEST_PASSWORD = b"h7fyctiuucf"  # Quazal guest account (PID 100)


SESSION_KEY = bytes(
    [
        0x9C,
        0xB0,
        0x1D,
        0x7A,
        0x2C,
        0x5A,
        0x6C,
        0x5B,
        0xED,
        0x12,
        0x68,
        0x45,
        0x69,
        0xAE,
        0x09,
        0x0D,
    ]
)

TICKET_DATA = bytes(
    [
        0x76,
        0x21,
        0x4B,
        0xA6,
        0x21,
        0x96,
        0xD3,
        0xF3,
        0x9A,
        0x8C,
        0x7A,
        0x27,
        0x0D,
        0xD9,
        0xB3,
        0xFA,
        0x21,
        0x0E,
        0xED,
        0xAF,
        0x42,
        0x63,
        0x92,
        0x95,
        0xC1,
        0x16,
        0x54,
        0x08,
        0xEE,
        0x6E,
        0x69,
        0x17,
        0x35,
        0x78,
        0x2E,
        0x6E,
    ]
)


def derive_key(pid, password):
    """Helper.DeriveKey: iterate MD5 65000 + (pid % 1024) times."""
    count = 65000 + (pid % 1024)
    buff = password
    for _ in range(count):
        buff = hashlib.md5(buff).digest()  # noqa: S324 - Quazal Helper.DeriveKey mandates MD5
    return buff


def make_ticket(user_pid, server_pid, password, session_key=SESSION_KEY, ticket_data=TICKET_DATA):
    """KerberosTicket.ToBuffer: RC4(derived key, sessionKey + serverPID +
    ticket) + HMAC-MD5."""
    body = session_key + struct.pack("<II", server_pid, len(ticket_data)) + ticket_data
    key = derive_key(user_pid, password)
    encrypted = rc4(key, body)
    mac = hmac.new(key, encrypted, hashlib.md5).digest()
    return encrypted + mac


def password_for_pid(pid):
    """Guest pid 100 uses the guest password; all others DIRT2_PASSWORD."""
    if pid == 100:
        return GUEST_PASSWORD
    return DIRT2_PASSWORD


def decrypt_connect_check_data(payload):
    """QPacketHandlerPRUDP.MakeConnectPayload: parse the secure-server
    CONNECT payload and return the response code (caller replies with
    Buffer(u32 responseCode + 1)).
    """
    offset = 0
    ticket_size = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    _ticket = payload[offset : offset + ticket_size]
    offset += ticket_size

    enc_size = struct.unpack_from("<I", payload, offset)[0] - 16
    offset += 4
    buff = rc4(SESSION_KEY, payload[offset : offset + enc_size])

    user_pid, connection_id, response_code = struct.unpack_from("<III", buff, 0)
    logger.info(
        f"CONNECT check data: pid={user_pid} cid={connection_id} responseCode={response_code}"
    )
    return response_code, user_pid
