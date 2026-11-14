# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Plan, texture and render brick-film sections, then hand over to film-finish.

  python render.py <section> --stills 0,120,300     plan + test frames -> stills/<section>/still_NNNN.png
  python render.py <section>                        plan + all frames  -> scenes/<section>/f.0000.png ...
  python render.py --all                            every section of project.json
  options: --project .  --keep-plan (render bricks/<section>.json as edited by hand)  --percent 50 --samples 16
           (fast drafts)  --remeasure (exposure again)  --cycles (path tracing, slow)  --preview (film-finish
           overlays + preview/<section>.mp4 afterwards)
Rendering takes the GPU lock (bricks-3d/blender_run.py); EEVEE needs ~0.3-0.6 s per frame at 1280x720.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "bricks-3d")
import config  # noqa: E402
from song_project import Project  # noqa: E402

B3D = _studio.skill_dir("bricks-3d") / "scripts"
FF = _studio.skill_dir("film-finish") / "scripts"
HERE = Path(__file__).resolve().parent


def run(cmd):
    print("  $", " ".join(str(c) for c in cmd[-6:]), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def section(P, name, a):
    plan_f = P.dir / "bricks" / f"{name}.json"
    if not (a.keep_plan and plan_f.exists()):
        run([sys.executable, HERE / "plan.py", name, "--project", P.dir])
    plan = json.loads(plan_f.read_text(encoding="utf-8"))
    tex = Path(plan["textures"])
    tex.mkdir(parents=True, exist_ok=True)
    scr = P.cache / f"screens_{name}.json"
    scr.write_text(json.dumps(plan["screen"].get("tile_specs", [{"kind": "code"}]), ensure_ascii=False), encoding="utf-8")
    signs = P.cache / f"signs_{name}.json"                   # name signs on robot torsos (neutral lettering)
    signs.write_text(json.dumps([{"text": f["sign"], "file": f["sign_tex"]} for f in plan["figures"] if f.get("sign")],
                                ensure_ascii=False), encoding="utf-8")
    run(config.script_cmd(B3D / "textures.py") + [tex, "--screens", scr,
         "--signs", signs, "--seed", str(plan.get("seed", 7) % 1000)])
    extra = []
    for k in ("percent", "samples"):
        if getattr(a, k):
            extra += [f"--{k}", str(getattr(a, k))]
    extra += [x for x, on in (("--remeasure", a.remeasure), ("--cycles", a.cycles)) if on]
    if a.stills:
        run([sys.executable, B3D / "blender_run.py", "brickfilm.py", "--", plan_f, "--stills", a.stills, *extra])
        return
    out = Path(plan["out"])
    for old in out.glob("f.*.png"):                          # a re-render must not leave stale frames behind
        old.unlink()
    run([sys.executable, B3D / "blender_run.py", "brickfilm.py", "--", plan_f, "--render", *extra])
    n = len(list(out.glob("f.*.png")))
    want = round((plan["to"] - plan["from"]) * plan["fps"])
    print(f"-> scenes/{name}: {n}/{want} frames", flush=True)
    if a.preview:
        run(config.script_cmd(FF / "overlays.py") + [name, "--project", P.dir])
        run(config.script_cmd(FF / "build.py") + ["preview", name, "--project", P.dir])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("section", nargs="?")
    ap.add_argument("--project", default=".")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--stills")
    ap.add_argument("--keep-plan", action="store_true")
    ap.add_argument("--percent", type=int)
    ap.add_argument("--samples", type=int)
    ap.add_argument("--remeasure", action="store_true")
    ap.add_argument("--cycles", action="store_true")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("bricks-music-video")                 # project.json validated before any long step
    names = [s["name"] for s in P.sections()] if a.all or not a.section else [a.section]
    for n in names:
        section(P, n, a)


if __name__ == "__main__":
    main()
