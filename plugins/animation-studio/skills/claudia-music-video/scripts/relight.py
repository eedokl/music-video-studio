# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""A new Claudia film from a finished one in another light ("Nachtschicht"): same song, same shots, same places and
people - the start images of the finished film re-lit by Qwen-Image-Edit, then new LTX takes on them.

    uv run relight.py <finished project> <new project> --light night|club|dusk|dawn|golden|rain|fog
                      [--looks looks.json] [--text "..." --short "..."] [--variants 2] [--keep s27,s30]
                      [--only s02,s05] [--no-originals] [--name "Title - night"]

What it does (no GPU, a few seconds):
  - copies song.wav, lyrics.txt, analysis/ (word times, vocals - no new analysis), the Demucs instrumental
    (cache/sep/), and every file project.json names (reference images, stems, placed clips)
  - per lipsync / claudia_moving / B-roll shot: the picked start image (selection.json, a hand choice first) is
    copied to ai/relight_src/<shot>.png and the shot gets "relight": {"src", "light", "seeds", "size", "from_shot"} -
    jobs.py turns that into Qwen-Image-Edit jobs "Change only the light and the time of day of this photo: <light>.
    Keep everything else exactly as it is: ..." with the original as the only reference (seeds 11 / 23 as in the
    Nachtschicht test) -> ai/start/<shot>_v1.png, _v2.png (B-roll: ai/broll/)
  - the shot's "set" / "set_short" and a new look "<look>_<light>" carry the light into the LTX prompts
  - the original take of every shot is copied as a kept take <shot>_orig_<...>.mp4 (takes page: "original take",
    never the automatic pick) - the user may keep the old light for a shot; --no-originals leaves them out
  - --keep / --only (the others) / an empty light text in --looks: the shot keeps its original take (no jobs)
  - project.json "relit_from": {project, light, shots: {new shot: {shot, start, clip, lag}}} = the map new take ->
    old shot; the shots keep their names, times and lead-ins, so the new cut lines up with the old one
The canon check is NOT run on relit start images (pick.py takes the first variant, the sheet says "check by eye"):
the original passed it and only the light changes - in the Nachtschicht test faces, the headset, Oliver and the places
stayed. Look at sheet_start.jpg anyway (a strong colour light can hide the streak).

--looks: {"<look of the source film>": ["<light instruction for Qwen>", "<short light sentence for LTX>"]} - one
light per place, as the Nachtschicht brief did (server hall: red club light, office: magenta and cyan ...); looks
not in the file take --light (or --text / --short). An empty instruction keeps that look's shots as they are.
Then:  jobs.py <new> -> night_run.py <new>/jobs.json --phases qwen_edit -> look at sheet_start.jpg / sheet_broll.jpg
       -> night_run.py <new>/jobs.json -> pick.py all -> takes.py --serve -> render_shots.py -> make_film.py
"""
import argparse
import json
import shutil
import struct
import sys
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
from song_project import Project  # noqa: E402
import claudia  # noqa: E402

# name: (instruction for Qwen-Image-Edit, short sentence for the LTX look, what changes)
LIGHTS = {
    "night": ("night, the place lit only by its own lamps, street lights and lit windows, deep blue shadows",
              "night light from lamps and lit windows, deep blue shadows", None),
    "club": ("night, coloured club light in magenta, cyan and violet, a slowly turning mirror ball, light haze in the air",
             "coloured club light, mirror ball and haze at night", None),
    "dusk": ("blue hour just after sunset, a deep blue sky, the first lamps switched on, warm lit windows",
             "blue dusk light after sunset, the first lamps on", None),
    "dawn": ("first light before sunrise, a pale pink and grey sky, soft cool light", "pale first light before dawn", None),
    "golden": ("golden hour, a low warm sun from the side, long soft shadows", "low warm golden-hour sun, long shadows",
               None),
    "rain": ("a grey rainy day, wet glistening surfaces, raindrops in the air, soft diffuse light",
             "grey rainy light, wet glistening surfaces", "the light and the weather"),
    "fog": ("thick fog, soft diffuse light, the background fading into white haze", "soft diffuse light in thick fog",
            "the light and the weather"),
}
STILL = "Photographic 35mm film still, {short}, fine film grain, shallow depth of field."
SEEDS = [11, 23, 37, 51]                      # Nachtschicht: 11 / 23
TAKE_DIRS = ("lipsync", "s2v", "infinitetalk", "humo", "minimax_h3", "ltx25", "moving", "broll")
ACTED = ("lipsync", "claudia_moving")


def image_size(path):
    """(w, h) of a PNG / JPEG without an image library, None if unknown."""
    b = Path(path).read_bytes()[:65536]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            m, ln = b[i + 1], struct.unpack(">H", b[i + 2:i + 4])[0]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            i += 2 + ln
    return None


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


def rel_files(S, value, out):
    """Every relative path string in project.json that names an existing file of the source project."""
    if isinstance(value, dict):
        for v in value.values():
            rel_files(S, v, out)
    elif isinstance(value, list):
        for v in value:
            rel_files(S, v, out)
    elif isinstance(value, str) and 0 < len(value) < 260 and "\n" not in value and not value.startswith("skill:"):
        p = Path(value)
        if not p.is_absolute() and ".." not in p.parts:
            try:
                if (S.dir / p).is_file():
                    out.add(p.as_posix())
            except OSError:
                pass


def picked(sel, group, name):
    return ((sel.get("manual") or {}).get(group) or {}).get(name) or (sel.get(group) or {}).get(name)


def copy_take(S, D, name, entry, note, img):
    """The source film's take of a shot -> <shot>_orig_<rest>.mp4 (+ sidecars) in the new project, marked as kept
    original (takes page: shown, never the automatic pick). Returns its relative path or None."""
    f = S.path(entry["file"])
    if not f.exists():
        return None
    stem = f.stem
    new_stem = f"{name}_orig_{stem[len(name) + 1:] if stem.startswith(name + '_') else stem}"
    folder = D.dir / "ai" / f.parent.name
    folder.mkdir(parents=True, exist_ok=True)
    for side in sorted(f.parent.glob(f"{stem}.*")):
        if side.name.startswith(stem + "."):
            copy(side, folder / (new_stem + side.name[len(stem):]))
    mp = folder / f"{new_stem}.json"
    meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    meta.update(kept="orig", original={"project": str(S.dir), "file": entry["file"], "lag": entry.get("lag", 0),
                                       "note": note})
    if img:
        meta["image"] = str(img.resolve())
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"ai/{f.parent.name}/{new_stem}.mp4"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="the finished project (project.json + selection.json)")
    ap.add_argument("new", help="folder of the new project (must not exist or be empty)")
    ap.add_argument("--light", default="night", help=f"preset ({', '.join(LIGHTS)}) or a name for --text / --short")
    ap.add_argument("--text", help="own light instruction for Qwen (with --short)")
    ap.add_argument("--short", help="own short light sentence for the LTX prompts")
    ap.add_argument("--looks", help="json {source look: [instruction, short]} - one light per place")
    ap.add_argument("--variants", type=int, default=2, help="relit variants per shot (1-4, seeds 11, 23, 37, 51)")
    ap.add_argument("--keep", default="", help="shots that keep their original take (e.g. a black break)")
    ap.add_argument("--only", default="", help="relight only these shots; every other one keeps its original take")
    ap.add_argument("--no-originals", action="store_true", help="do not copy the original takes as kept takes")
    ap.add_argument("--name", help="title of the new project (default: '<source title> - <light>')")
    a = ap.parse_args()

    S = Project(a.source)
    sf = S.dir / "selection.json"
    if not sf.exists():
        raise SystemExit(f"{sf} missing - relight.py starts from a finished (picked) film")
    sel = json.loads(sf.read_text(encoding="utf-8"))
    dst = Path(a.new).resolve()
    if dst == S.dir:
        raise SystemExit("the new project must be another folder")
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"{dst} exists and is not empty - relight.py makes a NEW project")
    light_name = a.light.strip().lower()
    if a.text or a.short:
        if not (a.text and a.short):
            raise SystemExit("--text and --short go together (instruction for the picture, short sentence for LTX)")
        base = (a.text, a.short, None)
    elif light_name in LIGHTS:
        base = LIGHTS[light_name]
    else:
        raise SystemExit(f"--light {a.light}: not a preset ({', '.join(LIGHTS)}) - give --text and --short for it")
    if not light_name.replace("_", "").isalnum():
        raise SystemExit(f"--light {a.light!r}: letters, digits and _ only (it becomes a look name)")
    per_look = {}
    if a.looks:
        per_look = json.loads(Path(a.looks).read_text(encoding="utf-8"))
        bad = [k for k, v in per_look.items() if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v))]
        if bad:
            raise SystemExit(f"--looks: {', '.join(bad)} - each entry is [\"<instruction>\", \"<short sentence>\"]")
    weak = [k for k, v in [(light_name, base[1])] + [(k, v[1]) for k, v in per_look.items() if v[0].strip()]
            if not any(w in v.lower() for w in claudia.LIGHT_WORDS)]
    if weak:                                      # jobs.py would refuse every shot (LTX jumps scenes without one)
        raise SystemExit(f"short light sentence of {', '.join(weak)} names no light: use one of the words "
                         f"{', '.join(claudia.LIGHT_WORDS)} (e.g. \"warm lamp light\")")
    nvar = max(1, min(4, a.variants))
    keep = {x for x in a.keep.split(",") if x}
    only = {x for x in a.only.split(",") if x}
    names = {s["name"] for s in S.sections()}
    unknown = sorted((keep | only) - names)
    if unknown:
        raise SystemExit(f"unknown shot(s): {', '.join(unknown)}")

    D_dir = dst
    D_dir.mkdir(parents=True, exist_ok=True)
    p = json.loads(S.file.read_text(encoding="utf-8"))
    for f in ("song.wav", "lyrics.txt", "analysis"):
        if (S.dir / f).exists():
            copy(S.dir / f, D_dir / f)
    if (S.cache / "sep").exists():                # the Demucs instrumental of the moving clips: no GPU again
        copy(S.cache / "sep", D_dir / "cache" / "sep")
    files = set()
    rel_files(S, {k: v for k, v in p.items() if k != "sections"}, files)
    for s in p.get("sections", []):
        rel_files(S, {k: v for k, v in s.items() if k not in ("start_image", "relight")}, files)
    for f in sorted(files):
        if not (D_dir / f).exists():
            copy(S.dir / f, D_dir / f)
    (D_dir / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    D = Project(D_dir)

    brief = p.setdefault("brief", {})
    looks = brief.setdefault("looks", {})
    new_sel = {"manual": {"start": {}, "broll": {}, "clip": {}}}
    shots_map, relit, kept, fresh, originals = {}, [], [], [], 0
    for s in p.get("sections", []):
        name, tech = s["name"], s["technique"]
        if tech not in ACTED + ("broll",):
            continue                                  # typo / placed: as they are (their files are copied)
        group = "broll" if tech == "broll" else "start"
        src_img = picked(sel, group, name) or s.get("start_image")
        clip = picked(sel, "clip", name)
        clip = clip if isinstance(clip, dict) else None
        look = s.get("look") or brief.get("look") or ""
        text, short = (per_look[look] if look in per_look else base[:2])
        what = None if look in per_look else base[2]
        shots_map[name] = {"shot": name, "start": src_img, "clip": (clip or {}).get("file"),
                           "lag": (clip or {}).get("lag", 0), **({"still": True} if (clip or {}).get("still") else {})}
        img = None
        if src_img and S.path(src_img).exists():
            sp = S.path(src_img)
            img = D_dir / "ai" / "relight_src" / f"{name}{sp.suffix.lower()}"
            copy(sp, img)
        stays = name in keep or (only and name not in only) or not text.strip()
        if stays and img is not None and clip:
            s.pop("start_image", None)
            s["relight"] = {"keep": True, "from_shot": name, "src": img.relative_to(D_dir).as_posix()}
            new_sel["manual"][group][name] = s["relight"]["src"]
            new_sel.setdefault(group, {})[name] = s["relight"]["src"]
            if clip.get("still"):
                new_sel["manual"]["clip"][name] = {"still": True}
            else:
                own = copy_take(S, D, name, clip, "kept, not relit", img)
                if own:
                    new_sel["manual"]["clip"][name] = {"file": own, "lag": clip.get("lag", 0)}
            kept.append(name)
            continue
        # the light goes into the place text and the look (LTX prompts, and fresh start images if any)
        if s.get("set"):
            s["set"] = f"{s['set']}, {text}"
        if s.get("set_short"):
            s["set_short"] = f"{s['set_short']}, {short}"
        if tech == "broll" and s.get("subject"):
            s["subject"] = f"{s['subject']}, {text}"
        new_look = f"{look or 'look'}_{light_name}"
        looks[new_look] = [STILL.format(short=short), short]
        s["look"] = new_look
        if img is None:                               # never picked: made fresh with the canon check as usual
            fresh.append(name)
            continue
        s.pop("start_image", None)
        s["relight"] = {"src": img.relative_to(D_dir).as_posix(), "light": text, "seeds": SEEDS[:nvar],
                        "from_shot": name, **({"what": what} if what else {})}
        size = image_size(img)
        if size:
            s["relight"]["size"] = list(size)
        if clip and clip.get("file") and not a.no_originals:
            originals += bool(copy_take(S, D, name, clip, f"before the relight to {light_name}", img))
        relit.append(name)
    if f"{brief.get('look')}_{light_name}" in looks:
        brief["look"] = f"{brief['look']}_{light_name}"
    p["name"] = a.name or f"{p.get('name') or S.dir.name} - {light_name}"
    p["relit_from"] = {"project": str(S.dir), "light": light_name, "made": time.strftime("%Y-%m-%d"),
                       "shots": shots_map}
    (D_dir / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    new_sel["manual"] = {k: v for k, v in new_sel["manual"].items() if v}
    (D_dir / "selection.json").write_text(json.dumps(new_sel, ensure_ascii=False, indent=1), encoding="utf-8")
    D = Project(D_dir)
    D.check("claudia-music-video")
    print(f"{D_dir}: {len(relit)} shot(s) to relight ({light_name}, {nvar} variant(s) each), {len(kept)} kept with "
          f"the original take, {len(fresh)} without a picked start image (made fresh, canon check as usual), "
          f"{originals} original take(s) on the takes page")
    if kept:
        print("  kept: " + ", ".join(kept))
    if fresh:
        print("  fresh: " + ", ".join(fresh))
    print("No canon check on relit start images (the originals passed it; only the light changes) - look at "
          "sheet_start.jpg / sheet_broll.jpg after the image phase.\n"
          f"Next: jobs.py {D_dir} -> night_run.py {D_dir / 'jobs.json'} --phases qwen_edit -> sheets -> night_run.py "
          "(clips) -> pick.py all -> takes.py --serve -> render_shots.py -> make_film.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
