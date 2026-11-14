"""Put the analysed song into the project's engine (video/): song, lyric lines + sections, timing, hits, held notes.

  uv run --no-project python install_data.py PROJECT [--held analysis/held.json] [--video video]

Reads (all made by analyze_song.py / song-analysis):
  lyrics.txt            sung lines with [Section] headers -> RAW in video/src/lyrics.ts
  analysis/timing.json  per line {"t","e","words","ends"}  -> video/src/timing.json (exactly this format)
  analysis/hits.json    {"hits","big","bpm","offset"}       -> video/src/hits.json, BPM + BEAT_OFFSET in lyrics.ts
  analysis/held.json    held notes (held_notes.py measure)  -> video/src/held.json + TrackName in vocal.ts
  analysis/held_auto.json  held notes picked by analyze_song.py (entries with "auto": true + line/word/vowel) ->
                        merged into video/src/held.json; the template's SungLine stretches them by itself
                        (project.json "held_stretch": false leaves them out; "held_style" -> HELD_STYLE in lyrics.ts)
  song.wav              -> video/public/song.wav;  its length -> SONG_END;  project.json "seed" -> SEED
Sections come from the headers: [Intro] [Verse 1] [Pre-Chorus] [Chorus] [Bridge] [Final Chorus] [Outro]
(mapped to intro|verse1|chorus|verse2|bridge|final|outro; a pre-chorus belongs to the verse before it).
"""
import argparse
import json
import re
import shutil
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import creative  # noqa: E402
from media import duration  # noqa: E402
from song_project import Project  # noqa: E402


def section_of(header, seen_verse):
    h = header.lower()
    if "intro" in h:
        return "intro"
    if "outro" in h or "end" in h:
        return "outro"
    if "final" in h or "last" in h:
        return "final"
    if "bridge" in h or "breakdown" in h or "spoken" in h:
        return "bridge"
    if "pre" in h and "chorus" in h:
        return "verse1" if seen_verse <= 1 else "verse2"
    if "chorus" in h or "refrain" in h or "hook" in h or "drop" in h:
        return "chorus"
    return "verse1" if seen_verse <= 1 else "verse2"


def lyric_rows(path):
    rows, sec, verses = [], "intro", 0
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("("):
            continue
        if re.match(r"^\[.*\]$", line):
            if "verse" in line.lower():
                verses += 1
            sec = section_of(line, verses)
            continue
        rows.append((sec, " ".join(line.split())))
    return rows


def sub(text, pattern, repl, what, required=True):
    new, n = re.subn(pattern, lambda m: repl, text, flags=re.S)
    if not n:
        if required:
            raise SystemExit(f"engine file does not contain {what} - was it rewritten by hand?")
        print(f"note: {what} not found in the engine - left as it is (an engine that does not use it)")
    return new


def main():
    ap = argparse.ArgumentParser(description="Install the song analysis into the lyric-video engine.")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--held", help="held.json (default: analysis/held.json if it exists)")
    ap.add_argument("--video", help="engine folder (default: project.json 'video' or video/)")
    a = ap.parse_args()
    P = Project(a.project)
    video = P.dir / (a.video or P.get("video", "video"))
    src, pub = video / "src", video / "public"
    pub.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(P.song, pub / "song.wav")
    rows = lyric_rows(P.path(P.get("lyrics", "lyrics.txt")))
    timing = json.loads((P.analysis / "timing.json").read_text(encoding="utf-8"))
    if len(timing) != len(rows):
        raise SystemExit(f"timing has {len(timing)} lines, lyrics.txt {len(rows)} - run analyze_song.py --redo after "
                         f"editing the lyrics")
    for (s, text), L in zip(rows, timing):
        if len(L["words"]) != len(text.split(" ")):
            raise SystemExit(f"word count differs for '{text}': {len(L['words'])} times")
    h = json.loads((P.analysis / "hits.json").read_text(encoding="utf-8"))
    song_end = duration(pub / "song.wav")

    ts = (src / "lyrics.ts").read_text(encoding="utf-8")
    body = ",\n".join(f"  [{json.dumps(s)}, {json.dumps(t, ensure_ascii=False)}]" for s, t in rows)
    ts = sub(ts, r"const RAW: \[SectionId, string\]\[\] = \[.*?\n\];", "const RAW: [SectionId, string][] = [\n" + body + ",\n];",
             "const RAW")
    ts = sub(ts, r"export const SONG_END = [\d.]+;", f"export const SONG_END = {song_end:.2f};", "SONG_END")
    # optional: older engines (pop-up, rock stage) detect the beat themselves and have no BPM / held notes
    ts = sub(ts, r"export const BPM = [\d.]+;", f"export const BPM = {h['bpm']};", "BPM", required=False)
    ts = sub(ts, r"export const BEAT_OFFSET = [\d.]+;", f"export const BEAT_OFFSET = {h['offset']};", "BEAT_OFFSET",
             required=False)
    seed = creative.seed(P)
    if re.search(r"export const SEED = \d+;", ts):
        ts = re.sub(r"export const SEED = \d+;", f"export const SEED = {seed};", ts)
    else:
        ts += f"\n// Creative seed of the project (project.json \"seed\")\nexport const SEED = {seed};\n"
    style = P.get("held_style", "vowels")
    if style == "auto":                               # same seed -> same style, new seed -> maybe the other
        style = creative.rng(P, "held_style").choice(["vowels", "stretch"])
    if style not in ("vowels", "stretch"):
        raise SystemExit(f"project.json held_style must be vowels, stretch or auto, not {style!r}")
    # only engines from the current template stretch held notes by themselves (older examples: left as they are)
    ts = re.sub(r"export const HELD_STYLE = '\w+'", f"export const HELD_STYLE = '{style}'", ts)
    (src / "lyrics.ts").write_text(ts, encoding="utf-8")
    (src / "timing.json").write_text(json.dumps(timing, indent=0), encoding="utf-8")
    (src / "hits.json").write_text(json.dumps({"hits": h["hits"], "big": h["big"], "loud": h.get("loud", [])}),
                                   encoding="utf-8")
    held_file = Path(a.held) if a.held else P.analysis / "held.json"
    held = json.loads(held_file.read_text(encoding="utf-8")) if held_file.exists() else {}
    auto_file = P.analysis / "held_auto.json"
    if P.get("held_stretch", True) is not False and auto_file.exists() and not a.held:
        for k, v in json.loads(auto_file.read_text(encoding="utf-8")).items():
            held.setdefault(k, v)
    (src / "held.json").write_text(json.dumps(held), encoding="utf-8")
    names = list(held) or ["none"]
    if (src / "vocal.ts").exists():
        v = (src / "vocal.ts").read_text(encoding="utf-8")
        v = sub(v, r"export type TrackName = [^;]+;", "export type TrackName = " + " | ".join(f"'{n}'" for n in names)
                + ";", "TrackName in vocal.ts (held-note names - check they match held.json)", required=False)
        (src / "vocal.ts").write_text(v, encoding="utf-8")
    elif held:
        print("note: no vocal.ts in the engine - held.json installed but nothing reads it")
    present = sorted({s for s, _ in rows})
    auto = [k for k, v in held.items() if v.get("auto")]
    print(f"installed {len(rows)} lines (sections {present}), song {song_end:.1f} s, {h['bpm']} BPM, "
          f"{len(h['hits'])} hits, held notes {list(held) or '-'} (automatic: {auto or '-'}), seed {seed} -> {video}")


if __name__ == "__main__":
    main()
