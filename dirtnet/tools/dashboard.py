#!/usr/bin/env python3
# ruff: noqa: S104 - dev tool binds 0.0.0.0
"""In-process tournament dashboard for the DiRT 2 PS3 server (default :8090).

Read-only Vue 3 app (single-file, vendored Vue — no build step) showing the
previous / active / upcoming tournaments and a history of ended runs. Static
files live in tools/static/; the live data comes from /api/state (game.tournament,
same process). Auto-refreshes.
"""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from game import replays
from game import tournament as T

logger = logging.getLogger(__name__)

_STATIC = Path(__file__).resolve().parent / "static"
_TYPES = {".html": "text/html; charset=utf-8",
          ".js": "application/javascript; charset=utf-8",
          ".css": "text/css; charset=utf-8",
          ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml"}


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _static(self, name):
        f = (_STATIC / name).resolve()
        if _STATIC not in f.parents or not f.is_file():
            return self._send(404, "not found", "text/plain")
        self._send(200, f.read_bytes(), _TYPES.get(f.suffix, "application/octet-stream"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._static("index.html")
        if path == "/api/state":
            return self._send(200, json.dumps(T.state_snapshot()))
        if path == "/api/replays":
            return self._send(200, json.dumps(replays.list_replays()))
        if path.startswith("/") and "/" not in path[1:]:  # top-level static file
            return self._static(path.lstrip("/"))
        self._send(404, "{}")

    def log_message(self, *a):  # quiet
        pass


def start_dashboard(host="0.0.0.0", port=8091):
    """Start the read-only dashboard in a daemon thread (call once at boot)."""
    srv = ThreadingHTTPServer((host, port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True,
                     name="dashboard").start()
    logger.info(f"tournament dashboard on http://{host}:{port}")
    return srv


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_dashboard()
    print("dashboard on http://localhost:8091")
    import time
    while True:
        time.sleep(3600)
