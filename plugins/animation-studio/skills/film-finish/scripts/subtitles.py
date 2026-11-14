# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Subtitle files on FILM time: film.srt + film.vtt (and an optional burned-in copy of the film).

  uv run subtitles.py --project .                     song project (analysis/song_sheet.json lines,
                                                                          film time = song time - first section start)
  uv run subtitles.py --dialogue analysis/dialogue.json [--names]    talking-character dialogue
  uv run subtitles.py --cut film_shots.json           shots of a cut.py film with "subtitles"
  ... [-o film] [--offset 0] [--max-chars 42] [--drop-calls] [--names] [--burn film.mp4 [--burn-out x.mp4]]

Sources:
  --project   a song project: the sung lines of analysis/song_sheet.json, only those inside the film (the sections);
              music videos built with build.py film start at the first section, so that start is subtracted.
  --dialogue  analysis/dialogue.json (talking-character: lines with speaker, times, words) or any song_sheet.json.
  --cut       <out>_shots.json written by cut.py: every shot with "subtitles" (a dialogue.json / song_sheet.json of the
              clip) is mapped through its place in the cut (in point, start, transitions) and clipped to the shot.
Rules (common subtitle practice): at most 2 lines of --max-chars (42) characters, balanced line breaks; a line that
is too long is split at word times (when the source has words) into several cues; each cue stays at least 1.0 s and
long enough to read (17 characters/s) but at most 6 s and never runs into the next cue (gap 0.08 s - call-and-response
lines that overlap in the song are shortened, not stacked). --drop-calls removes bracketed backing calls such as
"(Prompts!)"; --names puts the speaker in front ("Tim: ...", VTT gets <v Tim> voice tags).
--burn film.mp4 burns the SRT into a copy (<film>_subtitled.mp4, libass via ffmpeg's subtitles filter, audio copied):
the soft .srt/.vtt files are the main output - players and platforms switch them on and off; burn in only for
platforms without subtitle upload. overlays.py (lyrics: true) is the animated in-picture alternative.
Python:  import subtitles; cues = subtitles.make_cues(entries); subtitles.write(cues, "film")   # film.srt + film.vtt
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")

GAP, MIN_DUR, MAX_DUR, CPS = 0.08, 1.0, 6.0, 17.0


# ------------------------------------------------------------------ sources -> entries [{t, end, text, who, words}]

def entries_from_file(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    lines = d.get("lines", [])
    words = d.get("words", [])
    out = []
    for i, l in enumerate(lines):
        ws = l.get("words")
        if ws is None:
            ws = [w for w in words if w.get("line") == l.get("line", i)]
        out.append({"t": float(l["t"]), "end": float(l["end"]), "text": l.get("text", ""), "who": l.get("who"),
                    "words": [{"word": w["word"], "t": float(w["t"]), "end": float(w["end"])} for w in ws]})
    return out


def shift(entries, dt, lo=None, hi=None):
    """Move entries by dt seconds and clip them to [lo, hi) (film time)."""
    out = []
    for e in entries:
        t, end = e["t"] + dt, e["end"] + dt
        ws = [{**w, "t": w["t"] + dt, "end": w["end"] + dt} for w in e["words"]]
        if lo is not None:
            if end <= lo:
                continue
            ws = [w for w in ws if w["end"] > lo]
            t = max(t, lo)
        if hi is not None:
            if t >= hi:
                continue
            ws = [w for w in ws if w["t"] < hi]
            end = min(end, hi)
        out.append({**e, "t": t, "end": end, "words": ws})
    return out


def entries_from_project(folder):
    from song_project import Project
    P = Project(folder)
    secs = sorted(P.sections(), key=lambda s: s["from"])
    t0, t1 = (secs[0]["from"], secs[-1]["to"]) if secs else (0.0, None)
    return shift(entries_from_file(P.analysis / "song_sheet.json"), -t0, 0.0, None if t1 is None else t1 - t0)


def entries_from_cut(shots_json):
    d = json.loads(Path(shots_json).read_text(encoding="utf-8"))
    fps, out = d["fps"], []
    for sh in d["shots"]:
        if not sh.get("subtitles"):
            continue
        dt = (sh["start"] - sh["in"]) / fps                 # source second -> film second
        lo, hi = max(sh["start"], sh["vis_start"]) / fps, min(sh["end"], sh["vis_end"]) / fps
        out += shift(entries_from_file(sh["subtitles"]), dt, lo, hi)
    return out


# ------------------------------------------------------------------ cues

def wrap(text, max_chars=42, max_lines=2):
    """Balanced line breaks: the split point closest to the middle that keeps every line <= max_chars."""
    text = " ".join(text.split())
    if len(text) <= max_chars or max_lines < 2:
        return [text]
    words = text.split(" ")
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        score = max(len(a), len(b)) + (0 if a[-1] in ",.!?;:" else 2)
        if best is None or score < best[0]:
            best = (score, [a, b])
    return best[1]


def split_long(e, max_chars, max_lines):
    """A line longer than the cue can hold -> several entries, split at word times."""
    limit = max_chars * max_lines
    if len(e["text"]) <= limit or not e["words"]:
        return [e]
    parts, cur = [], []
    for w in e["words"]:
        if cur and len(" ".join(x["word"] for x in cur + [w])) > limit:
            parts.append(cur)
            cur = []
        cur.append(w)
    parts.append(cur)
    return [{**e, "t": p[0]["t"] if i else e["t"], "end": p[-1]["end"] if i < len(parts) - 1 else e["end"],
             "text": " ".join(x["word"] for x in p), "words": p} for i, p in enumerate(parts)]


def clean(text, drop_calls=False):
    if drop_calls:
        text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)             # [Chorus] markers never belong on screen
    return " ".join(text.split())


def make_cues(entries, max_chars=42, max_lines=2, drop_calls=False, names=False, offset=0.0):
    es = []
    for e in sorted(entries, key=lambda x: x["t"]):
        txt = clean(e["text"], drop_calls)
        if not txt:
            continue
        es += split_long({**e, "text": txt, "t": e["t"] + offset, "end": e["end"] + offset,
                          "words": [{**w, "t": w["t"] + offset, "end": w["end"] + offset} for w in e["words"]]},
                         max_chars, max_lines)
    cues = []
    for i, e in enumerate(es):
        t = max(0.0, e["t"])
        end = max(e["end"], t + MIN_DUR, t + len(e["text"]) / CPS)
        end = min(end, t + max(MAX_DUR, e["end"] - t))
        if i + 1 < len(es):
            end = min(end, es[i + 1]["t"] - GAP)
        if end - t < 0.3:                                   # squeezed by the next cue: keep it readable a moment
            end = t + 0.3
        who = (e.get("who") or "").strip()
        cues.append({"t": round(t, 3), "end": round(end, 3), "lines": wrap(e["text"], max_chars, max_lines),
                     "who": who.capitalize() if names and who else None})
    return cues


def stamp(t, sep):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def write(cues, prefix):
    """-> prefix.srt and prefix.vtt (UTF-8)."""
    prefix = Path(prefix)
    srt, vtt = [], ["WEBVTT", ""]
    for i, c in enumerate(cues, 1):
        lines = list(c["lines"])
        s_lines = [f"{c['who']}: {lines[0]}"] + lines[1:] if c.get("who") else lines
        v_lines = [f"<v {c['who']}>{lines[0]}"] + lines[1:] if c.get("who") else lines
        srt += [str(i), f"{stamp(c['t'], ',')} --> {stamp(c['end'], ',')}", *s_lines, ""]
        vtt += [f"{stamp(c['t'], '.')} --> {stamp(c['end'], '.')}", *v_lines, ""]
    if prefix.suffix.lower() in (".srt", ".vtt"):          # "film.srt" given as prefix
        prefix = prefix.with_suffix("")
    # append, never with_suffix: a prefix like "pip_v1.5" or "film.de" must keep its dot part
    f_srt, f_vtt = (prefix.with_name(prefix.name + ext) for ext in (".srt", ".vtt"))
    prefix.parent.mkdir(parents=True, exist_ok=True)
    f_srt.write_text("\n".join(srt), encoding="utf-8")
    f_vtt.write_text("\n".join(vtt), encoding="utf-8")
    return f_srt, f_vtt


def write_from_cut(shots_json, prefix, **kw):
    cues = make_cues(entries_from_cut(shots_json), **kw)
    write(cues, prefix)
    return len(cues)


def burn(video, srt, out, style=None):
    """Burn the SRT into a copy of the video (libass). Runs in the SRT's folder: Windows paths in the filter break."""
    from encoding import h264
    from media import ffmpeg
    style = style or ("FontName=Segoe UI,Bold=1,FontSize=17,PrimaryColour=&H00FFFFFF,OutlineColour=&H00142B2B,"
                      "BorderStyle=1,Outline=2,Shadow=0,MarginV=18")
    srt = Path(srt).resolve()
    tmp = srt.parent / "_burn_tmp.srt"
    tmp.write_text(srt.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(Path(video).resolve()), "-vf",
                        f"subtitles={tmp.name}:charenc=UTF-8:force_style='{style}'", *h264(), "-pix_fmt", "yuv420p",
                        "-c:a", "copy", "-movflags", "+faststart", str(Path(out).resolve())], check=True, cwd=srt.parent)
    finally:
        tmp.unlink(missing_ok=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="SRT/VTT subtitles on film time.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--project")
    src.add_argument("--dialogue")
    src.add_argument("--cut")
    ap.add_argument("-o", "--out", help="output prefix (default: <project or source folder>/film)")
    ap.add_argument("--offset", type=float, default=0.0, help="seconds added to every cue (e.g. a title before the film)")
    ap.add_argument("--max-chars", type=int, default=42)
    ap.add_argument("--max-lines", type=int, default=2)
    ap.add_argument("--drop-calls", action="store_true", help="remove bracketed backing calls like (Prompts!)")
    ap.add_argument("--names", action="store_true", help="speaker names in front of each line")
    ap.add_argument("--burn", help="video to burn the subtitles into")
    ap.add_argument("--burn-out")
    ap.add_argument("--style", help="libass force_style for --burn")
    a = ap.parse_args()
    if a.project:
        entries, base = entries_from_project(a.project), Path(a.project)
    elif a.dialogue:
        entries = entries_from_file(a.dialogue)
        base = Path(a.dialogue).resolve().parent
        base = base.parent if base.name == "analysis" else base
    else:
        entries, base = entries_from_cut(a.cut), Path(a.cut).resolve().parent
    cues = make_cues(entries, a.max_chars, a.max_lines, a.drop_calls, a.names, a.offset)
    srt, vtt = write(cues, Path(a.out) if a.out else base / "film")
    print(f"-> {srt} + {vtt.name}: {len(cues)} cues, {cues[0]['t']:.2f}-{cues[-1]['end']:.2f} s" if cues else "no cues")
    if a.burn:
        out = Path(a.burn_out) if a.burn_out else Path(a.burn).with_name(Path(a.burn).stem + "_subtitled.mp4")
        burn(a.burn, srt, out, a.style)
        print(f"-> {out} (burned in)")


if __name__ == "__main__":
    main()
