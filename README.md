# Dirt 2 PS3 Tournament Server

A Quazal RendezVous server that brings Dirt 2 PS3 online back: login, ghosts,
statistics, and tournaments with leaderboards and prizes.

## About Ghosts

Ghost times live on the PSN leaderboards, but the ghost files themselves were stored on DIRTNET, which is gone. The old records are lost to time, so everyone starts fresh and sets new ones.

The recommended way to unlock the trophy: play a track while logged in, upload your run at the end, then find your record through the Friends section of the leaderboard. Coordinating with a friend (or using a second account) makes this easier. Confirm the time shows on the PSN leaderboard first.

Heads up: the PSN leaderboards can be unreliable. Not every record posts, and a time can take a while to appear. If yours is missing, give it some time or try again. It can also help to try a different track and car/category combination, or even a different account.

## Running

You can either use the public server or self-host your own.

### Option 1 - Public server

No installation needed: redirect `dirt2ps3live.quazal.net` to the public server's address (see [DNS Redirection](#dns-redirection) below) and play.

### Option 2 - Self-host with Docker (SFTP server included)

An SFTP server is required for ghost upload/download; this option bundles one.

1. Install Docker: https://docs.docker.com/engine/install/
2. Download the entire project
3. In `.env`, set `DIRT2_ADVERTISED_ADDRESS` - ip address of the computer you're running this
4. From the project folder, run:

```bash
docker compose up -d
```

### Option 3 - Self-host with uv (bring your own SFTP server)

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

You must redirect `dirt2ps3live.quazal.net` to the server you're using - the public server's address, or your own machine if self-hosting. Example using
NextDNS (Windows): https://gist.github.com/darkmaizena/0a89ab083c18528274982a23b2bc8d1d

## References

- [PSHome-MultiServer](https://github.com/GitHubProUser67/PSHome-MultiServer)
- [NintendoClients](https://github.com/kinnay/NintendoClients)
