# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Several people in one place: ONE master picture of all of them, every other start image is a crop of it.

Start images made one by one for each shot do not agree: in a car film the passenger sat behind a steering wheel in one
shot and on the back seat in the next, and the view outside changed. So: make the master picture once (everybody in
their place), cut the singles out of it, and let Qwen-Image-Edit change only mouth and gaze inside a crop - the place,
the seats, the light and what is behind the people stay what the master shows.

project.json:
  "master": {"image": "ai/master/master.png",        the chosen master (make -> look -> use)
             "size": [1280, 704],                     size of the crops (the video model's frame)
             "crops": {"him": "1152:634:0:110", "her": "1152:634:768:190", "two": "1920:1056:0:0"},   w:h:x:y in the master
             "edits": {"him_talk": {"crop": "him", "change": "the man looks to the right at the driver beside him, his "
                                                              "mouth is open in the middle of a word, not smiling."}},
             "variants": 2, "seed": 41, "negative": "..."}

  uv run master_crops.py <project> make "<prompt>" --ref a.jpg --ref b.jpg [--seed 3101] [--variants 3] [--size 1920x1056]
  uv run master_crops.py <project> use ai/master/master_3101_v3.png     the picture you chose becomes "image"
  uv run master_crops.py <project> crops                                -> ai/master/<name>_crop.png
  uv run master_crops.py <project> edits [name ...]                     -> ai/master/<name>_v<k>.png
Use the results as a shot's "start_image" (claudia-music-video) and as "dialogue.image" (dialogue_clips.py).

Rules that held (car sketch, 2026-11): say in the master prompt how many people there are and who sits where as seen in
the picture ("on the right side of the picture, behind the steering wheel"); a reference sheet with several views of one
person needs the sentence "a sheet showing several views of that one person, not several people"; keep the crops'
aspect ratio equal to "size"; an edit sentence names ONE change - mouth and gaze - and nothing about the place.
A start image with an open mouth made LTX-2.3 hold the mouth half open and still in 4 of 7 takes; for a speaking
single prefer lips "parted" over "wide open", or InfiniteTalk for that shot when the background stands still.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import media  # noqa: E402
from song_project import Project  # noqa: E402

KEEP = ("Keep image 1 exactly as it is: the same people, faces, hair, clothes, the same place and everything behind them, "
        "the same framing and light. Change only this: ")
NEG = ("illustration, drawing, cartoon, text, logo, watermark, deformed hands, blurry, another person, hat, cap, glasses, "
       "different place, different background")


def spec(P):
    m = P.get("master") or {}
    m.setdefault("image", "ai/master/master.png")
    m.setdefault("size", [1280, 704])
    return m


def save_spec(P, m):
    P.p["master"] = m
    P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")


def crop_problems(m):
    out = []
    w, h = m["size"]
    for name, c in (m.get("crops") or {}).items():
        try:
            cw, ch, _, _ = (int(x) for x in str(c).split(":"))
        except ValueError:
            out.append(f'crop "{name}": write "w:h:x:y", got {c!r}')
            continue
        if abs(cw / ch - w / h) > 0.02:
            out.append(f'crop "{name}" is {cw}x{ch} ({cw / ch:.3f}) but "size" is {w}x{h} ({w / h:.3f}) - the picture '
                       "would be squeezed")
    for name, e in (m.get("edits") or {}).items():
        if e.get("crop") not in (m.get("crops") or {}):
            out.append(f'edit "{name}": crop "{e.get("crop")}" is not in "crops"')
        if not e.get("change"):
            out.append(f'edit "{name}": no "change"')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("cmd", choices=["make", "use", "crops", "edits"])
    ap.add_argument("args", nargs="*", help="make: the prompt; use: the chosen picture; edits: names (default all)")
    ap.add_argument("--ref", action="append", default=[], help="make: reference image of a person (1-3)")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--variants", type=int)
    ap.add_argument("--size", default="1920x1056", help="make: size of the master picture")
    ap.add_argument("--negative")
    ap.add_argument("--dry-run", action="store_true", help="print what would be made")
    a = ap.parse_args()
    P = Project(a.project)
    P.check()
    m = spec(P)
    folder = P.dir / "ai" / "master"
    probs = crop_problems(m)
    if probs and a.cmd in ("crops", "edits"):
        raise SystemExit("master problems:\n  " + "\n  ".join(probs))
    if a.cmd == "use":
        if len(a.args) != 1 or not P.path(a.args[0]).exists():
            raise SystemExit("use: name one existing picture")
        dst = P.path(m["image"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        if P.path(a.args[0]).resolve() != dst.resolve():
            shutil.copy2(P.path(a.args[0]), dst)
        save_spec(P, m)
        print(f"master = {m['image']}  (next: crops, edits)")
        return
    if a.cmd == "crops":
        src = P.path(m["image"])
        if not src.exists():
            raise SystemExit(f"{m['image']} missing - make the master first, then `use` the one you chose")
        w, h = m["size"]
        for name, c in (m.get("crops") or {}).items():
            out = folder / f"{name}_crop.png"
            if not a.dry_run:
                subprocess.run([media.ffmpeg(), "-y", "-v", "error", "-i", str(src), "-vf",
                                f"crop={c},scale={w}:{h}:flags=lanczos", str(out)], check=True)
            print(f"  {name}: crop {c} -> ai/master/{out.name}")
        return
    import qwen_edit                                  # ComfyUI + GPU lock from here on
    if a.cmd == "make":
        if len(a.args) != 1 or not a.ref:
            raise SystemExit('make: one prompt in quotes and at least one --ref')
        w, h = (int(x) for x in a.size.lower().split("x"))
        seed = a.seed if a.seed is not None else 3101
        for k in range(1, (a.variants or 3) + 1):
            out = folder / f"master_{seed}_v{k}.png"
            print(f"  master seed {seed + k - 1} -> ai/master/{out.name}", flush=True)
            if not a.dry_run:
                qwen_edit.edit([str(P.path(r)) for r in a.ref], a.args[0], out, w, h, seed + k - 1, a.negative or qwen_edit.NEG)
        print("look at them, then: master_crops.py <project> use ai/master/<the one you chose>")
        return
    w, h = m["size"]
    seed = a.seed if a.seed is not None else int(m.get("seed", 41))
    for name, e in (m.get("edits") or {}).items():
        if a.args and name not in a.args:
            continue
        ref = folder / f"{e['crop']}_crop.png"
        if not ref.exists() and not a.dry_run:
            raise SystemExit(f"ai/master/{ref.name} missing - run `crops` first")
        for k in range(1, int(a.variants or m.get("variants", 2)) + 1):
            out = folder / f"{name}_v{k}.png"
            print(f"  {name} v{k}: {e['change'][:70]}", flush=True)
            if not a.dry_run:
                qwen_edit.edit([str(ref)], m.get("keep", KEEP) + e["change"], out, w, h, seed + k - 1,
                               a.negative or m.get("negative") or NEG)


if __name__ == "__main__":
    main()
