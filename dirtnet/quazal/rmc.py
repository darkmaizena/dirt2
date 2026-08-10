"""
Minimal RMC (Remote Method Call) protocol implementation for Dirt 2
"""
import logging
import struct

from quazal.common import RMCError, StreamIn, StreamOut

logger = logging.getLogger(__name__)


class RMCMessage:
    """RMC protocol message"""
    REQUEST = 0
    RESPONSE = 1

    def __init__(self):
        self.mode = self.REQUEST
        self.protocol = None
        self.method = None
        self.call_id = 0
        self.error = -1
        self.body = b""

    @staticmethod
    def response(protocol, method, call_id, body):
        msg = RMCMessage()
        msg.mode = RMCMessage.RESPONSE
        msg.protocol = protocol
        msg.method = method
        msg.call_id = call_id
        msg.body = body
        return msg

    @staticmethod
    def error(protocol, method, call_id, error_code):
        msg = RMCMessage()
        msg.mode = RMCMessage.RESPONSE
        msg.protocol = protocol
        msg.method = method
        msg.call_id = call_id
        msg.error = error_code
        return msg

    def encode(self):
        """Encode RMC message to binary"""
        stream = StreamOut()

        flag = 0x80 if self.mode == self.REQUEST else 0
        if self.protocol < 0x80:
            stream.u8(self.protocol | flag)
        else:
            stream.u8(0x7F | flag)
            stream.u16(self.protocol)

        if self.mode == self.REQUEST:
            stream.u32(self.call_id)
            stream.u32(self.method)
            stream.data += self.body
        else:
            if self.error != -1:
                stream.bool(False)
                stream.u32(self.error | 0x80000000)
                stream.u32(self.call_id)
            else:
                stream.bool(True)
                stream.u32(self.call_id)
                stream.u32(self.method | 0x8000)
                stream.data += self.body

        # Prepend size
        data = stream.get()
        return struct.pack("<I", len(data)) + data

    @staticmethod
    def parse(data):
        """Parse binary data into RMC message"""
        stream = StreamIn(data)

        length = stream.u32()
        if length != stream.remaining():
            raise ValueError("RMC message has unexpected size")

        msg = RMCMessage()

        # Read protocol and determine mode
        protocol_flag = stream.u8()
        if protocol_flag & 0x80:
            msg.mode = RMCMessage.REQUEST
            msg.protocol = protocol_flag & 0x7F
        else:
            msg.mode = RMCMessage.RESPONSE
            msg.protocol = protocol_flag

        if msg.protocol == 0x7F:
            msg.protocol = stream.u16()

        if msg.mode == RMCMessage.REQUEST:
            msg.call_id = stream.u32()
            msg.method = stream.u32()
            msg.body = data[stream.pos:]
        else:
            success = stream.bool()
            if success:
                msg.call_id = stream.u32()
                msg.method = stream.u32() & 0x7FFF
                msg.body = data[stream.pos:]
            else:
                msg.error = stream.u32()
                msg.call_id = stream.u32()

        return msg


class RMCServer:
    """RMC protocol server"""
    def __init__(self):
        self.protocols = {}

    def register_protocol(self, protocol_id, handler):
        """Register a protocol handler"""
        self.protocols[protocol_id] = handler

    async def handle_request(self, client, data):
        """Dispatch an RMC request to its protocol handler."""
        try:
            message = RMCMessage.parse(data)

            # RESPONSE = client answer to a server->client call, or stray/dup;
            # consumed silently (already ACKed by PRUDP)
            if message.mode != RMCMessage.REQUEST:
                return None

            if message.protocol not in self.protocols:
                logger.warning(f"Unknown protocol: {message.protocol}")
                return RMCMessage.error(
                    message.protocol, message.method, message.call_id,
                    0x80010001,  # Core::NotImplemented
                ).encode()

            handler = self.protocols[message.protocol]
            input_stream = StreamIn(message.body)
            output_stream = StreamOut()

            try:
                await handler.handle(client, message.method,
                                     input_stream, output_stream)
                return RMCMessage.response(
                    message.protocol, message.method, message.call_id,
                    output_stream.get(),
                ).encode()
            except RMCError as e:
                return RMCMessage.error(
                    message.protocol, message.method, message.call_id, e.code,
                ).encode()

        except Exception as e:
            logger.error(f"Failed to handle RMC request: {e}")
            return RMCMessage.error(0, 0, 0, 0x80010001).encode()


class ProtocolHandler:
    """Base class for protocol handlers"""
    def __init__(self):
        self.methods = {}

    async def handle(self, client, method_id, input_stream, output_stream):
        """Handle a method call"""
        if method_id in self.methods:
            await self.methods[method_id](client, input_stream, output_stream)
        else:
            raise RMCError(f"Unknown method: {method_id}", 0x80010001)
