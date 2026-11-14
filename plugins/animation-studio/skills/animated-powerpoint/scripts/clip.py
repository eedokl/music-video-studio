# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Build and render one presentation clip: figures step out of the flat slide into a 2.5D room.

  clip.py clips/<name>/clip.json [--only plan|synfig|light|tex|3d|final] [--jobs 8]

clip.json (paths relative to it):
  {"deck": "../../deck/deck.json", "slide": 5, "figures_dir": "../../figures",
   "size": [1920, 1080],                  output size; default = 1920 x slide aspect (fits the presentation)
   "fps": 24, "look": "standard" | "none", "ending": "stay" | "return" (return = loopable, last frame = first),
   "boil": 0.0012,                        line boil in the room (0 = off)
   "hold": 36,                            ending "return": frames the tag stays before the hop back
   "figures": [{"name": "fritz", "action": "step_out", "start": 22, "tag": ["Fritz", "Builder"],
                "gesture": "fist", "spin": "flip", "gesture_part": "arm_r", "land": [-0.3, 3.2]},
               {"name": "hans", "action": "watch"}],
   "tail": 0,                              extra frames at the end
   "camera": [[0, [0, 0, 16.79, 0, 0, 0]], [{"fig": "fritz", "event": "land", "offset": 6}, [-4.2, -1.7, 12.4, 1, -2.6, 2.6]]]}
                                           optional own camera keys (time specs allowed) instead of the automatic shots
Figures not listed stay in the slide picture. "start" = first frame of the routine (look around); the routines of
several step_out figures follow each other when "start" is left out.
Steps (each writes into the clip folder, a later step reuses the earlier results):
  plan    acting keys + per-frame stage values -> <fig>.sif, stage.json
  synfig  Synfig renders every figure alone (transparent) -> frames/<fig>/<fig>.NNNN.png   (toon-2d render.py)
  light   light maps for flat -> rounded -> light/<fig>/s.NNNN.png
  tex     slide states (figures removed, dashed outlines), room, shadow, name tags -> tex/
  3d      three.js stage in headless Edge/Chrome -> frames_3d/mp_NNNN.png, stage.mp4      (toon-2d render_multiplane.py)
  final   look (film-finish apply_look.py) -> <name>.mp4, first/last frame PNG, contact sheet, in/out check
  sound   narration + sound effects on the event frames (sound.py, earshot) -> ton.wav, muxed into <name>.mp4
Usage: uv run clip.py
       clips/x/clip.json            (faster-whisper when the clip has narration: word times)
"""
# The steps live in modules of this folder (clip.py is the CLI and re-exports their names for scene.py, intro.py,
# outro.py and recipes):  clip_core (Clip, fig_geometry, Times)  clip_plan (plan: timing passes, keys, camera)
# clip_frames (per-frame stage values)  clip_stage (stage.json, plan.json)  clip_sif (write_sif)
# clip_light (light maps)  clip_tex (slide states, room textures, tags).  Acting styles + gestures: routines.py.
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

import _studio
_studio.use("toon-2d", "film-finish")
import config  # noqa: E402
from clip_core import H_REF, PX_PER_SU, WORLD_W, Clip, Times, fig_geometry  # noqa: E402,F401
from clip_light import LIGHT, RIM, light_map, lights  # noqa: E402,F401
from clip_plan import look_keys, plan  # noqa: E402,F401
from clip_sif import write_sif  # noqa: E402,F401
from clip_stage import tag_cfg  # noqa: E402,F401
from clip_tex import accent_color, dashed_outline, font, rest_mask, room_textures, textures  # noqa: E402,F401

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"


# ----------------------------------------------------------------- render + finish
def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], **kw)
    if r.returncode:
        raise SystemExit(f"failed: {' '.join(str(c) for c in cmd[:3])} ...")


def synfig(C, jobs):
    from render import render_sif
    for f in C.p["figures"]:
        n = f["name"]
        t0 = time.time()
        px = int(fig_geometry(C, n)["px"])          # pass the size: synfig_parallel defaults to 1280x720 (stretches)
        _, cnt = render_sif(C.dir / f"{n}.sif", C.dir / "frames" / n, width=px, height=px, jobs=jobs)
        print(f"  synfig {n}: {cnt} frames in {time.time() - t0:.0f} s")


def three(C):
    page = C.dir / "stage25d.html"
    shutil.copy(ASSETS / "stage25d.html", page)
    run([sys.executable, _studio.skill_dir("toon-2d") / "scripts" / "render_multiplane.py", C.dir / "stage.json",
         "--page", "/stage25d.html", "--contact", "none"])


def final(C):
    from render import contact_sheet
    name = C.dir.name
    raw = C.dir / "stage.mp4"
    out = C.dir / f"{name}.mp4"
    look = C.p.get("look", "standard")
    if look and look != "none":
        run([sys.executable, _studio.skill_dir("film-finish") / "scripts" / "apply_look.py", raw, "-o", out,
             "--look", look])
    else:
        shutil.copy(raw, out)
    ff = config.need("ffmpeg")
    end = C.p["end"]
    run([ff, "-y", "-v", "error", "-i", out, "-vf", "select=eq(n\\,0)", "-frames:v", "1", C.dir / "first.png"])
    run([ff, "-y", "-v", "error", "-sseof", "-0.2", "-i", out, "-update", "1", "-q:v", "1", C.dir / "last.png"])
    frames = sorted({0, 22, 40} | {int(x) for x in np.linspace(0, end, 9)})
    pattern = str(C.dir / "frames_3d" / "mp_%04d.png")
    contact_sheet(pattern, C.dir / "contact.png", [f for f in frames if f <= end][:12])
    # clean in/out: first frame of the 3D render vs. the slide as shown in the presentation
    sl = Image.open(C.deck_file.parent / C.slide["clean"]).convert("RGB").resize(C.size, Image.LANCZOS)
    f0 = Image.open(C.dir / "frames_3d" / "mp_0000.png").convert("RGB")
    fl = Image.open(C.dir / "frames_3d" / f"mp_{end:04d}.png").convert("RGB")
    d0 = np.abs(np.asarray(f0, np.int16) - np.asarray(sl, np.int16)).mean()
    dl = np.abs(np.asarray(fl, np.int16) - np.asarray(f0, np.int16)).mean()
    check = {"first_vs_slide": round(float(d0), 3), "last_vs_first": round(float(dl), 3), "frames": end + 1,
             "size": list(C.size), "seconds": round((end + 1) / C.fps, 2)}
    (C.dir / "check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
    print(f"-> {out}  ({check})")


def sound_step(C):
    if C.p.get("sound", True):
        import sound
        T = Times(C)              # event-anchored cues need the figures' events of the plan step
        T.events = {n: e for n, e in json.loads((C.dir / "plan.json").read_text(encoding="utf-8"))["events"]
                    .items() if not n.startswith("_")}
        sound.mux(C.dir / f"{C.dir.name}.mp4", sound.make(C.dir, C.p, T))


STEPS = ["plan", "synfig", "light", "tex", "3d", "final", "sound"]


def run_step(C, s, jobs):
    {"plan": plan, "synfig": lambda c: synfig(c, jobs), "light": lights, "tex": textures, "3d": three,
     "final": final, "sound": sound_step}[s](C)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--only", choices=STEPS)
    ap.add_argument("--from", dest="start", choices=STEPS, default="plan")
    ap.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 8) // 2))
    a = ap.parse_args()
    import project_check
    project_check.require(a.clip, skill="animated-powerpoint")   # clip.json validated before the first step
    C = Clip(a.clip)
    steps = STEPS
    todo = [a.only] if a.only else steps[steps.index(a.start):]
    t0 = time.time()
    for s in todo:
        run_step(C, s, a.jobs)
    print(f"  done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    sys.exit(main())
