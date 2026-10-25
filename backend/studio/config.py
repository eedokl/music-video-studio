"""Paths and settings of the studio (override with environment variables)."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("STUDIO_ROOT", Path(__file__).resolve().parents[2]))
PROJECTS = Path(os.environ.get("STUDIO_PROJECTS", ROOT / "projects"))
PIPELINE = ROOT / "backend" / "pipeline"
FRONTEND_DIST = ROOT / "frontend" / "dist"
RENDERER = ROOT / "renderer"
DOCS = ROOT / "docs"
PORT = int(os.environ.get("STUDIO_PORT", "8000"))
# the page the MP4 renderer opens (the backend serves the built frontend)
RENDER_BASE = os.environ.get("STUDIO_RENDER_BASE", f"http://127.0.0.1:{PORT}")
CLAUDE_BIN = os.environ.get("STUDIO_CLAUDE", "claude")
CLAUDE_MODEL = os.environ.get("STUDIO_CLAUDE_MODEL", "")  # empty = Claude Code default

PROJECTS.mkdir(parents=True, exist_ok=True)


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
