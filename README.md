# Dirt 2 PS3 Tournament Server

A Quazal RendezVous server that brings Dirt 2 PS3 online back: login, ghosts,
statistics, and tournaments with leaderboards and prizes.

## Running
a sftp server is required for ghosts upload/download, so there are multiple ways to run this, below are two options:

### Option 1 - Docker (SFTP Server included)

1. Install Docker: https://docs.docker.com/engine/install/
2. Download the entire project
3. In `.env`, set `DIRT2_ADVERTISED_ADDRESS` - ip address of the computer you're running this
4. From the project folder, run:

```bash
docker compose up -d
```

### Option 2 - uv (bring your own SFTP server)


1. Install uv: https://docs.astral.sh/uv/getting-started/installation/
2. Download the entire project
3. In `.env`, set:
   - `DIRT2_ADVERTISED_ADDRESS` - ip address of the computer you're running this
   - `SFTP_HOST`, `SFTP_PORT` - your SFTP server's address and port.
   - `SFTP_USER`, `SFTP_PASS` - credentials for that SFTP server.
4. From the project folder, run:

```bash
uv sync
uv run dirtnet/main.py
```

## DNS Redirection

You must redirect `dirt2ps3live.quazal.net` to your machine. Example using
NextDNS (Windows): https://gist.github.com/darkmaizena/0a89ab083c18528274982a23b2bc8d1d

## References

- [PSHome-MultiServer](https://github.com/GitHubProUser67/PSHome-MultiServer)
- [NintendoClients](https://github.com/kinnay/NintendoClients)
