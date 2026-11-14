"""Create a cartoon music-video project: folder with song.wav, lyrics.txt, (stems) and project.json.

Usage:
  python new_project.py <folder> --song song.mp3 [--lyrics text.txt] [--lead vocals.wav --backing backing.wav]
         [--from 38.3 --to 58.3] [--lyrics-from "first sung line" --lyrics-to "last sung line"]
         [--language de|en|...] [--name "Title"] [--force]

--from/--to cut an excerpt (song AND stems alike) - good for tests and pilots; the project timeline then starts at
0 = --from. With an excerpt, ALSO trim the lyrics to the sung lines (--lyrics-from/--lyrics-to, matched by the start of
the line text, case-insensitive): Whisper cannot place a whole song's lyrics onto 20 s of audio.
Lyrics: one sung line per row; section markers in square brackets ([Chorus], [Verse 1 - Tim, male lead]) are kept.
The new project.json holds the standard cast (Tim, Lia, Computer) and ONE section over everything.

Re-running on an existing project never replaces song.wav, stems or lyrics.txt silently: if the new files differ, it
stops and lists them. With --force they are replaced and the old analysis/ (word times, voices, Demucs vocals) is moved
to analysis.stale-<time>/ so the next analyze.py run starts fresh. An existing project.json is never overwritten.
"""
import argparse
import filecmp
import json
import shutil
import subprocess
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use('song-analysis')
from media import duration, ffmpeg


def cut(src, dst, start, end):
    cmd = [ffmpeg(), "-y", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if end:
        cmd += ["-t", f"{end - (start or 0):.3f}"]
    subprocess.run(cmd + ["-ac", "2", "-ar", "48000", str(dst)], check=True)


def trim_lyrics(text, first, last):
    """Keep the lines from the one starting with `first` to the one starting with `last` (+ markers in between)."""
    rows = text.splitlines()
    low = [r.strip().lower() for r in rows]
    i0 = next((i for i, r in enumerate(low) if first and r.startswith(first.lower())), 0)
    i1 = next((i for i in range(i0, len(low)) if last and low[i].startswith(last.lower())), len(rows) - 1)
    while i0 > 0 and low[i0 - 1].startswith("["):      # keep the section marker right above the first line
        i0 -= 1
    if i1 < i0:
        raise SystemExit("--lyrics-to comes before --lyrics-from")
    return "\n".join(rows[i0:i1 + 1]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--song", required=True)
    ap.add_argument("--lyrics")
    ap.add_argument("--lead", help="lead-vocal stem (e.g. Suno 'Vocals')")
    ap.add_argument("--backing", help="backing-vocal stem (e.g. Suno 'Backing Vocals')")
    ap.add_argument("--from", dest="start", type=float)
    ap.add_argument("--to", dest="end", type=float)
    ap.add_argument("--lyrics-from")
    ap.add_argument("--lyrics-to")
    ap.add_argument("--language", default="de", help="language of the vocals for Whisper (de, en, ...)")
    ap.add_argument("--name")
    ap.add_argument("--force", action="store_true",
                    help="replace song.wav / stems / lyrics.txt of an existing project when they differ")
    a = ap.parse_args()
    d = Path(a.folder).resolve()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / ".new_project_tmp"            # build everything here first, then compare with what exists
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    try:
        cut(a.song, tmp / "song.wav", a.start, a.end)
        stems = {}
        for k in ("lead", "backing"):
            src = getattr(a, k)
            if src:
                (tmp / "stems").mkdir(exist_ok=True)
                cut(src, tmp / "stems" / f"{k}.wav", a.start, a.end)
                stems[k] = f"stems/{k}.wav"
        warn = ""
        if a.lyrics:
            text = Path(a.lyrics).read_text(encoding="utf-8")
            if a.lyrics_from or a.lyrics_to:
                text = trim_lyrics(text, a.lyrics_from, a.lyrics_to)
            elif a.start or a.end:
                warn = ("\nWARNING: excerpt with the full lyrics - trim lyrics.txt to the sung lines "
                        "(or re-run with --lyrics-from/--lyrics-to), otherwise the word times will be wrong.")
            (tmp / "lyrics.txt").write_text(text, encoding="utf-8")
        new = [f.relative_to(tmp) for f in sorted(tmp.rglob("*")) if f.is_file()]
        changed = [r for r in new if (d / r).exists() and not filecmp.cmp(tmp / r, d / r, shallow=False)]
        if changed and not a.force:
            raise SystemExit(f"{d} already has different " + ", ".join(r.as_posix() for r in changed)
                             + " - not replaced. Re-run with --force to replace them (the old analysis/ is then "
                               "set aside as stale), or use a new folder.")
        for r in new:
            (d / r).parent.mkdir(parents=True, exist_ok=True)
            (tmp / r).replace(d / r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ana = d / "analysis"
    if changed and ana.is_dir() and any(ana.iterdir()):
        stale = d / f"analysis.stale-{time.strftime('%Y%m%d-%H%M%S')}"
        ana.rename(stale)
        print(f"source changed ({', '.join(r.as_posix() for r in changed)}) - old analysis moved to {stale.name}/")
    length = round(duration(d / "song.wav"), 2)
    p = {
        "name": a.name or d.name,
        "fps": 24,
        "source": {"song": Path(a.song).name, "path": str(Path(a.song).resolve()).replace("\\", "/"), "from": a.start or 0.0},
        "lyrics": "lyrics.txt" if a.lyrics else None,
        "stems": stems,
        "language": a.language,
        "figures": {
            "tim": {"svg": "skill:characters/assets/figures/tim.svg", "voice": "male", "size": 1.0},
            "lia": {"svg": "skill:characters/assets/figures/lia.svg", "voice": "female", "size": 1.0, "entrance": "flicker"},
            "computer": {"kind": "screen", "voice": "announcer"},
        },
        "narrator": "computer",
        "announcements": [],
        "sections": [
            {"name": "all", "from": 0.0, "to": length, "set": "stage", "figures": ["tim", "lia", "computer"],
             "dance": "chorus"}
        ],
        "gags": [],
        "gestures": [],
        "sounds": [],
        "transitions": [],
        "title": None,
        "look": "standard",
    }
    f = d / "project.json"
    if f.exists():
        print(f"{f} exists - not overwritten (new template: project.new.json)")
        f = d / "project.new.json"
    f.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {d}  song.wav {length:.1f} s, stems: {', '.join(stems) or 'none (Demucs in analyze.py)'}, "
          f"lyrics: {'yes' if a.lyrics else 'no'}, language {a.language}{warn}")


if __name__ == "__main__":
    main()
