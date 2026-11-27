# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""A dialogue of two people as LTX-2.5 clips that all start from ONE picture of both (references/dialogue.md).

Single takes per speaker drift apart: other seats, another car, another background. Here every exchange is one clip -
it opens on the two-shot with the first speaker and cuts to the second ("cut"), or stays on the two-shot while they
speak one after the other (no "cut"). Two sections of the film share that clip: each takes its part by the clip's
song_start, so the film plays the clip through and the model's own cut stays where it is.

project.json:
  "dialogue": {
    "image": "ai/master/two_talk.png",            the two-shot every clip starts from (ai-video master_crops.py)
    "set": "Medium shot through the windscreen of a small car that stands still, nothing outside moves.",
    "who": {"oliver": "the 55-year-old man with ..., in the passenger seat on the left",
            "claudia_v2": "the woman with ..., behind the steering wheel"},     identifiers, repeated after a cut
    "off": [[32.9, 34.6]],                        optional: times of a voice nobody in the picture speaks (sat-nav,
                                                  radio, narrator) - left out of the lip-sync audio
    "clips": [{"name": "A", "shots": ["s02", "s03"], "cut": "frontal medium close-up from the chest up",
               "how": {"s02": "turns to the woman beside him and"}},
              {"name": "F", "shots": ["s11"], "image": "ai/master/two_crop.png"}]
  }
A section's speaker is its "who" (the first name of a list), its words are "sing" (or "line").

  uv run dialogue_clips.py <project> plan                       times, frames, prompts and problems - renders nothing
  uv run dialogue_clips.py <project> lips                       only the lip-sync audio without the "off" voice
  uv run dialogue_clips.py <project> render [--only A,B] [--seeds 7,8]      ~5 min per 8 s clip; finished takes are kept
  uv run dialogue_clips.py <project> check                      hard cut or dissolve, where the cut sits, a strip per take
  uv run dialogue_clips.py <project> select A=8 B=7 [--harden]  the takes into selection.json (then render_shots.py, make_film.py)
"""
import argparse
import contextlib
import io
import json
import math
import subprocess
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video")
import cut_check  # noqa: E402
import ltx25  # noqa: E402
import media  # noqa: E402
from song_project import Project  # noqa: E402

LEAD = 0.1                       # the clip starts this long before its first section
SEEDS = (7, 8)
LISTENS = "listens with the mouth closed and looks straight ahead"
_ASCII = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def cap(s):
    return s[:1].upper() + s[1:]


def short(who):
    """'the woman with the black bob, in a green sweater, behind the wheel' -> 'the woman with the black bob'."""
    return who.split(",")[0].strip()


def speaker(s):
    w = s.get("speaker") or s.get("who")
    return w[0] if isinstance(w, list) else w


def words(s):
    """The section's line as the prompt quotes it: no closing full stop, umlauts written out (the model reads ASCII)."""
    t = (s.get("sing") or s.get("line") or "").strip()
    return "" if t.startswith("(") else t.rstrip(".").translate(_ASCII)


def plan(P):
    """-> ([clip dicts ready to render], [problems])."""
    d = P.get("dialogue") or {}
    probs, out = [], []
    for k in ("image", "set", "who", "clips"):
        if not d.get(k):
            probs.append(f'"dialogue" has no "{k}"')
    if probs:
        return out, probs
    say = "says the words" if P.get("delivery") == "speech" else "sings the words"
    sec = {s["name"]: s for s in P.sections()}
    off = [tuple(x) for x in d.get("off") or []]
    for i, c in enumerate(d["clips"]):
        name = str(c.get("name") or i + 1)
        shots = [sec.get(n) for n in c.get("shots") or []]
        if not shots or None in shots:
            probs.append(f"clip {name}: unknown or missing shots {c.get('shots')}")
            continue
        cut = c.get("cut")
        if cut and len(shots) != 2:
            probs.append(f"clip {name}: a cut joins exactly two shots, got {len(shots)}")
            continue
        img = P.path(c.get("image") or d["image"])
        if not img.exists():
            probs.append(f"clip {name}: start image {img.name} missing")
        t0 = max(0.0, round(min(s["from"] for s in shots) - LEAD, 3))
        end = max(s["to"] for s in shots)
        frames = int(math.ceil(((end - t0 + LEAD) * ltx25.FPS) / 8)) * 8 + 1
        if frames > ltx25.MAX_FRAMES:
            probs.append(f"clip {name}: {end - t0:.1f} s needs {frames} frames, at most {ltx25.MAX_FRAMES} "
                         f"({(ltx25.MAX_FRAMES - 1) / ltx25.FPS:.0f} s) - split it or shorten the pause")
        turns = []
        for s in shots:
            w, t = speaker(s), words(s)
            if w not in d["who"]:
                probs.append(f'clip {name}: shot {s["name"]} speaker "{w}" has no entry in "dialogue.who"')
                continue
            if not t:
                probs.append(f'clip {name}: shot {s["name"]} has no words ("sing" / "line")')
            turns.append((s, w, t, (c.get("how") or {}).get(s["name"])))
        if len(turns) != len(shots):
            continue
        start = min(s["from"] for s in shots)
        heard_off = any(a <= start + 0.5 and b > start for a, b in off)   # the clip opens on the off voice
        s1, w1, t1, how1 = turns[0]
        others = [short(v) for k, v in d["who"].items() if k != w1]
        if cut:
            s2, w2, t2, how2 = turns[1]
            listen = ("First everybody sits still with closed mouths and listens to a voice that comes from off screen, "
                      "nobody in the picture speaks. Then ") if heard_off else ""
            opening = (f'{d["set"].strip()} {listen + d["who"][w1] if listen else cap(d["who"][w1])} '
                       f'{how1 or "looks at the other person and"} {say} "{t1}", the '
                       f'lips form every word, not looking at the camera. '
                       + " ".join(f"{cap(o)} {d.get('listens', LISTENS)}." for o in others))
            cuts = [{"framing": cut, "who": d["who"][w2], "place": c.get("place", ""),
                     "action": f'{how2 or "the person looks straight ahead and"} {say} "{t2}", the lips form every word, the same '
                               "place, nothing else changes, static camera"}]
            probs += [f"clip {name}: {e}" for e in ltx25.check_cuts(cuts, sung=False)]
            prompt = ltx25.multishot_prompt(opening, cuts, c.get("ending", "Cinematic photographic 35mm film look."),
                                            audio="The voices continue unchanged across the cut.")
        else:
            parts = [d["set"].strip(), "Static camera, one continuous shot of everybody."]
            first = True
            if heard_off:
                parts.append("First everybody sits still with closed mouths and listens to a voice that comes from off "
                             "screen, nobody in the picture speaks.")
                first = False
            for s, w, t, how in turns:
                rest = "the others keep their mouths closed" if len(d["who"]) > 2 else \
                    f"{short(next(v for k, v in d['who'].items() if k != w))} keeps the mouth closed"
                parts.append(f'{"First" if first else "Then"} {d["who"][w]} {how or "looks at the other person and"} {say} '
                             f'"{t}", the lips form every word, while {rest}.')
                first = False
            parts.append("Nobody looks at the camera.")
            prompt, cuts = " ".join(parts), []
        out.append({"name": name, "shots": [s["name"] for s in shots], "image": img, "t0": t0, "frames": frames,
                    "seconds": round(frames / ltx25.FPS, 2), "prompt": prompt, "cuts": len(cuts),
                    "wav": P.dir / "ai" / "ltx25" / f"dlg_{name}.wav", "change": shots[1]["from"] if cut else None})
    return out, probs


def take(P, clip, seed):
    return P.dir / "ai" / "ltx25" / f"dlg_{clip['name']}_sd{seed}.mp4"


def lips_track(P):
    """The lip-sync audio: analysis/vocals_lead.wav, with the "off" times silenced (-> analysis/vocals_lips.wav)."""
    src = P.analysis / "vocals_lead.wav"
    if not src.exists():
        raise SystemExit("analysis/vocals_lead.wav missing - the voices-only track of the dialogue")
    off = (P.get("dialogue") or {}).get("off") or []
    if not off:
        return src
    dst = P.analysis / "vocals_lips.wav"
    f = ",".join(f"volume=enable='between(t,{a},{b})':volume=0" for a, b in off)
    subprocess.run([media.ffmpeg(), "-y", "-v", "error", "-i", str(src), "-af", f, str(dst)], check=True)
    return dst


def seeds_of(a):
    return [int(x) for x in a.seeds.split(",")] if a.seeds else list(SEEDS)


def cmd_plan(P, a):
    clips, probs = plan(P)
    for c in clips:
        print(f"== {c['name']}  shots {'+'.join(c['shots'])}  from {c['t0']:.2f} s, {c['frames']} frames ({c['seconds']} s), "
              f"{'cut' if c['cuts'] else 'no cut'}, image {c['image'].name}\n{ltx25.clean_positive(c['prompt'])}\n")
    for p in probs:
        print("PROBLEM:", p)
    est = sum(round(295 * c["frames"] / ltx25.MAX_FRAMES) for c in clips) * len(seeds_of(a))
    print(f"{len(clips)} clip(s) x {len(seeds_of(a))} seed(s): about {est // 60} min on the reference machine")
    return 1 if probs else 0


def cmd_render(P, a):
    clips, probs = plan(P)
    if probs:
        raise SystemExit("dialogue problems:\n  " + "\n  ".join(probs))
    only = [x for x in (a.only or "").split(",") if x]
    lips = lips_track(P)
    for seed in seeds_of(a):
        for c in clips:
            out = take(P, c, seed)
            if (only and c["name"] not in only) or out.exists():
                continue
            c["wav"].parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([media.ffmpeg(), "-y", "-v", "error", "-ss", str(c["t0"]), "-t", str(c["frames"] / ltx25.FPS),
                            "-i", str(lips), str(c["wav"])], check=True)
            print(f"== {c['name']} seed {seed}", flush=True)
            ltx25.render(c["image"], c["wav"], c["prompt"], out, c["frames"], seed,
                         meta={"song_start": c["t0"], "dialogue": c["name"], "shots": c["shots"]}, cuts=c["cuts"])
    return 0


def cmd_lips(P, a):
    print("lip-sync audio:", lips_track(P))
    return 0


def cmd_check(P, a):
    clips, _ = plan(P)
    sheets = P.dir / "ai" / "ltx25" / "sheets"
    bad = 0
    for c in clips:
        for f in sorted((P.dir / "ai" / "ltx25").glob(f"dlg_{c['name']}_sd*.mp4")):
            if f.stem.endswith("_hc"):
                continue
            r = cut_check.find(f)
            note = ""
            if c["cuts"] and r["kind"] == "hard":
                at = c["t0"] + r["t"]
                note = f"  cut at {at:.2f} s, the speaker changes at {c['change']:.2f} s"
                if abs(at - c["change"]) > 1.0:
                    note += "  <-- far from the change, look at it"
                    bad += 1
            elif c["cuts"]:
                bad += 1
            elif r["kind"] != "none":
                note = "  <-- this clip should not cut"
                bad += 1
            print(cut_check.line(f, r) + note)
            sheets.mkdir(parents=True, exist_ok=True)
            with contextlib.redirect_stdout(io.StringIO()):          # the sheet's own frame list is noise here
                media.contact_sheet(f, sheets / f"{f.stem}.jpg", cols=8, rows=2, width=384)
    print(f"strips: {sheets}  - look at every take: seats, mouths, what is outside" + (f"  ({bad} to look at first)" if bad else ""))
    return 0


def cmd_select(P, a):
    clips, _ = plan(P)
    by = {c["name"]: c for c in clips}
    f = P.dir / "selection.json"
    sel = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    sel.setdefault("clip", {})
    man = sel.setdefault("manual", {}).setdefault("clip", {})
    for pick in a.picks:
        name, _, seed = pick.partition("=")
        if name not in by or not seed.isdigit():
            raise SystemExit(f"'{pick}': write <clip>=<seed>, clips: {', '.join(by)}")
        src = take(P, by[name], int(seed))
        if not src.exists():
            raise SystemExit(f"{src.name} missing - render it first")
        r = cut_check.find(src)
        if by[name]["cuts"] and r["kind"] == "dissolve":
            if a.harden:
                src, _ = cut_check.harden(src)
                print(f"  {name}: dissolve replaced by a hard cut -> {src.name}")
            else:
                print(f"  {name}: this take DISSOLVES (frames {r['first']}-{r['last']}) - --harden or another seed")
        rel = src.relative_to(P.dir).as_posix()
        for shot in by[name]["shots"]:
            man[shot] = {"file": rel, "lag": 0}
            sel["clip"][shot] = {"file": rel, "lag": 0, "manual": True}
        print(f"  {name}: {'+'.join(by[name]['shots'])} <- {rel}")
    f.write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {f.name}; next: render_shots.py, make_film.py")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("cmd", choices=["plan", "lips", "render", "check", "select"])
    ap.add_argument("picks", nargs="*", help="select: <clip>=<seed> ...")
    ap.add_argument("--only", help="render: clip names, comma-separated")
    ap.add_argument("--seeds", help="seeds, comma-separated (default 7,8)")
    ap.add_argument("--harden", action="store_true", help="select: replace a dissolve by a hard cut (cut_check.py)")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("claudia-music-video")
    raise SystemExit({"plan": cmd_plan, "lips": cmd_lips, "render": cmd_render, "check": cmd_check, "select": cmd_select}[a.cmd](P, a))


if __name__ == "__main__":
    main()
