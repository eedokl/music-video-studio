"""Project storage: projects/<id>/project.json plus audio, analysis and custom wall modules.

Saves are atomic (write temp file, then replace) and every save keeps the previous version in
.history/ so nothing is lost when the editor or the chat agent changes something.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
from pathlib import Path

from .config import PROJECTS

_lock = threading.Lock()
HISTORY_KEEP = 60


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("-")
    return s or "song"


def project_dir(pid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", pid):
        raise ValueError("bad project id")
    return PROJECTS / pid


def new_id(title: str) -> str:
    base = slug(title)[:60]
    pid, n = base, 2
    while (PROJECTS / pid).exists():
        pid = f"{base}-{n}"
        n += 1
    return pid


def list_projects() -> list[dict]:
    out = []
    for d in sorted(PROJECTS.iterdir()) if PROJECTS.exists() else []:
        f = d / "project.json"
        if not f.exists():
            continue
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append({"id": d.name, "title": p.get("title", d.name), "duration": p.get("audio", {}).get("duration"), "updated": f.stat().st_mtime, "status": p.get("status", "ready")})
    out.sort(key=lambda x: -x["updated"])
    return out


def load(pid: str) -> dict:
    return json.loads((project_dir(pid) / "project.json").read_text(encoding="utf-8"))


def version(pid: str) -> float:
    f = project_dir(pid) / "project.json"
    return f.stat().st_mtime_ns / 1e9 if f.exists() else 0.0


def save(pid: str, data: dict, keep_history: bool = True) -> float:
    d = project_dir(pid)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "project.json"
    with _lock:
        if keep_history and f.exists():
            h = d / ".history"
            h.mkdir(exist_ok=True)
            shutil.copy2(f, h / f"{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.json")
            old = sorted(h.glob("*.json"))
            for o in old[:-HISTORY_KEEP]:
                o.unlink(missing_ok=True)
        tmp = d / "project.json.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, f)
    return version(pid)


def history(pid: str) -> list[str]:
    h = project_dir(pid) / ".history"
    return sorted(p.name for p in h.glob("*.json")) if h.exists() else []


def restore(pid: str, name: str) -> float:
    src = project_dir(pid) / ".history" / name
    if not src.exists() or "/" in name or "\\" in name:
        raise FileNotFoundError(name)
    return save(pid, json.loads(src.read_text(encoding="utf-8")))


def safe_file(pid: str, rel: str) -> Path:
    """Resolve a file inside the project folder (no path escapes)."""
    base = project_dir(pid).resolve()
    p = (base / rel).resolve()
    if base not in p.parents and p != base:
        raise ValueError("path outside project")
    return p
