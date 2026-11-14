"""Locate the sibling skills of the animation-studio plugin and make their scripts importable.

Every script of the plugin starts with:
    import _studio; _studio.use("song-analysis", "toon-2d")      # studio-core is always added
Skills are found relative to this file (<plugin>/skills/<skill>/scripts/_studio.py), never by absolute paths.
"""
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]


def skill_dir(name):
    d = SKILLS / name
    if not (d / "SKILL.md").exists() and not (d / "scripts").is_dir():
        raise SystemExit(f"skill '{name}' of the animation-studio plugin is missing (expected at {d})")
    return d


def use(*names):
    for n in ("studio-core",) + tuple(names):
        p = skill_dir(n) / "scripts"
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
