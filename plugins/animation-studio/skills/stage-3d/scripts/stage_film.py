# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""Build one clip of a 3D film project and render stills or a frame range.

  blender -b --factory-startup --python stage_film.py -- <project> <clip> [--q draft|preview|film|final]
          [--stills 1,40,90] [--every 24] [--range 1 120] [--overwrite] [--save]

  <project>  folder with project.json and scenes/<clip>.py (the module defines FRAMES, optionally SEED, and build(S))
  --stills / --every   single frames -> out/<clip>/stills_<q>/f_####.png
  --range a b          frame range -> out/<clip>/<q>/f_####.png (existing files are skipped: resumable;
                       --overwrite renders them again)
  --save               write out/<clip>/<clip>.blend for inspection
Always writes out/<clip>/build.json: frames, the camera cuts and the frame ranges of the spoken lines.
"""
import importlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    project, clip = Path(a[0]).resolve(), a[1]
    opt = {"q": "draft"}
    i = 2
    while i < len(a):
        k = a[i].lstrip("-")
        if k in ("save", "overwrite"):
            opt[k] = True
            i += 1
        elif k == "range":
            opt[k] = (int(a[i + 1]), int(a[i + 2]))
            i += 3
        else:
            opt[k] = a[i + 1]
            i += 2
    os.environ["STAGE3D_PROJECT"] = str(project)
    sys.path.insert(0, str(project))
    import stage_actor as K
    import stage_core as C
    C.PROJECT = project
    pj = project / "project.json"
    P = json.loads(pj.read_text(encoding="utf-8")) if pj.exists() else {}
    K.LIPS["strong"] = P.get("lips") == "strong"
    C.set_palette(P.get("palette"))
    t0 = time.time()
    mod = importlib.import_module("scenes." + clip)
    S = C.Stage(clip, mod.FRAMES, seed=getattr(mod, "SEED", P.get("seed", 1)))
    mod.build(S)
    S.bake()
    print(f"BUILT {clip} in {time.time() - t0:.1f}s", flush=True)
    q = opt["q"]
    C.render_setup(S, q, res=tuple(P.get("size") or (1920, 1080)))
    out = project / "out" / clip
    out.mkdir(parents=True, exist_ok=True)
    (out / "build.json").write_text(json.dumps({
        "clip": clip, "frames": mod.FRAMES, "device": S.device, "cuts": [f0 for f0, _ in S.shots],
        "said": [{"id": s[3], "start": s[4], "from": s[1], "to": s[2]} for s in sorted(K.SAID, key=lambda s: s[4])
                 if s[0] == clip]}, indent=1), encoding="utf-8")
    if opt.get("save"):
        import bpy
        bpy.ops.wm.save_as_mainfile(filepath=str(out / (clip + ".blend")))
    if "stills" in opt or "every" in opt:
        stills = ([int(x) for x in opt["stills"].split(",")] if "stills" in opt
                  else list(range(1, mod.FRAMES + 1, int(opt["every"]))))
        bad = [f for f in stills if not 1 <= f <= mod.FRAMES]
        if bad:
            raise SystemExit(f"{clip} has frames 1..{mod.FRAMES}; not in it: {bad}")
        C.render(S, out / ("stills_" + q), stills=stills)
    elif "range" in opt:
        f0, f1 = opt["range"]
        C.render(S, out / q, frames=(max(1, f0), min(mod.FRAMES, f1)), overwrite=bool(opt.get("overwrite")))
    print(f"DONE {clip} {time.time() - t0:.1f}s ({S.device})", flush=True)


main()
