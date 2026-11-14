# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Listen to the song: exposure sheet, vocal tracks, mouth shapes, male/female track -> <project>/analysis/.

  1 lyrics   lyrics without [markers] -> lyrics_clean.txt, markers with line numbers -> markers.json
  2 vocals   stems from project.json (lead/backing) - otherwise Demucs (separate_vocals.py, GPU lock) -> vocals_lead.wav
  3 sheet    track_read.py: beats, bars, accents, words, lines -> song_sheet.json (+ song_sheet.png to look at)
  3b         fix_timing.py repairs word times from the vocal tracks (calls on the backing stem, order errors)
  3c         when lyric lines collapse onto one time (a repeated chorus) or < 60 % of the words are recognised,
             best_words.py runs automatically (several Whisper passes, best per line; --no-best skips it)
  4 mouths   Rhubarb per vocal track -> lead_mouth.json, backing_mouth.json
  5 gender   earshot "a man singing" vs "a woman singing" every 0.5 s on the lead vocals -> gender.json
             (skipped with a note when earshot is not installed)
Finished steps are skipped (--redo recomputes everything, --only 3,5 runs just those steps).
Usage: uv run analyze.py [<project>] [--redo] [--only 1,2,...]
Time: ~1-3 min per 30 s of song (Whisper large-v3 on the GPU waits for the GPU lock; small on the CPU otherwise).
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import _studio  # noqa: E402
_studio.use('song-analysis')
import config
from media import duration, ffmpeg
from song_project import Project

HERE = Path(__file__).resolve().parent
MARKER = re.compile(r"^\s*\[(.+)\]\s*$")


def runner(gpu_pkgs):
    """Kept for callers of older versions - use config.gpu_runner."""
    return config.gpu_runner(gpu_pkgs)


def step_lyrics(P):
    src = P.path(P.get("lyrics"))
    if not src or not src.exists():
        print("1  no lyrics - words from Whisper only, choruses guessed from repeated lines")
        (P.analysis / "lyrics_clean.txt").write_text("", encoding="utf-8")
        return
    clean, markers = [], []
    for row in src.read_text(encoding="utf-8").splitlines():
        if not row.strip():
            continue
        if re.fullmatch(r"\s*\(.*\)\s*", row) and not re.search(r"[!?]", row):
            continue                                    # (stage direction) rows are not sung; "(Hey!)" calls are kept
        m = MARKER.match(row)
        if m:
            markers.append({"line": len(clean), "marker": m.group(1)})
        else:
            clean.append(row.strip())
    (P.analysis / "lyrics_clean.txt").write_text("\n".join(clean) + "\n", encoding="utf-8")
    (P.analysis / "markers.json").write_text(json.dumps(markers, ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(r.split()) for r in clean)
    print(f"1  lyrics: {len(clean)} lines, {words} words, {len(markers)} markers")
    secs = duration(P.song)
    if words > secs * 4:                                # more than ~4 words per second cannot be sung
        print(f"   WARNING: {words} words for {secs:.0f} s of song - trim lyrics.txt to the sung lines first")


def step_vocals(P):
    target = P.analysis / "vocals_lead.wav"
    st = P.get("stems") or {}
    if st.get("lead"):
        shutil.copy(P.path(st["lead"]), target)
        if st.get("backing"):
            shutil.copy(P.path(st["backing"]), P.analysis / "vocals_backing.wav")
        print("2  vocals from the stems")
        return
    subprocess.run(runner(["demucs", "soundfile"]) + [str(HERE / "separate_vocals.py"), str(P.song),
                                                      "-o", str(P.cache / "sep")], check=True)
    shutil.copy(P.cache / "sep" / "htdemucs" / "song" / "vocals.wav", target)
    print("2  vocals separated with Demucs (one track: lead and backing together)")


def step_sheet(P):
    cmd = runner(["librosa", "faster-whisper", "matplotlib"]) + [
        str(HERE / "track_read.py"), str(P.song), "--vocals", str(P.analysis / "vocals_lead.wav"),
        "--lang", P.get("language", "de"), "--fps", str(P.fps)]
    lyr = P.analysis / "lyrics_clean.txt"
    if lyr.exists() and lyr.read_text(encoding="utf-8").strip():
        cmd += ["--lyrics", str(lyr)]
    subprocess.run(cmd, check=True, env=dict(__import__("os").environ, TRACK_READ_RAW=str(P.analysis / "whisper_raw.json")))
    for ext in ("json", "csv", "png"):
        q = P.dir / f"song_sheet.{ext}"
        if q.exists():
            shutil.move(str(q), P.analysis / q.name)
    print("3  exposure sheet -> analysis/song_sheet.json (overview song_sheet.png)")
    import fix_timing
    print(f"3b word times repaired from the vocal tracks: {fix_timing.fix(P)} words moved "
          "(calls to backing bursts, order errors, cut-off line starts)")
    sheet = json.loads((P.analysis / "song_sheet.json").read_text(encoding="utf-8"))
    starts = [l["t"] for l in sheet.get("lines", [])]
    stuck = sum(1 for a, b in zip(starts, starts[1:]) if b <= a + 0.05)
    words = sheet.get("words", [])
    heard = sum(1 for w in words if w.get("source") == "recognized") / max(len(words), 1)
    if words and (stuck or heard < 0.6):              # lines collapsed (repeated chorus) or too little heard
        print(f"3c {stuck} lyric lines do not start after the previous one, {heard:.0%} of the words recognized "
              "-> best_words.py (several Whisper passes, best pass per line, sung order kept)")
        if "--no-best" not in sys.argv:
            subprocess.run(runner(["librosa", "faster-whisper", "numpy", "soxr"]) + [str(HERE / "best_words.py"),
                                                                                str(P.dir)], check=True)


def step_mouths(P):
    for k in ("lead", "backing"):
        track = P.analysis / f"vocals_{k}.wav"
        if not track.exists():
            continue
        mono = P.cache / f"mono_{k}.wav"
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(track), "-ac", "1", "-ar", "16000", str(mono)], check=True)
        subprocess.run([config.need("rhubarb"), "-r", "phonetic", "-f", "json", "--extendedShapes", "GHX", "-q",
                        "-o", str(P.analysis / f"{k}_mouth.json"), str(mono)], check=True)
        n = len(json.loads((P.analysis / f"{k}_mouth.json").read_text(encoding="utf-8"))["mouthCues"])
        print(f"4  Rhubarb {k}: {n} mouth shapes")


def step_gender(P, step=0.5, window=1.0):
    ear = config.get("earshot")
    if not ear:
        print("5  earshot not installed - no male/female track (voices follow lyric markers and corrections.json)")
        (P.analysis / "gender.json").write_text("[]", encoding="utf-8")
        return
    track = P.analysis / "vocals_lead.wav"
    tmp = P.cache / "gender"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    starts = [round(i * step, 2) for i in range(int(max(duration(track) - window, 0) / step) + 1)]
    for s in starts:
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-ss", str(s), "-t", str(window), "-i", str(track), "-ac", "1",
                        str(tmp / f"c_{int(s * 100):06d}.wav")], check=True)
    res = {}
    for key, query in (("m", "a man singing, male vocals"), ("f", "a woman singing, female vocals")):
        out = tmp / f"{key}.json"
        subprocess.run(config.cmdline([ear, "rank", query, str(tmp), "--json", "--out", str(out)]), check=True,
                       capture_output=True)
        res[key] = {x["name"]: x for x in json.loads(out.read_text(encoding="utf-8"))["results"]}
    track_d = []
    for s in starts:
        n = f"c_{int(s * 100):06d}.wav"
        mm, ff = res["m"][n], res["f"][n]
        track_d.append({"t": round(s + window / 2, 3), "d": round(mm["cosine"] - ff["cosine"], 4),
                        "silent": bool(mm.get("near_silent", False))})
    (P.analysis / "gender.json").write_text(json.dumps(track_d), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    male = sum(1 for x in track_d if x["d"] > 0.03 and not x["silent"])
    female = sum(1 for x in track_d if x["d"] < -0.01 and not x["silent"])
    print(f"5  earshot: {len(track_d)} windows, male {male}, female {female}")


STEPS = [(1, "lyrics_clean.txt", step_lyrics), (2, "vocals_lead.wav", step_vocals),
         (3, "song_sheet.json", step_sheet), (4, "lead_mouth.json", step_mouths), (5, "gender.json", step_gender)]


def main():
    args = sys.argv[1:]
    only = {int(x) for x in args[args.index("--only") + 1].split(",")} if "--only" in args else None
    rest = [a for i, a in enumerate(args) if not a.startswith("--") and not (i > 0 and args[i - 1] == "--only")]
    P = Project(rest[0] if rest else ".")
    P.check("song-analysis")                 # project.json validated before any long step
    for nr, fname, fn in STEPS:
        if only and nr not in only:
            continue
        if not only and "--redo" not in args and (P.analysis / fname).exists():
            print(f"{nr}  {fname} exists - skipped")
            continue
        fn(P)


if __name__ == "__main__":
    main()
