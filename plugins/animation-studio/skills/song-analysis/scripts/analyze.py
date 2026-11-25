# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Listen to the song: exposure sheet, vocal tracks, mouth shapes, male/female track -> <project>/analysis/.

  1 lyrics   lyrics without [markers] -> lyrics_clean.txt, markers with line numbers -> markers.json;
             `lyric{sung}` per-word overrides (Suno sang "Hey" where the lyrics say "Hi": write Hi{Hey}) -> the sung
             word goes into lyrics_clean.txt, so alignment, song_sheet and subtitles show it; list in sung_words.json
  2 vocals   stems from project.json (lead/backing) - otherwise Demucs (separate_vocals.py, GPU lock) -> vocals_lead.wav
  3 sheet    track_read.py: beats, bars, accents, words, lines -> song_sheet.json (+ song_sheet.png to look at)
  3b         fix_timing.py repairs word times from the vocal tracks (calls on the backing stem, order errors)
  3c         when lyric lines collapse onto one time (a repeated chorus) or < 60 % of the words are recognised,
             best_words.py runs automatically (several Whisper passes, best per line; --no-best skips it)
  4 mouths   Rhubarb per vocal track -> lead_mouth.json, backing_mouth.json
  5 gender   earshot "a man singing" vs "a woman singing" every 0.5 s on the lead vocals -> gender.json
             (skipped with a note when earshot is not installed)
             project.json "sung_words": "line_start" also takes Whisper's word for a line's FIRST word when it is
             stable (see line_start_swaps); otherwise such a word is only reported with a ready Hi{Hey} hint
Finished steps are skipped (--redo recomputes everything, --only 3,5 runs just those steps).
Usage: uv run analyze.py [<project>] [--redo] [--only 1,2,...]
       uv run analyze.py [<project>] --quick [--no-words]   CPU only while the GPU is busy (no Demucs, no GPU lock):
             step 1 + quick_info.py (tempo, beats, sections, loudness per 2 s, jumps, Whisper small on the CPU on the
             mix or the lead stem) -> analysis/quick.json; song_sheet.json is NOT written (the full run still does it)
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
from song_project import Project, sung_text

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
    clean, markers, sung = [], [], []
    for row in src.read_text(encoding="utf-8").splitlines():
        if not row.strip():
            continue
        if re.fullmatch(r"\s*\(.*\)\s*", row) and not re.search(r"[!?]", row):
            continue                                    # (stage direction) rows are not sung; "(Hey!)" calls are kept
        m = MARKER.match(row)
        if m:
            markers.append({"line": len(clean), "marker": m.group(1)})
        else:
            text, pairs = sung_text(row.strip())
            sung += [{"line": len(clean), "lyric": a, "sung": b, "source": "lyrics"} for a, b in pairs]
            if text:
                clean.append(text)
    (P.analysis / "lyrics_clean.txt").write_text("\n".join(clean) + "\n", encoding="utf-8")
    (P.analysis / "markers.json").write_text(json.dumps(markers, ensure_ascii=False, indent=1), encoding="utf-8")
    (P.analysis / "sung_words.json").write_text(json.dumps(sung, ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(r.split()) for r in clean)
    print(f"1  lyrics: {len(clean)} lines, {words} words, {len(markers)} markers"
          + (f", {len(sung)} sung-word override(s): " + ", ".join(f"{s['lyric'] or '-'} -> {s['sung'] or '-'}"
                                                                for s in sung) if sung else ""))
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
    ts = sorted(w["t"] for w in words if w.get("t") is not None)
    crowded = sum(1 for x, y in zip(ts, ts[1:]) if y - x < 0.08) / max(1, len(ts) - 1)
    # < 85 % heard or words stacked together: the extra passes paid off in the user tests (was < 60 %)
    if words and (stuck or heard < 0.85 or crowded > 0.15):
        print(f"3c {stuck} lyric lines do not start after the previous one, {heard:.0%} of the words recognized, "
              f"{crowded:.0%} crowded -> best_words.py (several Whisper passes, best pass per line, sung order kept)")
        if "--no-best" not in sys.argv:
            subprocess.run(runner(["librosa", "faster-whisper", "numpy", "soxr"]) + [str(HERE / "best_words.py"),
                                                                                str(P.dir)], check=True)
            sheet = json.loads((P.analysis / "song_sheet.json").read_text(encoding="utf-8"))
    if P.get("sung_words") == "line_start":
        done = apply_line_start(P, sheet)
        if done:
            print(f"3d sung words from Whisper at line starts (\"sung_words\": \"line_start\"): "
                  + ", ".join(f"line {d['line']} {d['lyric']} -> {d['sung']}" for d in done))
    for msg in sheet_warnings(sheet):
        print("   WARNING " + msg)


LETTERS = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
MIN_PROB = 0.7          # Whisper's probability for a heard word to count as stable


def _core(word):
    """(leading punctuation, word, trailing punctuation)"""
    m = re.match(r"^(\W*)(.*?)(\W*)$", word)
    return m.group(1), m.group(2), m.group(3)


def line_start_swaps(sheet, min_prob=MIN_PROB):
    """Lines whose FIRST word Whisper heard as another word, stably: the lyric word was matched 1:1 to a different
    heard word ("aligned" with `heard`), Whisper was sure (probability >= min_prob in the pass whose timing is used -
    best_words.py passes count), the heard word is one plain word and the line's next word was recognized exactly
    (the line is anchored right behind it; an unlisted call "Hey! Hey!" heard over two lyric words "Out of" fails
    this). A pause after the word is allowed: "Hey. Ich bin hier ..." (maschine_dance, 0.0 s, mix pass p=0.96).
    Only line starts: mid-line, Whisper's other word is far more often a mishearing of singing than a real change.
    -> [(word dict, heard word)]"""
    by_line = {}
    for w in sheet.get("words", []):
        if w.get("t") is not None and w.get("line") is not None:
            by_line.setdefault(w["line"], []).append(w)
    out = []
    for li, ws in sorted(by_line.items()):
        w0 = ws[0]
        heard = (w0.get("heard") or "").strip()
        if (w0.get("source") != "aligned" or not heard or (w0.get("heard_prob") or 0) < min_prob
                or len(ws) < 2 or ws[1].get("source") != "recognized"):
            continue
        core = _core(heard)[1]
        if not LETTERS.fullmatch(core) or core.lower() == _core(w0["word"])[1].lower():
            continue
        out.append((w0, core))
    return out


def apply_line_start(P, sheet, min_prob=MIN_PROB):
    """Take Whisper's word for stable line-start swaps (project.json "sung_words": "line_start"): the word in
    song_sheet.json (the lyric word kept as "lyric"), the line text and lyrics_clean.txt; listed in sung_words.json
    with "source": "whisper". -> [{"line", "lyric", "sung", "source", "t", "prob"}]"""
    swaps = line_start_swaps(sheet, min_prob)
    if not swaps:
        return []
    lyr_f = P.analysis / "lyrics_clean.txt"
    rows = lyr_f.read_text(encoding="utf-8").splitlines() if lyr_f.exists() else []
    done = []
    for w, core in swaps:
        lead, old, tail = _core(w["word"])
        new_core = core[:1].upper() + core[1:] if old[:1].isupper() else core[:1].lower() + core[1:]
        new = lead + new_core + tail
        done.append({"line": w["line"], "lyric": w["word"], "sung": new, "source": "whisper", "t": w["t"],
                     "prob": w.get("heard_prob")})
        w["lyric"], w["word"] = w["word"], new
        for l in sheet.get("lines", []):
            if l.get("line") == w["line"] and l.get("text"):
                l["text"] = l["text"].replace(w["lyric"], new, 1)
        if 0 <= w["line"] < len(rows):
            rows[w["line"]] = rows[w["line"]].replace(w["lyric"], new, 1)
    (P.analysis / "song_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
    if rows:
        lyr_f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    sw = P.analysis / "sung_words.json"
    old = json.loads(sw.read_text(encoding="utf-8")) if sw.exists() else []
    redone = {d["line"] for d in done}
    keep = [s for s in old if not (s.get("source") == "whisper" and s.get("line") in redone)]
    sw.write_text(json.dumps(keep + done, ensure_ascii=False, indent=1), encoding="utf-8")
    return done


def leading_strays(starts):
    """How many words (0-2) at the start of a line sit far before a dense rest: each gap after them > 1 s and more
    than twice the median gap of the rest. User tests: an unlisted "Hey! Hey!" was heard as "Out of"."""
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    for k in (2, 1):
        rest = gaps[k:]
        if len(rest) >= 2:
            med = sorted(rest)[len(rest) // 2]
            if all(g > 1.0 and g > 2 * med for g in gaps[:k]):
                return k
    return 0


def sheet_warnings(sheet):
    """Plausibility notes on the word times of song_sheet.json (user tests): a lyric line placed after the song end
    (an excerpt that stops before the last line), and a line whose first word sits far before a dense rest (a call
    that is not in the lyrics, "Hey!", heard as that word)."""
    out, end = [], float(sheet.get("duration") or 0)
    swaps = line_start_swaps(sheet)
    swapped = {w["line"] for w, _ in swaps}
    by_line = {}
    for w in sheet.get("words", []):
        if w.get("t") is not None:
            by_line.setdefault(w.get("line"), []).append(w)
    for li, ws in sorted(by_line.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
        ws.sort(key=lambda w: w["t"])
        if end and ws[0]["t"] >= end - 0.3:
            where = "after the song end" if ws[0]["t"] >= end else f"only {end - ws[0]['t']:.2f} s before the song end"
            out.append(f"lyric line {li} starts at {ws[0]['t']:.2f} s, {where} ({end:.2f} s): at most a fragment of it "
                       "is sung in this (excerpt of the) song - delete it (or keep only the sung words) and run --redo")
            continue
        k = leading_strays([w["t"] for w in ws])
        if k and li not in swapped:                     # a stable swapped first word gets its own hint below
            lead = " ".join(w["word"] for w in ws[:k])
            out.append(f"lyric line {li}: '{lead}' ({ws[0]['t']:.2f} s) sits far before the rest of the line - a call "
                       "that is not in the lyrics (\"Hey!\") heard as it? add the call to the lyrics ({Hey!} before "
                       "the line = sung but not written), or fix the time")
    for w, core in swaps:
        out.append(f"lyric line {w['line']}: sung '{core}' where the lyrics say '{w['word']}' ({w['t']:.2f} s, Whisper "
                   f"p={w.get('heard_prob', 0):.2f}) - the subtitle shows the lyric word: write "
                   f"{_core(w['word'])[1]}{{{core}}} in lyrics.txt and run --redo, or set project.json "
                   "\"sung_words\": \"line_start\"")
    return out


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


def step_quick(P, words=True):
    """CPU-only overview while the GPU is busy -> analysis/quick.json (quick_info.py; no Demucs, no GPU lock).
    Words from the lead stem when project.json has one, else from the mix; aligned to lyrics_clean.txt."""
    out = P.analysis / "quick.json"
    cmd = runner(["librosa", "faster-whisper", "soxr"]) + [
        str(HERE / "quick_info.py"), str(P.song), str(out), "--lang", P.get("language", "de"), "--fps", str(P.fps)]
    lead = (P.get("stems") or {}).get("lead")
    if lead and P.path(lead).exists():
        cmd += ["--vocals", str(P.path(lead))]
    lyr = P.analysis / "lyrics_clean.txt"
    if lyr.exists() and lyr.read_text(encoding="utf-8").strip():
        cmd += ["--lyrics", str(lyr)]
    if not words:
        cmd.append("--no-words")
    import os
    subprocess.run(cmd, check=True, env=dict(os.environ, WHISPER_CPU="1"))
    print("Q  quick overview (CPU) -> analysis/quick.json - song_sheet.json still needs the full analyze.py run")


def main():
    args = sys.argv[1:]
    only = {int(x) for x in args[args.index("--only") + 1].split(",")} if "--only" in args else None
    rest = [a for i, a in enumerate(args) if not a.startswith("--") and not (i > 0 and args[i - 1] == "--only")]
    P = Project(rest[0] if rest else ".")
    P.check("song-analysis")                 # project.json validated before any long step
    if "--quick" in args:
        if "--redo" in args or not (P.analysis / "lyrics_clean.txt").exists():
            step_lyrics(P)
        step_quick(P, words="--no-words" not in args)
        return
    for nr, fname, fn in STEPS:
        if only and nr not in only:
            continue
        if not only and "--redo" not in args and (P.analysis / fname).exists():
            print(f"{nr}  {fname} exists - skipped")
            continue
        fn(P)


if __name__ == "__main__":
    main()
