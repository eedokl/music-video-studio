# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Turn a song project (song-analysis new_project.py) into a brick-film project: minifig looks for the figures,
a brick set per section (varied with the creative seed), the "bricks" options block and a seed.

  uv run setup.py [<project>] [--sections "verse:0-19.5,chorus:19.5-40"] [--set room]
         [--cameo mann:silhouette] [--look tim=rocker] [--seed 4711]
Without --sections the existing sections stay (new_project.py makes one section "all").
Sets: room | stage | rooftop | house | arena | cloud (bricks-3d layouts.SETS). Looks: see bricks-3d/assets/cast.json. Never overwrites choices already in project.json
except the ones given on the command line.
"""
import argparse
import json

import _studio  # noqa: E402
_studio.use("song-analysis", "bricks-3d")
import creative  # noqa: E402
from layouts import SETS  # noqa: E402
from song_project import Project  # noqa: E402

CAST = json.loads((_studio.skill_dir("bricks-3d") / "assets" / "cast.json").read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--sections")
    ap.add_argument("--set")
    ap.add_argument("--cameo", action="append", default=[])
    ap.add_argument("--look", action="append", default=[])
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    P = Project(a.project)
    p = P.p
    if a.seed is not None:
        p["seed"] = a.seed
    creative.seed(P)
    figs = p.setdefault("figures", {})
    for n, f in figs.items():
        if f.get("kind") == "screen" or f.get("minifig"):
            continue
        f["minifig"] = CAST["figure_defaults"].get(n) or {"male": "rocker", "female": "singer"}.get(f.get("voice"), "robot")
    for kv in a.look:
        n, look = kv.split("=")
        figs.setdefault(n, {})["minifig"] = look
    for c in a.cameo:
        n, _, look = c.partition(":")
        figs[n] = dict(figs.get(n, {}), minifig=look or "silhouette", cameo=True, voice=None)
    if a.sections:
        old = {s["name"]: s for s in p.get("sections", [])}
        secs = []
        for part in a.sections.split(","):
            name, rng = part.split(":")
            t0, t1 = map(float, rng.split("-"))
            s = dict(old.get(name, {}), name=name, **{"from": t0, "to": t1})
            s.setdefault("figures", [n for n in figs if not figs[n].get("cameo")] + [n for n in figs if figs[n].get("cameo")])
            secs.append(s)
        p["sections"] = secs
    prev = None
    for s in p.get("sections", []):
        if a.set:
            s["set"] = a.set
        if s.get("set") not in SETS:
            r = creative.rng(P, f"bricks:setup:{s['name']}")
            s["set"] = r.choice([k for k in SETS if k != prev])
        for n in figs:
            if figs[n].get("cameo") and n not in s.setdefault("figures", list(figs)):
                s["figures"].append(n)
        prev = s["set"]
    p.setdefault("bricks", {"samples": 32, "camera": "calm"})
    for k in ("gestures", "props", "screen", "gags"):
        p.setdefault(k, [])
    P.file.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"brick project: seed {p['seed']}, sections {[(s['name'], s['set']) for s in p['sections']]}, "
          f"looks {({n: f.get('minifig') for n, f in figs.items()})}")


if __name__ == "__main__":
    main()
