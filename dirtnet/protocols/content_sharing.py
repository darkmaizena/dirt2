"""
ContentSharing protocol (83).

    method 1 = RetrieveFTPInfo -> ContentSharingFTPInfo(host, port, user, password)

The console requests these credentials, then transfers the ghost file over SFTP.
"""
import logging

import config
from quazal.common import RMCError, Structure
from quazal.rmc import ProtocolHandler

logger = logging.getLogger(__name__)


class ContentSharingFTPInfo(Structure):
    """ContentSharingFTPInfo::Extract: String host, u32 port, String user,
    String password."""
    def __init__(self, host="", port=0, user="", password=""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def save(self, out, version):
        out.string(self.host)
        out.u32(self.port)
        out.string(self.user)
        out.string(self.password)


class ContentSharingService(ProtocolHandler):
    PROTOCOL_ID = 83

    def __init__(self):
        super().__init__()
        self.sftp_host = config.SFTP_HOST
        self.sftp_port = config.SFTP_PORT
        self.sftp_user = config.SFTP_USER
        self.sftp_pass = config.SFTP_PASS
        self.methods = {1: self.retrieve_ftp_info}

    def retrieve_ftp_info(self, client, input, output):
        logger.info(f"RetrieveFTPInfo -> {self.sftp_user}@{self.sftp_host}:{self.sftp_port}")
        output.add(ContentSharingFTPInfo(
            self.sftp_host, self.sftp_port, self.sftp_user, self.sftp_pass))

    async def handle(self, client, method_id, input_stream, output_stream):
        if method_id not in self.methods:
            logger.warning(f"Unknown ContentSharing method {method_id}")
            raise RMCError(f"Unknown method {method_id}", 0x80010001)
        self.methods[method_id](client, input_stream, output_stream)
