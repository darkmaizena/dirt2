"""
Quazal TicketGrantingService (protocol 10) for Dirt 2 PS3, ported from QNetZ
RDVServices (TicketGrantingService.cs). Auth server: login / ticket granting.
"""
import logging

import config
from game import accounts
from quazal import kerberos
from quazal.common import RMCError, Structure
from quazal.rmc import ProtocolHandler

logger = logging.getLogger(__name__)


def _dump_remaining(input, tag):
    """Hexdump the unread tail of a request body + pull ASCII className runs
    (the custom AnyData/DynamicData bag the client sends at login/register)."""
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


# ErrorCode.Core_NoError in QNetZ serialized retVal
CORE_NO_ERROR = 0x10001
GUEST_PID = 100
SERVER_PID = 2  # sPID of the secure backend


def station_url(scheme, address, params):
    """QNetZ StationURL string: scheme:/address=IP;key=val;..."""
    if not address:
        return f"{scheme}:/"
    param_str = ";".join(f"{k}={v}" for k, v in params.items())
    sep = ";" if param_str else ""
    return f"{scheme}:/address={address}{sep}{param_str}"


class RVConnectionData(Structure):
    """StationURL urlRegularProtocols, empty lstSpecialProtocols, empty
    urlSpecialProtocols."""
    def __init__(self, url=""):
        self.url = url

    def save(self, out, version):
        out.string(self.url)
        out.u32(0)       # m_lstSpecialProtocols: empty byte list
        out.string("")   # m_urlSpecialProtocols: empty StationURL


class LoginResponse(Structure):
    """retVal, pidPrincipal, pbufResponse(ticket), RVConnectionData, strReturnMsg."""
    def __init__(self, pid=0, ticket=b"", url=""):
        self.pid = pid
        self.ticket = ticket
        self.url = url

    def save(self, out, version):
        out.u32(CORE_NO_ERROR)
        out.u32(self.pid)
        out.buffer(self.ticket)
        out.add(RVConnectionData(self.url))
        out.string("")


class RequestTicketResponse(Structure):
    """retVal, pbufResponse(ticket)."""
    def __init__(self, ticket=b""):
        self.ticket = ticket

    def save(self, out, version):
        out.u32(CORE_NO_ERROR)
        out.buffer(self.ticket)


class TicketGrantingService(ProtocolHandler):
    """Protocol 10 - login / ticket granting (auth server)."""

    PROTOCOL_ID = 10

    def __init__(self):
        super().__init__()
        self.server_address = config.ADVERTISED_ADDRESS
        self.secure_port = 31021  # secure server port, fixed console-side
        self.methods = {
            1: self.handle_login,
            2: self.handle_login_ex,
            3: self.handle_request_ticket,
        }

    def _pid_for(self, username):
        """Stable pid per account (persisted). Empty/guest -> GUEST_PID,
        "Tracking" -> 0."""
        if not username or username in ("guest", "Tracking"):
            return 0 if username == "Tracking" else GUEST_PID
        return accounts.find_or_create_account(username)

    def _secure_url(self):
        return station_url("prudps", self.server_address, {
            "port": self.secure_port,
            "CID": 1,
            "PID": SERVER_PID,
            "sid": 1,
            "stream": 3,
            "type": 2,
        })

    def _write_login_response(self, output, pid, password):
        ticket = kerberos.make_ticket(pid, SERVER_PID, password)
        output.add(LoginResponse(pid, ticket, self._secure_url()))

    def handle_login(self, client, input, output):
        username = input.string()
        pid = self._pid_for(username)
        logger.info(f"Login('{username}') from {client} -> pid={pid}")
        self._write_login_response(output, pid, kerberos.password_for_pid(pid))

    def handle_login_ex(self, client, input, output):
        username = input.string()
        pid = self._pid_for(username)
        logger.info(f"LoginEx('{username}') from {client} -> pid={pid}")
        _dump_remaining(input, "LoginEx.customData")
        self._write_login_response(output, pid, kerberos.password_for_pid(pid))

    def handle_request_ticket(self, client, input, output):
        source_pid = input.u32()
        target_pid = input.u32()
        logger.info(f"RequestTicket({source_pid}, {target_pid})")

        ticket = kerberos.make_ticket(
            source_pid, target_pid, kerberos.password_for_pid(source_pid))
        output.add(RequestTicketResponse(ticket))

    async def handle(self, client, method_id, input_stream, output_stream):
        if method_id not in self.methods:
            raise RMCError(f"Unknown TicketGranting method {method_id}",
                           0x80010001)
        self.methods[method_id](client, input_stream, output_stream)
