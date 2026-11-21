# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""The film as a code cut (second way to cut a finished project, next to render_shots.py + make_film.py):
the picked takes and stills stay as they are, the cut is written as data on the beat grid, and lyrics, labels,
tickers and cards are drawn in code frame by frame (film-finish code_cut.py). B-roll and unsung shots are their
picked still, moved in code - B-roll clips are not needed for this cut.

Reads project.json (sections = shots, "pace", "code_layer"), selection.json and the song sheet; writes
  <work>/edit.json song.json clips.json frames/ stills/     (work = <project>/code_cut)
  <project>/film_code_v01.mp4, film_code_v02.mp4 ...           (never overwritten) + film_code_vNN_sheet.jpg

Usage: uv run code_film.py [<project>] [--pace calm|medium|fast] [--plan-only] [--from K --to K] [--work DIR] [--no-masks]

Pace (project.json "pace" or --pace, default calm): how long a picture holds.
  calm    a sung take runs through its whole shot; stills hold up to 8 beats; beat pulse halved
  medium  takes get one jump-in on a word onset (shots of 4 beats and more); stills change every 3 beats
  fast    jump-ins from 3 beats, a one-beat reframe in long takes; stills every 2 beats, every beat in a chorus
Per shot, project.json sections[]."code" overrides: {"pattern": "push|jump|cut", "beats": 2, "tag": "TEXT",
"tag_at": [x, y], "cam": {...}, "label": "tracker text", "lyric_top": true, "overlays": [...]}.
"code_layer" (all optional) is described in film-finish references/code-cut.md: worlds per look (grade, accent,
tracker, dust), accents per line, chrome (meter, clock, label, bars, frames), ticker file, overlays anchored to words,
"dust", "iris".

Overlays (in "code_layer" or in a shot's "code") are written with anchors instead of frame numbers:
  "at" / "until": {"line": i, "word": j} | {"line": i, "end": true} | {"t": s} | {"shot": "s05"[, "end": true]} | {"k": n},
  or "len": frames. In a shot's "code" the shot's start and end are the defaults.
  Without "until" and "len" a text piece stands as long as it takes to read it (stamp 2 s, quote 5 s, title 1.5 s,
  lower third 2 s) - also across the cut when the shot is shorter.
  Inside a piece: list items "at" and "strike_at", check words "at", flip "flip_at".
  "side": "left" | "right" instead of x: beside the face (sung takes are framed with the face in the middle).
Takes that carry dust or an overlay with "behind": true get their masks from ai-video near_masks.py (GPU; --no-masks
skips it, then dust is left out and those overlays lie in front).
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video", "film-finish")
import clips  # noqa: E402
import code_cut  # noqa: E402
import mouth  # noqa: E402
from cvio import video_capture  # noqa: E402
from media import duration, ffmpeg  # noqa: E402
from song_project import Project  # noqa: E402

PACES = {"calm": dict(still_beats=8, chorus_beats=4, jump_from=None, cut_from=None, pulse=0.5),
         "medium": dict(still_beats=3, chorus_beats=2, jump_from=4, cut_from=None, pulse=0.75),
         "fast": dict(still_beats=2, chorus_beats=1, jump_from=3, cut_from=6, pulse=1.0)}
CAMS = [dict(z=[1.0, 1.08]), dict(z=[1.22, 1.1], ease="out"),
        dict(z=[1.12, 1.12], c=[0.42, 0.5], c1=[0.58, 0.5], ease="linear"), dict(z=[1.06, 1.16], c=[0.55, 0.45]),
        dict(z=[1.3, 1.14], ease="out"), dict(z=[1.14, 1.14], c=[0.6, 0.48], c1=[0.44, 0.48], ease="linear")]


def faces(video, fps):
    """Face box [x, y, w, h] (0..1) per frame, lightly smoothed; None where no face is found."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=mouth.landmarker_model()),
                                        running_mode=vision.RunningMode.VIDEO, num_faces=1)
    out, i = [], 0
    with vision.FaceLandmarker.create_from_options(opts) as lm:
        cap = video_capture(video)
        while True:
            ok, f = cap.read()
            if not ok:
                break
            r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)),
                                    int(i * 1000 / fps))
            if r.face_landmarks:
                xs = [p.x for p in r.face_landmarks[0]]
                ys = [p.y for p in r.face_landmarks[0]]
                out.append([min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)])
            else:
                out.append(None)
            i += 1
    arr = np.array([b if b else [np.nan] * 4 for b in out], float)
    for c in range(4):
        col = arr[:, c]
        ok = ~np.isnan(col)
        if ok.sum() > 5:
            col[ok] = np.convolve(np.pad(col[ok], 2, mode="edge"), np.ones(5) / 5, mode="valid")
    return [None if np.isnan(r[0]) else [round(float(x), 4) for x in r] for r in arr]


def prepare_clip(P, work, name, c):
    """Numbered JPGs + placement data of one picked clip. Cached by the clip file's time stamp."""
    src = P.path(c["file"])
    meta = clips.read_meta(src)
    fd = work / "frames" / name
    stamp = work / "frames" / f"{name}.json"
    key = dict(file=str(c["file"]), mtime=src.stat().st_mtime, lag=c.get("lag", 0))
    if stamp.exists():
        old = json.loads(stamp.read_text(encoding="utf-8"))
        if old.get("key") == key and fd.is_dir():
            return old["clip"]
    shutil.rmtree(fd, ignore_errors=True)
    shutil.rmtree(work / "masks" / name, ignore_errors=True)   # masks belong to these frames
    fd.mkdir(parents=True)
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(src), "-q:v", "2", str(fd / "%04d.jpg")], check=True)
    n = len(list(fd.glob("*.jpg")))
    fps = meta["fps"] * meta.get("tempo", 1.0)
    # clips.frame_index folded into the three numbers the page knows: lag moves the start, clip_start the delay
    clip = dict(fps=fps, frames=n, song_start=round(meta["song_start"] - c.get("lag", 0) / 24.0, 4),
                delay_frames=meta.get("delay_frames", 0) - int(meta.get("clip_start", 0)), faces=faces(src, meta["fps"]))
    stamp.write_text(json.dumps(dict(key=key, clip=clip)), encoding="utf-8")
    print(f"  clip {name}: {n} frames, faces in {sum(b is not None for b in clip['faces'])}", flush=True)
    return clip


def card(path, s, size):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, (28, 30, 36))
    d = ImageDraw.Draw(img)
    d.text((60, 60), f"{s['name']}  {s['technique']}  (no material)", fill=(217, 119, 87))
    d.text((60, 100), (s.get("line") or "")[:90], fill=(230, 226, 218))
    img.save(path)


def anchor(a, K, lines, shots, default=None):
    """{"line": i, "word": j} | {"line": i, "end": true} | {"t": seconds} | {"shot": "s05"[, "end": true]} | {"k": frame}"""
    if a is None:
        return default
    if "k" in a:
        return int(a["k"])
    if "t" in a:
        return K(a["t"])
    if "shot" in a:
        s = next(x for x in shots if x["id"] == a["shot"])
        return s["k1"] if a.get("end") else s["k0"]
    ln = next(x for x in lines if x["i"] == a["line"])
    if a.get("end"):
        return ln["k1"]
    w = ln["words"][a.get("word", 0)]
    return w["k1"] if a.get("word_end") else w["k0"]


READ_S = code_cut.READ_S                                     # shortest time a text piece can be read in
RIGHT_X = {"stamp": 800, "flip": 1040, "list": 812, "counter": 972, "check": 880, "typer": 612, "board": 672}
LEFT_X = {"stamp": 60, "flip": 60, "list": 48, "counter": 48, "check": 96, "typer": 48, "board": 48}


def resolve_overlay(ov, K, lines, shots, frames, fps, shot=None):
    """One overlay written with anchors -> the edit.json form with frame numbers (see the module doc)."""
    ov = dict(ov)
    d0, d1 = (shot["k0"], shot["k1"]) if shot else (0, frames)
    ov["k0"] = anchor(ov.pop("at", None), K, lines, shots, d0)
    if "len" in ov:
        ov["k1"] = ov["k0"] + ov.pop("len")
    elif "until" in ov:
        ov["k1"] = anchor(ov.pop("until"), K, lines, shots, d1)
    else:
        need = READ_S.get(ov.get("type"))
        stand = ov["k0"] + int(round(need * fps)) if need else d1
        ov["k1"] = max(d1, stand) if shot else stand
    ov["k1"] = min(max(ov["k1"], ov["k0"] + 1), frames)
    for it in ov.get("items", []) + ov.get("words", []) + [x for x in ov.get("lines", []) if isinstance(x, dict)]:
        if "at" in it or "k" not in it:
            it["k"] = anchor(it.pop("at", None), K, lines, shots, ov["k0"])
        if "strike_at" in it:
            it["strike"] = anchor(it.pop("strike_at"), K, lines, shots, ov["k0"])
    if ov.get("type") == "flip" and ("flip_at" in ov or "k" not in ov):
        ov["k"] = anchor(ov.pop("flip_at", None), K, lines, shots, (ov["k0"] + ov["k1"]) // 2)
    side = ov.pop("side", None)
    if side and "x" not in ov and ov.get("type") in RIGHT_X:
        ov["x"] = (RIGHT_X if side == "right" else LEFT_X)[ov["type"]]
    return ov


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--pace", choices=list(PACES))
    ap.add_argument("--plan-only", action="store_true", help="write the work folder and check it, render nothing")
    ap.add_argument("--from", dest="k0", type=int, help="re-render from this frame (the film is rebuilt from all frames)")
    ap.add_argument("--to", dest="k1", type=int)
    ap.add_argument("--work", help="work folder (default <project>/code_cut)")
    ap.add_argument("--out", help="film file (default <project>/film_code_vNN.mp4, next free number)")
    ap.add_argument("--no-masks", action="store_true", help="do not make near masks (dust is left out, 'behind' pieces lie in front)")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("claudia-music-video")
    secs = P.sections()
    if not secs:
        raise SystemExit("project.json has no shots - run plan.py first")
    pace_name = a.pace or P.get("pace") or "calm"
    pace = PACES[pace_name]
    layer = P.get("code_layer") or {}
    work = Path(a.work).resolve() if a.work else P.dir / "code_cut"
    (work / "stills").mkdir(parents=True, exist_ok=True)
    (work / "frames").mkdir(exist_ok=True)
    sheet = P.sheet()
    sel = json.loads((P.dir / "selection.json").read_text(encoding="utf-8")) if (P.dir / "selection.json").exists() else {}
    fps = P.fps
    t0 = min(float(s["from"]) for s in secs)
    t1 = min(max(float(s["to"]) for s in secs), duration(P.song))
    K = lambda t: int(round((float(t) - t0) * fps))          # noqa: E731  song seconds -> film frame
    frames = K(t1)

    # ---- song.json: beat grid, kick per beat, lines with words
    acc_t = {round(x["t"], 2): x.get("strength", 0) for x in sheet.get("accents", [])}
    top = max(acc_t.values(), default=0) or 1.0
    beats = [b for b in sheet.get("beats", []) if t0 <= b["t"] <= t1]
    lines = []
    for ln in sheet.get("lines", []):
        if not (t0 <= ln["t"] < t1):
            continue
        ws = [w for w in sheet.get("words", []) if w.get("line") == ln["line"]]
        lines.append(dict(i=ln["line"], text=ln["text"], k0=K(ln["t"]), k1=K(ln["end"]),
                          words=[dict(w=w["word"], k0=K(w["t"]), k1=K(w["end"])) for w in ws]))
    lines = [ln for ln in lines if ln["words"]]
    song = dict(t0=t0, fps=fps, frames=frames, beats_k=[K(b["t"]) for b in beats],
                kick=[round(min(1.0, (acc_t.get(round(b["t"], 2), 0) / top) * 1.4 if acc_t else float(b.get("downbeat", False))), 2)
                      for b in beats], lines=lines)
    (work / "song.json").write_text(json.dumps(song, ensure_ascii=False), encoding="utf-8")
    beat_k = sorted(set(song["beats_k"]))
    kick = dict(zip(song["beats_k"], song["kick"]))
    bf = float(np.median(np.diff(beat_k))) if len(beat_k) > 2 else fps / 2
    onsets = sorted({w["k0"] for ln in lines for w in ln["words"]})

    # ---- material: picked clips as frames, picked stills
    cl, free = {}, set()
    print(f"code cut at pace {pace_name}: {len(secs)} shots, {frames} frames at {fps} fps -> {work}")
    shots = []
    for n, s in enumerate(secs):
        name = s["name"]
        k0, k1 = K(s["from"]), min(K(s["to"]), frames)
        if k1 <= k0:
            continue
        free |= {k0}                                         # the shot plan's own cuts are accepted as given
        o = s.get("code") or {}
        chorus = "chorus" in (s.get("marker") or "").lower()
        c = (sel.get("clip") or {}).get(name)
        take = bool(c and not c.get("still") and c.get("file") and P.path(c["file"]).exists()
                    and s["technique"] != "broll")
        grp = "broll" if s["technique"] == "broll" else "start"
        img = (sel.get(grp) or {}).get(name)
        still = None
        if img and P.path(img).exists():
            still = f"stills/{name}{Path(img).suffix}"
            if not (work / still).exists() or (work / still).stat().st_mtime < P.path(img).stat().st_mtime:
                shutil.copy(P.path(img), work / still)
        idea = s.get("idea") or s.get("line") or name
        parts = []
        if take:
            cl[name] = prepare_clip(P, work, name, c)
            cc = cl[name]
            a0 = int(np.ceil((cc["song_start"] - t0) * fps))
            a1 = int((cc["song_start"] + cc["frames"] / cc["fps"] - t0) * fps)
            ka, kb = k0, k1
            if a0 - k0 > 3 and still:                         # the clip starts later than the shot: its start image first
                ka = min(k1 - 6, a0)
                free.add(ka)
                parts.append(dict(k0=k0, k1=ka, kind="still", src=still, cam=dict(z=[1.0, 1.02]),
                                  why="start image until the take begins"))
            hold = kb > a1 + 3
            n_beats = (kb - ka) / bf
            pat = o.get("pattern") or ("cut" if pace["cut_from"] and n_beats >= pace["cut_from"] and n % 2 else
                                       "jump" if pace["jump_from"] and n_beats >= pace["jump_from"] else "push")
            base = dict(kind="take", src=name)
            for key in ("label", "lyric_top"):
                if key in o:
                    base[key] = o[key]
            if hold:
                base["hold"] = True                           # the take ends early: its last frame is held (checked as such)
            mid = ka + (kb - ka) * 0.55
            cand = [x for x in onsets if ka + fps * 0.7 <= x <= kb - fps * 0.5] or \
                   [x for x in beat_k if ka + fps * 0.7 <= x <= kb - fps * 0.5]
            if pat == "push" or not cand:
                parts.append(dict(base, k0=ka, k1=kb, cam=o.get("cam") or dict(z=[1.0, 1.06]),
                                  why=f"{idea} [sung take, held {n_beats:.1f} beats, slow push]"))
            elif pat == "cut" and [x for x in beat_k if ka + 2 * bf <= x <= kb - 2 * bf]:
                bs = [x for x in beat_k if ka + 2 * bf <= x <= kb - 2 * bf]
                ca = min(bs, key=lambda x: (kick.get(x, 0) <= 0.5, abs(x - mid)))
                cb = min([x for x in beat_k if x > ca], default=kb)
                parts += [dict(base, k0=ka, k1=ca, cam=dict(z=[1.0, 1.05]), why=f"{idea} [sung take]"),
                          dict(base, k0=ca, k1=cb, cam=dict(z=[1.3, 1.36]), track=False,
                               why=f"one-beat punch-in on beat {ca}: the same take, much closer"),
                          dict(base, k0=cb, k1=kb, cam=dict(z=[1.1, 1.16]), why="back to her, 10 % closer than before")]
            else:
                j = min(cand, key=lambda x: abs(x - mid))
                word = next((w["w"] for ln in lines for w in ln["words"] if w["k0"] == j), "the beat")
                parts += [dict(base, k0=ka, k1=j, cam=dict(z=[1.0, 1.05]), why=f"{idea} [sung take]"),
                          dict(base, k0=j, k1=kb, cam=dict(z=[1.1, 1.16]),
                               why=f"jump-in on {word.strip(',.!?').upper()} (frame {j}): same take, 10 % closer")]
        else:
            if not still:
                still = f"stills/{name}_card.png"
                card(work / still, s, tuple(P.size))
                print(f"  {name}: no picked image - placeholder card", flush=True)
            nb = o.get("beats") or (pace["chorus_beats"] if chorus else pace["still_beats"])
            cuts = [k0]
            for x in beat_k:
                if k0 < x < k1 and x - cuts[-1] >= nb * bf - 3 and k1 - x >= max(6, bf - 2):
                    cuts.append(x)
            cuts.append(k1)
            for j in range(len(cuts) - 1):
                p = dict(k0=cuts[j], k1=cuts[j + 1], kind="still", src=still,
                         cam=o.get("cam") or dict(CAMS[(n + j) % len(CAMS)]),
                         why=f"{idea} [{'still, moved in code' if j == 0 else 'the same picture, reframed on the beat'}, "
                             f"{(cuts[j + 1] - cuts[j]) / bf:.1f} beats]")
                if o.get("tag") and j == 0 and cuts[1] - cuts[0] >= fps * 0.8:
                    p["tag"] = dict(text=o["tag"], at=o.get("tag_at", [0.7, 0.32]))
                parts.append(p)
        shots.append(dict(id=name, k0=k0, k1=k1, world=s.get("look") or "default",
                          scene=s.get("scene") or (s.get("marker") or "").upper(), parts=parts))
    # close gaps between shots (rounding, shots outside the song) so the film is tiled
    for i, s in enumerate(shots):
        nxt = shots[i + 1]["k0"] if i + 1 < len(shots) else frames
        if s["k1"] != nxt:
            s["k1"] = s["parts"][-1]["k1"] = nxt
    if shots[0]["k0"] != 0:
        shots[0]["k0"] = shots[0]["parts"][0]["k0"] = 0
    for name, c in cl.items():                                # masks made earlier (near_masks.py) stay valid with their frames
        c = cl[name] = dict(c)
        if len(list((work / "masks" / name).glob("*.png"))) == c["frames"]:
            c["masks"] = True
    (work / "clips.json").write_text(json.dumps(cl), encoding="utf-8")

    # ---- the code layer
    worlds = {}
    for name in {s["world"] for s in shots}:
        w = dict((layer.get("worlds") or {}).get(name) or {})
        w["pulse"] = round(w.get("pulse", 1.0) * pace["pulse"], 2)
        if "tracker" not in w and layer.get("tracker"):
            w["tracker"] = layer["tracker"]
        worlds[name] = w
    accents = {str(k): v for k, v in (layer.get("accents") or {}).items()}
    if layer.get("accents") is None:                           # default: the longest word of each line
        for ln in lines:
            ws = [w["w"].lower() for w in ln["words"]]
            clean = ["".join(ch for ch in w if ch.isalpha()) for w in ws]
            accents[str(lines.index(ln))] = max(clean, key=len) if clean else ""
    chrome = dict(layer.get("chrome") or {})
    chrome.setdefault("label", (P.get("ai_label") or "AI-GENERATED").upper()[:110])
    for key in ("meter", "clock"):
        if key in chrome:
            m = chrome[key] = dict(chrome[key])
            if key == "meter":
                m["k0"], m["k1"] = anchor(m.pop("from", None), K, lines, shots, 0), anchor(m.pop("until", None), K, lines, shots, frames)
            else:
                m["k_end"] = anchor(m.pop("until", None), K, lines, shots, frames)
    overlays = [resolve_overlay(json.loads(json.dumps(ov)), K, lines, shots, frames, fps) for ov in layer.get("overlays") or []]
    by_id = {s["id"]: s for s in shots}
    for s in secs:                                            # overlays written at their shot: they move with the shot
        if s["name"] in by_id:
            overlays += [resolve_overlay(json.loads(json.dumps(ov)), K, lines, shots, frames, fps, by_id[s["name"]])
                         for ov in (s.get("code") or {}).get("overlays") or []]
    overlays.sort(key=lambda o: o["k0"])
    edit = dict(fps=fps, frames=frames, size=list(P.size), pace=pace_name, worlds=worlds, accents=accents, chrome=chrome,
                fade_in=round(fps * 0.4), fade_out=round(fps * 1.5), free_cuts=sorted(free), overlays=overlays, shots=shots)
    if layer.get("dust"):
        edit["dust"] = layer["dust"]
    if layer.get("iris"):                                     # iris out, by default over the last 1.5 s of the film
        ir = dict(layer["iris"])
        ir["k1"] = anchor(ir.pop("until", None), K, lines, shots, frames)
        ir["k0"] = anchor(ir.pop("at", None), K, lines, shots, max(0, ir["k1"] - round(fps * 1.5)))
        edit["iris"] = ir
        if ir["k1"] >= frames - 1:
            edit["fade_out"] = 0                              # the iris ends in black already
    if layer.get("ticker"):
        shutil.copy(P.path(layer["ticker"]), work / "ticker.json")
        edit["ticker"] = "ticker.json"
    (work / "edit.json").write_text(json.dumps(edit, indent=1, ensure_ascii=False), encoding="utf-8")
    if not a.plan_only and not a.no_masks:                    # pieces behind people need the takes' near masks
        import near_masks
        todo = [t for t in near_masks.needed(edit) if not cl.get(t, {}).get("masks")]
        if todo:
            print(f"near masks for {len(todo)} take(s): {', '.join(todo)}", flush=True)
            near_masks.run(work, takes=todo)
    if not code_cut.report(work):
        sys.exit(2)
    if a.plan_only:
        return
    v = 1
    while (P.dir / f"film_code_v{v:02d}.mp4").exists():
        v += 1
    out = Path(a.out).resolve() if a.out else P.dir / f"film_code_v{v:02d}.mp4"
    if out.exists():
        raise SystemExit(f"{out.name} exists - never overwrite a render, pick the next version name")
    if not code_cut.render_frames(work, a.k0 or 0, a.k1 or frames):
        sys.exit(1)
    code_cut.build(work, P.song, out)
    code_cut.sheet(work, out.with_name(out.stem + "_sheet.jpg"), [round(frames * (i + 0.5) / 9) for i in range(9)])


if __name__ == "__main__":
    main()
