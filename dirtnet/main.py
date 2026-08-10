#!/usr/bin/env python3
import asyncio
import logging
from pathlib import Path

import config
from quazal.common import ClientContext
from quazal.prudp import PRUDPPacket, PRUDPSession
from quazal.rmc import RMCServer
from protocols import AUTH_HANDLERS, SECURE_HANDLERS

# Fixed console-side.
AUTH_PORT = 31020
SECURE_PORT = 31021

logger = logging.getLogger("dirt2")


class QuazalEndpoint(asyncio.DatagramProtocol):
    """One UDP port speaking PRUDP; RMC payloads go to an RMCServer."""

    def __init__(self, name, rmc_server):
        self.name = name
        self.rmc_server = rmc_server
        self.sessions = {}
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        logger.info(f"[{self.name}] UDP endpoint ready")

    def datagram_received(self, data, addr):
        # Fire-and-forget; PRUDP handles retransmission.
        asyncio.ensure_future(self._handle_datagram(data, addr))  # noqa: RUF006

    async def _handle_datagram(self, data, addr):
        # Logs only packets that never reach a protocol.
        try:
            packet = PRUDPPacket.parse(data)
        except ValueError as e:
            logger.warning(
                f"[{self.name}] DROP unparseable from {addr[0]}:{addr[1]}: {e} | hex={data.hex()}"
            )
            return

        if addr not in self.sessions:
            self.sessions[addr] = PRUDPSession(addr, self._handle_rmc)
        session = self.sessions[addr]

        for reply in await session.handle_packet(packet):
            self.transport.sendto(reply.encode(), addr)

    async def _handle_rmc(self, session, payload):
        client_id = f"{self.name}_{session.addr[0]}:{session.addr[1]}"
        client_ctx = ClientContext(client_id, session.pid)
        return await self.rmc_server.handle_request(client_ctx, payload)


def setup_logging():
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "dirtnet.log"),
            logging.StreamHandler(),
        ],
    )
    return logs_dir


async def main():
    setup_logging()

    # Register handlers per endpoint (auth vs secure).
    auth_rmc = RMCServer()
    for cls in AUTH_HANDLERS:
        auth_rmc.register_protocol(cls.PROTOCOL_ID, cls())

    secure_rmc = RMCServer()
    for cls in SECURE_HANDLERS:
        secure_rmc.register_protocol(cls.PROTOCOL_ID, cls())

    # Ports fixed console-side. SECURE_PORT is also advertised by TicketGranting.
    loop = asyncio.get_running_loop()
    auth_transport, _ = await loop.create_datagram_endpoint(
        lambda: QuazalEndpoint("auth", auth_rmc),
        local_addr=(config.BIND_ADDRESS, AUTH_PORT),
    )
    secure_transport, _ = await loop.create_datagram_endpoint(
        lambda: QuazalEndpoint("secure", secure_rmc),
        local_addr=(config.BIND_ADDRESS, SECURE_PORT),
    )

    print("=" * 60)
    print("Dirt 2 - DiRTNET Server")
    print("=" * 60)
    print(f"Listening on: {config.BIND_ADDRESS}")
    logger.info("Server started..")

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        auth_transport.close()
        secure_transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
