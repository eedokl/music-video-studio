"""The bridge from a song to a 3D film (used by film3d.py `song`): a song-analysis project + the film's plan
(song_plan.json) -> timing.json, one vocal slice per lyric line for the lip sync, project.json clips / lines / audio.

song_plan.json (in the film folder, written by `film3d.py song <folder> --draft`, then edited):
  {"song": "song",                              the song-analysis project folder (relative to the film folder)
   "clips": [["c01_intro", 0.0, "the boss announces ..."], ["c02_title", 14.6, "..."]],
                                                the edit: clip name, the song second it starts on, what happens;
                                                every clip runs to the next one, the last to the end of the song
   "who": {"mo": ["4-11", 44], "flo": ["26-33"], "all": ["12-21"]},
                                                who performs which lyric line (numbers and "a-b" ranges)
   "groups": {"all": ["mo", "flo", "bot"]},     names that stand for several figures
   "show": {"El-Ge-Te-Em": "LGTM"},             sung -> written: every text a scene shows (stickers, lyrics) comes
                                                from timing.json and carries the written form
   "fix": {"4:0": 25.25},                       a word's start (line:word -> song second) where the recognition is wrong
   "end": {"70": 199.0}}                        a line's end
Lyric line numbers are those of the song sheet (song_lines.txt lists them with their times).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import config
import derived
from stage_project import FPS

PLAN = "song_plan.json"
TIMING = "timing.json"
GAP = 3.0            # a silence this long inside a line after its first word: the word belongs to the rest
PAD = (0.02, 0.12)   # a vocal slice starts / ends this much before / after its line


def rel(path, base):
    """path relative to the film folder (as written into its files); absolute when it lies on another drive"""
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except ValueError:
        return Path(path).as_posix()


def read_plan(F):
    f = F.dir / PLAN
    if not f.exists():
        sys.exit(f"{f} missing - film3d.py song {F.dir} --draft writes a first one")
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"{f} is not valid JSON: {e}")


def song_dir(F, plan):
    d = (F.dir / plan.get("song", "song")).resolve()
    if not (d / "analysis" / "song_sheet.json").exists():
        sys.exit(f"{d / 'analysis' / 'song_sheet.json'} missing - analyse the song first (song-analysis BLOCK.md: "
                 "new_project.py, analyze.py)")
    return d


def song_audio(d):
    for name in ("song.wav", "song.mp3", "song.flac"):
        if (d / name).exists():
            return d / name
    sys.exit(f"no song.wav in {d}")


def vocal_track(d):
    """the isolated lead voice of the song project (the lip sync and the timing checks need it), else None"""
    for rel in ("analysis/vocals_lead.wav", "analysis/vocals.wav", "stems/vocals.wav"):
        if (d / rel).exists():
            return d / rel
    return None


def numbers(items, key):
    """[4, "6-11"] -> [4, 6, 7, ..., 11]"""
    out = []
    for x in items if isinstance(items, (list, tuple)) else [items]:
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", str(x))
        if not m:
            sys.exit(f'{PLAN} "who" {key}: {x!r} is neither a line number nor a range "a-b"')
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        out += list(range(a, b + 1))
    return out


def shown(text, show):
    for a, b in (show or {}).items():
        text = text.replace(a, b)
    return text


def sheet_lines(sheet, plan=None, notes=None):
    """[{"n", "text", "t", "end", "words": [{"word", "t", "end"}]}] of a song sheet, in sung order, with the plan's
    word fixes and the one repair that needs no ears: a first word that stands alone, seconds before the rest of its
    line (the recognition glued it to the line before), moves in front of the second word."""
    plan, notes = plan or {}, notes if notes is not None else []
    fix = {tuple(int(v) for v in k.split(":")): float(t) for k, t in (plan.get("fix") or {}).items()}
    end = {int(k): float(t) for k, t in (plan.get("end") or {}).items()}
    words = {}
    for w in sheet["words"]:
        if w.get("line") is not None:
            words.setdefault(w["line"], []).append({"word": w["word"], "t": float(w["t"]), "end": float(w["end"])})
    out = []
    for ln in sheet["lines"]:
        n = ln["line"]
        ws = words.get(n, [])
        if len(ws) > 1 and (n, 0) not in fix and ws[1]["t"] - ws[0]["end"] >= GAP:
            new = round(ws[1]["t"] - min(0.3, max(0.1, ws[0]["end"] - ws[0]["t"])), 3)
            notes.append(f'line {n}: "{ws[0]["word"]}" was heard at {ws[0]["t"]:.2f} s, {ws[1]["t"] - ws[0]["end"]:.1f} s '
                         f'before the rest of the line - moved to {new:.2f} s (set "fix": {{"{n}:0": seconds}} to place it)')
            ws[0].update(t=new, end=ws[1]["t"])
        for i, w in enumerate(ws):
            if (n, i) in fix:
                w["t"] = fix[(n, i)]
                w["end"] = max(w["end"], w["t"] + 0.05)
        t0 = ws[0]["t"] if ws else float(ln["t"])
        t1 = end.get(n, max([float(ln["end"])] + [w["end"] for w in ws]))
        out.append({"n": n, "text": ln["text"], "t": t0, "end": max(t1, t0 + 0.05), "words": ws})
    bad = sorted(k for k in fix if k[0] not in words or k[1] >= len(words[k[0]]))
    if bad:
        sys.exit(f'{PLAN} "fix": no such word {", ".join(f"{a}:{b}" for a, b in bad)} (line:word, both counted from 0)')
    return out


def quiet_starts(vocals, lines):
    """lines whose first word starts while the voice is silent -> [(n, heard start, voiced start or None)]"""
    import numpy as np
    import media
    sr = 16000
    x = media.decode(vocals, sr)
    hop = sr // 50
    e = np.sqrt(np.add.reduceat(x[:len(x) // hop * hop] ** 2, np.arange(0, len(x) // hop * hop, hop)) / hop)
    out = []
    for ln in lines:
        a, b = int(ln["t"] * 50), int(ln["end"] * 50)
        seg = e[a:b]
        if len(seg) < 15 or not ln["words"]:
            continue
        ref = float(np.percentile(seg, 80))
        if ref < 1e-4:                                      # nothing in the vocal track (a line of the backing voices)
            continue
        if float(seg[:12].max()) < 0.15 * ref:              # the first quarter second holds no voice
            loud = np.nonzero(seg >= 0.4 * ref)[0]
            out.append((ln["n"], ln["t"], round(ln["t"] + int(loud[0]) / 50, 2) if len(loud) else None))
    return out


def slug(text, fallback):
    t = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    ws = re.findall(r"[a-z0-9]+", t)[:2]
    return "_".join(ws)[:18] or fallback


def draft(F, song, target=9.0):
    """A first plan: clips of about `target` seconds that start on a downbeat between two lyric lines (always where
    the voice pauses for two seconds), every line sung by the first figure. Returns (plan, lines)."""
    d = (F.dir / song).resolve()
    plan = {"song": rel(d, F.dir)}
    d = song_dir(F, plan)
    sheet = json.loads((d / "analysis" / "song_sheet.json").read_text(encoding="utf-8"))
    notes = []
    lines = sheet_lines(sheet, notes=notes)
    bars = [b["t"] for b in sheet.get("beats", []) if b.get("downbeat")]
    dur = float(sheet["duration"])
    cuts, prev_end = [(0.0, None)], 0.0
    for ln in lines:
        gap = ln["t"] - prev_end
        fit = [b for b in bars if prev_end <= b <= ln["t"] - 0.1]
        cut = fit[-1] if fit else (prev_end + ln["t"]) / 2 if gap > 0 else ln["t"] - 0.05
        length = cut - cuts[-1][0]
        if cut > cuts[-1][0] and (length >= target or (gap >= 2.0 and length >= 4.0)):
            cuts.append((round(cut, 2), ln))
        elif cuts[-1][1] is None and len(cuts) == 1 and ln is lines[0] and ln["t"] < 4.0:
            cuts[0] = (0.0, ln)                              # the song starts with the voice: clip 1 is its first line
        prev_end = max(prev_end, ln["end"])
    if len(cuts) > 1 and dur - cuts[-1][0] < 3.0:
        cuts.pop()
    clips = []
    for i, (t0, ln) in enumerate(cuts, 1):
        name = f"c{i:02d}_" + (slug(ln["text"], "part") if ln else "intro")
        clips.append([name, t0, ln["text"] if ln else "instrumental"])
    cast = list(F.get("cast") or {"mo": "bear"})
    plan.update(clips=clips, who={cast[0]: [f"0-{lines[-1]['n']}"] if lines else []}, groups={"all": cast}, show={},
                fix={}, end={})
    return plan, lines, notes


def lines_text(lines, clips):
    """song_lines.txt: every lyric line with its number, time and clip - what "who" and the clip list are written from"""
    out, k = [], 0
    for ln in lines:
        while k + 1 < len(clips) and clips[k + 1][1] <= ln["t"]:
            k += 1
        out.append(f'{ln["n"]:3d}  {ln["t"]:7.2f}  {clips[k][0]:22s}  {ln["text"]}')
    return "\n".join(out) + "\n"


def scene_frames(f):
    try:
        m = re.search(r"^FRAMES\s*=\s*(\d+)", f.read_text(encoding="utf-8"), re.M)
    except OSError:
        return None
    return int(m.group(1)) if m else None


def apply(F, make_scene):
    """song_plan.json + the song sheet -> timing.json, speech/<id>.wav, project.json (clips, lines, audio), a scene
    module for every new clip (make_scene(name, frames, about)). Returns the notes for the author."""
    plan = read_plan(F)
    d = song_dir(F, plan)
    sheet = json.loads((d / "analysis" / "song_sheet.json").read_text(encoding="utf-8"))
    dur = float(sheet["duration"])
    notes = []
    # ---- the clips
    pc = plan.get("clips") or []
    if not pc:
        sys.exit(f'{PLAN}: "clips" is empty')
    names = [c[0] for c in pc]
    for c in pc:
        if len(c) < 2 or not str(c[0]).isidentifier():
            sys.exit(f'{PLAN} "clips": {c!r} - expected [name, start second, about] with a name of letters, digits, _')
    if len(set(names)) != len(names):
        sys.exit(f'{PLAN} "clips": a clip name is used twice')
    starts = [int(round(float(c[1]) * FPS)) for c in pc] + [int(round(dur * FPS))]
    if starts[0] != 0:
        sys.exit(f'{PLAN} "clips": the first clip must start at 0 (the song lies under the whole film), not {pc[0][1]}')
    if any(b <= a for a, b in zip(starts, starts[1:])):
        sys.exit(f'{PLAN} "clips": the start seconds must rise and lie before the end of the song ({dur:.2f} s)')
    clips = [{"name": c[0], "t0": starts[i] / FPS, "t1": starts[i + 1] / FPS, "frames": starts[i + 1] - starts[i],
              "about": c[2] if len(c) > 2 else ""} for i, c in enumerate(pc)]
    # ---- the lines
    lines = sheet_lines(sheet, plan, notes)
    groups = {k: list(v) for k, v in (plan.get("groups") or {}).items()}
    who = {}
    for name, items in (plan.get("who") or {}).items():
        for n in numbers(items, name):
            if n in who and who[n] != name:
                sys.exit(f'{PLAN} "who": line {n} is given to {who[n]} and to {name}')
            who[n] = name
    known = {ln["n"] for ln in lines}
    if extra := sorted(set(who) - known):
        notes.append(f'"who" names lines the song sheet does not have: {extra}')
    cast = list(F.get("cast") or [])
    default = "all" if "all" in groups else (cast[0] if cast else "all")
    if free := [ln["n"] for ln in lines if ln["n"] not in who]:
        notes.append(f'no performer in "who" for the lines {free} - sung by "{default}"')
    vocals = vocal_track(d)
    if vocals is None:
        notes.append(f"no isolated lead voice in {d.name}/analysis - the lip sync is cut from the whole song (weak: "
                     "the mouths follow the drums). Separate the vocals (song-analysis) and run this again")
    else:
        for n, t, voiced in quiet_starts(vocals, lines):
            notes.append(f"line {n} starts at {t:.2f} s while the voice is silent"
                         + (f' - it is first heard at {voiced:.2f} s: check it and set "fix": {{"{n}:0": {voiced}}}'
                            if voiced else " and stays silent - a line of the backing voices? check its time"))
    src = vocals or song_audio(d)
    src_hash = derived.file_hash(src)
    show = plan.get("show") or {}
    width = max(2, len(str(max(known, default=0))))
    tl, pl = [], []
    for ln in lines:
        n = ln["n"]
        lid = f"l{n:0{width}d}"
        a, b = max(0.0, ln["t"] - PAD[0]), min(dur, ln["end"] + PAD[1])
        wav = F.dir / "speech" / f"{lid}.wav"
        spec = {"src": src_hash, "a": round(a, 3), "b": round(b, 3), "v": 1}
        if not derived.fresh(wav, spec=spec):
            with derived.build(wav, spec=spec) as bld:
                r = subprocess.run([config.need("ffmpeg"), "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}",
                                    "-i", str(src), "-ac", "1", "-ar", "16000", "-f", "wav", str(bld.path)],
                                   capture_output=True, text=True, errors="replace")
                if r.returncode != 0:
                    sys.exit(f"ffmpeg failed on the vocal slice of line {n}: {r.stderr[-400:]}")
        w = who.get(n, default)
        text = shown(ln["text"], show)
        tw = [{"word": shown(x["word"], show), "t": round(x["t"], 3),
               **({"sung": x["word"]} if shown(x["word"], show) != x["word"] else {})} for x in ln["words"]]
        tl.append({"n": n, "id": lid, "who": w, "text": text, **({"sung": ln["text"]} if text != ln["text"] else {}),
                   "t0": round(a, 3), "t1": round(ln["end"], 3), "words": tw})
        pl.append({"id": lid, "who": w, "text": ln["text"], "audio": f"speech/{lid}.wav",
                   "words": [{"word": x["word"], "t": round(max(0.0, x["t"] - a), 3)} for x in ln["words"]]})
    for ln in tl:
        if not any(c["t0"] <= ln["t0"] < c["t1"] for c in clips):
            notes.append(f'line {ln["n"]} ({ln["t0"]:.2f} s) starts in no clip')
    # ---- timing.json (the record marks it as made here: stage_run.py then counts it into every clip's source key)
    old_ids = set()
    tf = F.dir / TIMING
    if tf.exists():
        try:
            old_ids = {x["id"] for x in json.loads(tf.read_text(encoding="utf-8")).get("lines", [])}
        except (ValueError, KeyError, TypeError):
            pass
    timing = {"fps": FPS, "duration": dur, "bpm": sheet.get("tempo_bpm"), "clips": clips,
              "beats": [round(b["t"], 3) for b in sheet.get("beats", [])],
              "bars": [round(b["t"], 3) for b in sheet.get("beats", []) if b.get("downbeat")],
              "accents": [round(x["t"], 3) for x in sheet.get("accents", [])], "groups": groups, "lines": tl}
    derived.write_text(tf, json.dumps(timing, ensure_ascii=False, indent=1))
    derived.record(tf, spec={"made_by": "film3d.py song", "v": 1})
    # ---- project.json: the clips keep their own keys (xfade), the credit clips stay behind the film
    have = {c["name"]: c for c in F.get("clips") or []}
    new = [dict(have.get(c["name"], {}), name=c["name"], frames=c["frames"], about=c["about"]) for c in clips]
    credit = [c for c in F.get("clips") or [] if c.get("part") == "credits" and c["name"] not in names]
    if gone := [n for n, c in have.items() if n not in names and c.get("part") != "credits"]:
        notes.append(f"clips no longer in the plan were taken out of project.json (their scene files stay): {gone}")
    ids = {x["id"] for x in pl}
    F.p["clips"] = new + credit
    F.p["lines"] = pl + [x for x in F.get("lines") or [] if x.get("id") not in ids and x.get("id") not in old_ids]
    F.p["audio"] = rel(song_audio(d), F.dir)
    F.p.pop("sound", None)
    F.save()
    # ---- scene modules
    for c in clips:
        f = F.dir / "scenes" / f"{c['name']}.py"
        if not f.exists():
            make_scene(c["name"], c["frames"], c["about"])
        elif (n := scene_frames(f)) is not None and n != c["frames"]:
            notes.append(f"scenes/{c['name']}.py says FRAMES = {n}, the clip is {c['frames']} frames now - change it "
                         "(what is placed with SG.f() / SG.word() / SG.beats() follows by itself)")
    print(f"{F.dir.name}: {sum(c['frames'] for c in clips)} frames = {dur:.2f} s, {len(clips)} clips, {len(tl)} lyric "
          f"lines -> {TIMING}, speech/, project.json")
    for c in clips:
        ns = [x["n"] for x in tl if c["t0"] <= x["t0"] < c["t1"]]
        print(f'  {c["name"]:22s} {c["t0"]:7.2f} s {c["frames"]:5d} f   lines '
              + (f"{ns[0]}..{ns[-1]}" if ns else "-"))
    return notes
