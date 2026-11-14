"""Painted sets bundled with toon-2d (assets/sets/<name>/set.json + PNGs) or your own set folders.

    from sets import load_set, set_layers
    info = load_set("park")                     # dict from set.json, plus "dir"
    back, front = set_layers("park")            # Synfig image layers: back goes under the figures, front over them
    view = info.get("view", "-8 4.5 8 -4.5")

set.json keys: description, back [png...], front [png...], image_box [l, t, r, b] (units; default = the 16x9 view
-8 4.5 8 -4.5), view (camera that frames it best), floor (y of the feet), places {name: x}, scale (figure scale),
screen [l, t, r, b] (a screen for the Computer), desk {top, color}, glow,
window {layer, x, y} (index into "back" where things seen THROUGH a window go - the room set: 1 = between sky and wall).
Bundled: stage (theatre, curtains in front), room (Tim's room at night, desk + monitor), park (blurred park path).
Own sets: a folder with the same layout; pass its path instead of a name.
"""
import json
from pathlib import Path

import _studio
from sif import image

SETS = _studio.skill_dir("toon-2d") / "assets" / "sets"


def load_set(name):
    d = Path(name) if Path(name).is_dir() else SETS / name
    f = d / "set.json"
    if not f.exists():
        avail = ", ".join(sorted(p.name for p in SETS.iterdir() if (p / "set.json").exists()))
        raise SystemExit(f"set '{name}' not found (bundled: {avail})")
    info = json.loads(f.read_text(encoding="utf-8"))
    info["dir"] = d
    return info


def set_layers(name, box=None):
    """-> (back layers, front layers) as Synfig image layers filling image_box (or `box`)."""
    info = load_set(name)
    l, t, r, b = box or info.get("image_box", (-8, 4.5, 8, -4.5))
    mk = lambda files, kind: [image(f"Set {info['dir'].name} {kind} {Path(fn).stem}", info["dir"] / fn, tl=(l, t), br=(r, b))
                              for fn in files]
    return mk(info.get("back", []), "back"), mk(info.get("front", []), "front")
