"""List ghost/replay files from the shared ghost storage (sftpgo home).

Layout: <root>/ghosts2/<ids>/<PSN online id>/<name>.rgf
  - user  = parent directory (PSN online id)
  - track = parsed from the filename (e.g. Lapbaja_ironroute_0rally)
  - car   = null-terminated ASCII code in the .rgf header (e.g. n12_01)
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _car_code(path):
    """Car code string from the .rgf header (u32 version, then the code)."""
    try:
        head = path.read_bytes()[:64]
        end = head.find(b"\x00", 5)
        code = head[5:end]
        return code.decode("latin1") if code.isascii() and code else None
    except OSError:
        return None


def _parse_name(stem):
    """(track, discipline) best-effort from the filename tokens."""
    parts = stem.split("_")
    track = parts[1] if len(parts) >= 2 else stem
    discipline = parts[2] if len(parts) >= 3 else None
    return track, discipline


def list_replays(root=None):
    """[{user, track, discipline, car, file, path, size, modified}] for every
    .rgf under the ghost root (empty if the root is absent)."""
    base = Path(root or "/ghosts")
    if not base.is_dir():
        return []
    out = []
    for p in sorted(base.rglob("*.rgf")):
        if p.name.startswith("._"):
            continue  # macOS AppleDouble sidecar, not a ghost
        try:
            st = p.stat()
        except OSError:
            continue
        track, discipline = _parse_name(p.stem)
        out.append({
            "user": p.parent.name,
            "track": track,
            "discipline": discipline,
            "car": _car_code(p),
            "file": p.name,
            "path": str(p.relative_to(base)),
            "size": st.st_size,
            "modified": int(st.st_mtime),
        })
    return out
