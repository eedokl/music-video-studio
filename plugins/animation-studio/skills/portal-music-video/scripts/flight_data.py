"""The song for a portal flight: analysis of the song project -> flight/src/song.js (+ public/song.wav).

Imported by new_flight.py and flight.py (no CLI of its own).

Reads   analysis/timing.json       per sung line {"t","e","words","ends"} (song seconds; lyric-music-video analyze_song.py)
        analysis/hits.json         {"bpm","offset"} = the beat grid
        analysis/lyrics_clean.txt  the sung lines, one per row (lyrics.txt without headers when it is missing)
        analysis/markers.json      [{"line": index of the first line after it, "marker": "[Section] header text"}]
Writes  public/spectrum.json (eight frequency bands of the song over time, see spectrum()) and
        song.js: BPM, OFFSET, BEAT, SONG_END, V, STEP, EYE, LINES (words in upper case + their times) and SECTIONS =
        the song cut into parts for one world each. Whatever stands below the marker line in an existing song.js is kept.

How the song is cut: a part starts on the bar line nearest to the first word of a [Section] header's first line (a
portal is crossed on the one of a bar, and sung lines mostly start with an upbeat just before it). A stretch of
24 beats or more without words becomes a part of its own (an instrumental world); parts shorter than 8 beats join
the part before. The first part starts with the song, the last one ends with it.
"""
import json
import re
import shutil
from pathlib import Path

MARK = "// ---- below this line flight.py data keeps what you add ----"
SPEED = 6               # world units per second
MIN_BEATS = 8           # a world is at least two bars long
GAP_BEATS = 24          # this long without words = an instrumental part of its own


def sung_lines(P):
    f = P.analysis / "lyrics_clean.txt"
    if f.exists():
        return [" ".join(r.split()) for r in f.read_text(encoding="utf-8").splitlines() if r.strip()]
    rows = P.path(P.get("lyrics", "lyrics.txt")).read_text(encoding="utf-8").splitlines()
    rows = [re.sub(r"[^\s{}]*\{([^{}]*)\}", r"\1", r) for r in rows]   # lyric{sung} -> the sung word (song_project.sung_text)
    return [" ".join(r.split()) for r in rows if r.strip() and not re.match(r"^\s*[\[(]", r)]


def cut(timing, markers, bpm, offset, end):
    """-> [{"name", "beats", "lines": [indexes]}]; beats are counted from the song's first sample."""
    beat = 60.0 / bpm
    total = end / beat                                           # the song in beats (from second 0)
    at = lambda sec: (sec - offset) / beat + offset / beat       # song second -> beats from second 0  # noqa: E731
    bar = lambda sec: round((sec - offset) / (4 * beat)) * 4 + offset / beat   # nearest bar line, in beats from 0  # noqa: E731
    names = {}
    for m in markers:                                            # several headers before one line: the last one names it
        if 0 <= int(m["line"]) < len(timing):
            names[int(m["line"])] = re.sub(r"\s*[–-].*$", "", str(m["marker"]).strip("[] ")).strip() or "Part"
    starts = sorted(names) or [0]
    if starts[0] != 0:
        starts.insert(0, 0)
    parts = []                                                   # [start beat, name, [line indexes]]
    for k, first in enumerate(starts):
        last = (starts[k + 1] if k + 1 < len(starts) else len(timing))
        idx = list(range(first, last))
        if not idx:
            continue
        b = max(0.0, bar(timing[first]["t"]))
        if parts and first > 0:                                  # a long silence before it: an instrumental part
            quiet_from = timing[first - 1]["e"]
            if at(timing[first]["t"]) - at(quiet_from) >= GAP_BEATS:
                gb = bar(quiet_from + 2 * beat + 2 * beat)       # the bar line after the last word has rung out
                if gb - parts[-1][0] >= MIN_BEATS and b - gb >= MIN_BEATS:
                    parts.append([gb, "Instrumental", []])
        if parts and b - parts[-1][0] < MIN_BEATS:
            parts[-1][2] += idx                                  # too short for a world of its own
            continue
        parts.append([b, names.get(first, "Part"), idx])
    if not parts:
        parts = [[0.0, "Song", []]]
    if parts[0][0] >= MIN_BEATS:                                 # music before the first word
        parts.insert(0, [0.0, "Intro", []])
    parts[0][0] = 0.0
    last_end = timing[-1]["e"] if timing else 0.0
    if total - at(last_end) >= GAP_BEATS:                        # music after the last word
        ob = bar(last_end + 4 * beat)
        if ob - parts[-1][0] >= MIN_BEATS and total - ob >= MIN_BEATS:
            parts.append([ob, "Outro", []])
    if len(parts) == 1:                                          # a flight needs two worlds: halve it on a bar line
        half = round(total / 8) * 4 + offset / beat
        lines = parts[0][2]
        parts = [[0.0, parts[0][1], [i for i in lines if at(timing[i]["t"]) < half]],
                 [half, parts[0][1] + " 2", [i for i in lines if at(timing[i]["t"]) >= half]]]
    out = []
    for k, (b, name, idx) in enumerate(parts):
        nxt = parts[k + 1][0] if k + 1 < len(parts) else total
        out.append({"name": name, "beats": round(nxt - b, 4), "lines": idx})
    return out


def write(P, flight):
    """Write flight/src/song.js and flight/public/song.wav; returns the sections."""
    from media import duration
    flight = Path(flight)
    for need in ("timing.json", "hits.json"):
        if not (P.analysis / need).exists():
            raise SystemExit(f"analysis/{need} missing - analyse the song first (lyric-music-video analyze_song.py PROJECT)")
    timing = json.loads((P.analysis / "timing.json").read_text(encoding="utf-8"))
    hits = json.loads((P.analysis / "hits.json").read_text(encoding="utf-8"))
    bpm, offset = float(hits["bpm"]), float(hits.get("offset", 0.0))
    if bpm <= 0:
        raise SystemExit("analysis/hits.json: bpm must be > 0")
    offset = offset % (4 * 60.0 / bpm)                           # the first bar line of the song
    lines = sung_lines(P)
    if len(lines) != len(timing):
        raise SystemExit(f"timing.json has {len(timing)} lines, the lyrics {len(lines)} - analyse again after editing the lyrics")
    for text, t in zip(lines, timing):
        if len(t["words"]) != len(text.split(" ")):
            raise SystemExit(f"word count differs for '{text}': {len(t['words'])} times")
    end = duration(P.song)
    sections = cut(timing, P.markers(), bpm, offset, end)
    where = {i: k for k, s in enumerate(sections) for i in s["lines"]}
    rows = [{"text": text, "section": where.get(i, 0), "words": text.upper().split(" "),
             "at": [round(float(x), 3) for x in t["words"]]} for i, (text, t) in enumerate(zip(lines, timing))]
    js = ["// The song's data. WRITTEN BY flight.py data (from the song project's analysis) - do not edit by hand above the",
          "// marker line at the end; a film's own additions (fonts, hand-picked times) go below it and are kept.",
          "",
          f"export const BPM = {bpm:g};",
          f"export const OFFSET = {offset:.4f}; // first bar line of the song, seconds",
          "export const BEAT = 60 / BPM;",
          "export const FROM = 0; // the film is the whole song",
          f"export const SONG_END = {end:.3f};",
          "",
          f"export const V = {SPEED}; // flight speed, world units per second - the same in every world",
          "export const STEP = V * BEAT; // distance flown per beat: everything along the road is spaced in STEPs",
          "export const EYE = 1.6; // height of the camera above the road",
          "",
          "// every sung line: the words as shown (upper case) and when each word starts (song seconds)",
          "export const LINES = ["]
    js += [f"  {json.dumps(r, ensure_ascii=False)}," for r in rows]
    js += ["];",
           "// the song cut into worlds: every part starts on a bar line; beats are fractional in the first and last part",
           "export const SECTIONS = ["]
    js += [f"  {json.dumps(s, ensure_ascii=False)}," for s in sections]
    js += ["];", "", MARK]
    f = flight / "src" / "song.js"
    tail = ""
    if f.exists():
        old = f.read_text(encoding="utf-8")
        if MARK in old:
            tail = old.split(MARK, 1)[1]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(js) + (tail if tail.strip() else "\n"), encoding="utf-8")
    pub = flight / "public"
    pub.mkdir(parents=True, exist_ok=True)
    dst = pub / "song.wav"
    if not dst.exists() or dst.stat().st_size != P.song.stat().st_size:
        shutil.copyfile(P.song, dst)
    spectrum(P.song, pub / "spectrum.json")
    return sections, bpm, offset, end


def spectrum(song, out, fps=60, bands=8, win=4096, sr=32000):
    """What the song sounds like over time, for worlds that listen (src/spectrum.js levelsAt): eight frequency bands
    from the bass (0) to the highs (7) at 60 values a second -> {"fps", "bands", "frames", "data": [0..255, ...]}.
    Every band is scaled to its own range in this song (5th to 98th percentile of its level in dB) and follows the
    sound with a fast attack and a slow release, so that lights jump on and glide off."""
    import numpy as np
    from media import decode
    x = decode(song, sr)
    hop = sr / fps
    frames = int(len(x) / hop)
    edges = np.geomspace(40, 12000, bands + 1)
    freqs = np.fft.rfftfreq(win, 1 / sr)
    masks = [(freqs >= edges[b]) & (freqs < edges[b + 1]) for b in range(bands)]
    window = np.hanning(win)
    pad = np.concatenate([np.zeros(win // 2), x, np.zeros(win)])
    level = np.zeros((frames, bands))
    for i in range(frames):
        k = int(i * hop)
        spec = np.abs(np.fft.rfft(pad[k:k + win] * window)) ** 2
        level[i] = [spec[m].sum() for m in masks]
    db = 10 * np.log10(level + 1e-12)
    lo, hi = np.percentile(db, 5, axis=0), np.percentile(db, 98, axis=0)
    norm = np.clip((db - lo) / np.maximum(hi - lo, 1e-6), 0, 1)
    env = np.zeros_like(norm)
    for i in range(frames):                                      # fast attack, slow release
        env[i] = norm[i] if i == 0 else np.maximum(norm[i], env[i - 1] * 0.9)
    Path(out).write_text(json.dumps({"fps": fps, "bands": bands, "frames": frames,
                                     "data": np.round(env * 255).astype(int).flatten().tolist()}, separators=(",", ":")),
                         encoding="utf-8")
