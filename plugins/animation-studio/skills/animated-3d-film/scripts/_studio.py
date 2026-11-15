"""Locate the sibling skills of the animation-studio plugin and make their scripts importable.

Every script of the plugin starts with:
    import _studio; _studio.use("song-analysis", "toon-2d")      # studio-core is always added
Skills are found relative to this file (<plugin>/skills/<skill>/scripts/_studio.py), never by absolute paths.
The calling skill's own scripts/ folder always stays FIRST on sys.path, so a module of the skill itself wins over a
sibling's module of the same name (several skills have a mouth.py / scene.py / plan.py ...).

This file is identical in every skill (tests/smoke.py checks it) - change it here and copy it to all skills.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]

# Windows consoles (cp1252) crash on characters such as U+FFFD in tsc / Whisper output - replace them instead
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass


def _refresh_root():
    """Scene folders find the plugin through the machine-config entry "animation_studio_root" (toon-2d new_scene.py).
    After a plugin update that entry still points at the old version folder, which exists for a while - so whenever a
    plugin script runs from a different (valid) plugin folder, the entry is moved to this one. Only an existing entry
    is updated; failures are ignored (read-only home, corrupt file - check_tools.py reports those)."""
    import json
    import os
    root = SKILLS.parent
    cfg = Path(os.environ.get("ANIMATION_STUDIO_CONFIG") or Path.home() / ".animation-studio" / "config.json")
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        old = data.get("animation_studio_root")
        if not old or Path(old).resolve() == root or not (root / "skills" / "toon-2d" / "scripts" / "_studio.py").exists():
            return
        data["animation_studio_root"] = root.as_posix()
        tmp = cfg.with_name(cfg.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.replace(tmp, cfg)
    except (OSError, ValueError, AttributeError):
        pass


_refresh_root()


def skill_dir(name):
    d = SKILLS / name
    if not (d / "SKILL.md").exists() and not (d / "scripts").is_dir():
        raise SystemExit(f"skill '{name}' of the animation-studio plugin is missing (expected at {d})")
    return d


def use(*names):
    own = str(HERE)
    if own in sys.path:
        sys.path.remove(own)
    sys.path.insert(0, own)
    for n in ("studio-core",) + tuple(names):
        p = str(skill_dir(n) / "scripts")
        if p != own and p not in sys.path:
            sys.path.insert(1, p)                     # right after the skill's own folder
