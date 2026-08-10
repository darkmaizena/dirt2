import os

BIND_ADDRESS = os.environ.get("DIRT2_BIND_ADDRESS", "0.0.0.0")
ADVERTISED_ADDRESS = os.environ["DIRT2_ADVERTISED_ADDRESS"]

# SFTP server for ghost files
SFTP_HOST = os.environ.get("SFTP_HOST", ADVERTISED_ADDRESS)
SFTP_PORT = int(os.environ.get("SFTP_PORT", "2121"))
SFTP_USER = os.environ.get("SFTP_USER", "dirt")
SFTP_PASS = os.environ.get("SFTP_PASS", "dirt")
