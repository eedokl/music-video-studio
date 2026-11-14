# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "opentimelineio==0.18.1", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Film music for films WITHOUT a song: a generated score that follows a cue list (numpy synthesis), or - opt-in -
ElevenLabs Music cues laid on the same cue list.

  uv run score.py --plan cut.json [-o music.wav] [--seed 3]
        [--style light|orchestral] [--version v2]         cue list from the cut plan (cut.py), exact film length
  uv run score.py --cues cues.json --duration 29.7 -o music.wav
  ... score.py --plan cut.json --elevenlabs [--fetch]     ElevenLabs Music instead of the synthesis (see below)

Cue list (in the cut plan as "music": {"score": {"cues": [...], "seed": 3, "style": "light"}} or a cues.json):
  [{"at": 0, "mood": "intro"}, {"shot": "Pip spricht", "mood": "calm"}, {"at": 21.5, "mood": "finale", "stinger": true}]
  "at" in film seconds or "shot": a shot name / index of the cut plan (its start on the finished timeline).
  Without cues the shots' own "mood" keys are used (consecutive shots with the same mood share one cue), else one
  "playful" cue. Moods: intro, playful, calm, night, tension, hope, sad, build, finale.
  "stinger": true = an accent on the cue start (bell flourish; orchestral: timpani + brass swell).
  "hits": [{"at": 12.4, "kind": "bell"|"timpani"|"stinger"}] in the score dict = extra accents (a gag, a reveal).
How it sounds (technique from the ai_efficiency film, generalised): e-piano chords + eighth arpeggios, plucked bass,
shaker, glockenspiel accents, string pads for quiet/sad/night cues; "orchestral" adds string pads everywhere, brass
swells and timpani on cue changes and a big final chord. Each cue fills whole bars: the bar length is stretched so
the bars end exactly on the next cue. A final chord + bell run lands on the film end, 1.5 s fade-in, 2 s fade-out.
The creative seed varies key, tempo, chord progressions, arpeggio patterns, lead instrument and accents - same seed,
same score; new seed, new take. The score is a BED: cut.py ducks it under dialogue.

ElevenLabs Music (optional, opt-in, costs credits):
  --elevenlabs uses cached cues (cache/music_cues/<mood>_<hash>.mp3); --fetch is needed to request missing ones.
  The API key is read ONLY from the environment variable ELEVENLABS_API_KEY - never stored, never printed.
  The PROMPT TEXT (mood description + optional "prompt" of the score dict) LEAVES THE MACHINE and is sent to
  api.elevenlabs.io; no picture, no dialogue, no project names are sent. Ask the user before using it.
  Montage: consecutive cues of the same mood share one continuous cue; a mood that comes back continues at the next
  bar after where it stopped; a cue shorter than its section loops at bar boundaries (librosa beats when installed,
  else every 2 s) with a 120 ms crossfade; the last cue is aligned so its ending lands on the film end.

Python:  import score; y = score.compose(cues, total_s, seed=3, style="light", sr=48000)  # (n, 2) float32
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()

SR = 48000

CH = {  # chord: (bass MIDI, voicing)
    "C": (36, [60, 64, 67, 71]), "Am": (45, [57, 60, 64, 67]), "Dm": (38, [62, 65, 69, 72]), "G": (43, [59, 62, 65, 67]),
    "F": (41, [57, 60, 64, 65]), "Em": (40, [59, 62, 64, 67]), "E": (40, [56, 59, 64, 68]), "Fm": (41, [56, 60, 63, 65]),
    "Bb": (46, [58, 62, 65, 69]), "Ab": (44, [56, 60, 63, 67]),
}
MOODS = {  # mood: (progressions to choose from, density, texture)
    "intro": ([["Am", "F", "C", "G"], ["C", "Em", "F", "G"]], 0.45, "thin"),
    "playful": ([["C", "Am", "Dm", "G"], ["C", "F", "Dm", "G"], ["F", "G", "Em", "Am"]], 0.75, "full"),
    "calm": ([["C", "Am", "F", "G"], ["F", "C", "Dm", "C"]], 0.55, "medium"),
    "night": ([["Am", "Em", "F", "G"], ["Dm", "Am", "Em", "Am"]], 0.6, "night"),
    "tension": ([["Dm", "Am", "Bb", "E"], ["Am", "Fm", "Am", "E"]], 0.55, "medium"),
    "hope": ([["F", "C", "Dm", "G"], ["C", "G", "Am", "F"]], 0.6, "medium"),
    "sad": ([["Am", "F", "Dm", "E"], ["Am", "Dm", "Fm", "E"]], 0.35, "pad"),
    "build": ([["Am", "F", "C", "G"], ["F", "G", "Am", "C"]], 0.6, "build"),
    "finale": ([["C", "G", "Am", "F"], ["F", "G", "C", "C"]], 0.9, "full"),
}
ALIASES = {"spiel": "playful", "ruhig": "calm", "nacht": "night", "spannung": "tension", "hoffnung": "hope",
           "traurig": "sad", "aufbau": "build", "happy": "playful", "neutral": "calm", "suspense": "tension"}


def mood_of(m):
    m = ALIASES.get(str(m).lower(), str(m).lower())
    if m not in MOODS:
        raise SystemExit(f"unknown mood '{m}' - use one of {', '.join(MOODS)}")
    return m


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ------------------------------------------------------------------ instruments (numpy, mono)

def env(n, a, d, sustain=0.0, r=0.0):
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-4), sustain + (1 - sustain) * np.exp(-(t - a) / max(d, 1e-4)))
    if r > 0:
        e *= np.clip((n / SR - t) / r, 0, 1)
    return e


def epiano(f, dur, vel=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = np.sin(2 * np.pi * f * t) * 1.2 * np.exp(-t * 3)
    s = np.sin(2 * np.pi * f * t + mod) + 0.25 * np.sin(4 * np.pi * f * t)
    return s * env(n, 0.005, 0.9, 0.0, 0.08) * vel * (1 + 0.04 * np.sin(2 * np.pi * 5 * t))


def marimba(f, dur, vel=0.5):
    n = int(min(dur, 1.2) * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 3.9 * t) * np.exp(-t * 18)
    return s * env(n, 0.002, 0.35, 0.0, 0.03) * vel * 1.2


def pluck(f, dur, vel=0.5):
    """Karplus-Strong string (guitar/harp-like)."""
    n = int(min(dur, 1.6) * SR)
    p = max(2, int(SR / f))
    rng = np.random.default_rng(int(f * 10))
    buf = rng.uniform(-1, 1, p)
    out = np.empty(n + p)
    for k in range(0, n, p):                            # one period per step (vectorised Karplus-Strong)
        out[k:k + p] = buf
        buf = 0.5 * (buf + np.roll(buf, -1)) * 0.996
    return out[:n] * vel * 0.6 * env(n, 0.001, 10, 1.0, 0.05)


def bass(f, dur, vel=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    return s * env(n, 0.004, 0.45, 0.0, 0.05) * vel


def bell(f, dur, vel=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)
    return s * env(n, 0.002, 0.6, 0, 0.05) * vel


def shaker(dur, vel, rng):
    n = int(dur * SR)
    x = np.diff(np.concatenate([[0], rng.normal(0, 1, n)]))
    return x * env(n, 0.003, 0.05, 0, 0.01) * vel


def strings(freqs, dur, vel=0.18, attack=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        for det in (-0.006, 0.0, 0.007):
            ff = f * (1 + det)
            for h in range(1, 9):
                s += np.sin(2 * np.pi * ff * h * t + h * det * 100) / (h ** 1.15) * (0.6 if h > 4 else 1)
    s *= 1 + 0.03 * np.sin(2 * np.pi * 5.2 * t)
    return s * np.clip(t / attack, 0, 1) * np.clip((dur - t) / 0.8, 0, 1) * vel / (len(freqs) * 6)


def brass(freqs, dur, vel=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    swell = np.clip(t / (dur * 0.6), 0, 1) ** 1.5
    for f in freqs:
        for h in range(1, 7):
            s += np.sin(2 * np.pi * f * h * t + 0.2 * np.sin(2 * np.pi * 5 * t)) * (swell ** (h * 0.4)) / h
    return s * swell * np.clip((dur - t) / 0.3, 0, 1) * vel / len(freqs)


def timpani(dur=2.0, vel=0.7):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 55 + 35 * np.exp(-t * 8)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) + 0.4 * np.sin(1.5 * ph) + np.random.default_rng(3).normal(0, 1, n) * np.exp(-t * 40) * 0.5
    return s * np.exp(-t * 1.6) * vel


LEADS = {"epiano": epiano, "marimba": marimba, "pluck": pluck}
LAST = {}                                               # what the last compose() chose (key, tempo, lead, chords)


def add(buf, x, t0, pan=0.0):
    i = int(t0 * SR)
    if i < 0:
        x, i = x[-i:], 0
    if i >= len(buf):
        return
    x = x[: len(buf) - i]
    buf[i:i + len(x), 0] += x * min(1, 1 - pan)
    buf[i:i + len(x), 1] += x * min(1, 1 + pan)


# ------------------------------------------------------------------ composition

def sections(cues, total):
    """cues [{"at", "mood", ...}] -> [(t0, dur, cue)] covering 0..total (first cue pulled to 0)."""
    cs = sorted(({**c, "at": float(c.get("at", 0)), "mood": mood_of(c.get("mood", "playful"))} for c in cues),
                key=lambda c: c["at"]) or [{"at": 0.0, "mood": "playful"}]
    cs[0]["at"] = 0.0
    out = []
    for i, c in enumerate(cs):
        end = cs[i + 1]["at"] if i + 1 < len(cs) else total
        if end - c["at"] > 0.05:
            out.append((c["at"], end - c["at"], c))
    return out


def compose(cues, total, seed=0, style="light", sr=48000, hits=()):
    """-> (n, 2) float32 at sr, exactly total seconds, peak 0.8."""
    global SR
    SR = sr
    rng = np.random.default_rng(int(seed) * 7919 + 7)
    orch = style == "orchestral"
    key = int(rng.integers(-3, 5))                      # transpose
    bpm = float(rng.uniform(88, 108))
    beat = 60 / bpm
    bar_nom = 4 * beat
    lead = LEADS[rng.choice(list(LEADS), p=[0.5, 0.3, 0.2])]
    prog = {m: v[0][int(rng.integers(len(v[0])))] for m, v in MOODS.items()}
    arp_shape = rng.permutation(4)
    LAST.clear()
    LAST.update(key=key, bpm=round(bpm, 1), lead=lead.__name__, style=style,
                progressions={c["mood"]: prog[c["mood"]] for c in (x[2] for x in sections(cues, total))})
    buf = np.zeros((int((total + 4) * SR), 2))
    secs = sections(cues, total)
    for si, (t0, dur, cue) in enumerate(secs):
        mood = cue["mood"]
        _, strength, tex = MOODS[mood]
        strength *= float(cue.get("level", 1.0))
        chords = prog[mood]
        bars = max(1, int(round(dur / bar_nom)))
        bl = dur / bars
        for b in range(bars):
            tb = t0 + b * bl
            bs, voices = CH[chords[b % len(chords)]]
            bs, voices = bs + key, [v + key for v in voices]
            pr = (b + 1) / bars
            dens = strength if tex != "build" else 0.25 + 0.7 * pr
            if tex in ("full", "medium", "night", "build", "thin"):
                for k, m in enumerate(voices):
                    add(buf, epiano(mtof(m), bl * 0.9, 0.16 * dens), tb + 0.01 * k, pan=-0.3 + 0.2 * k)
                if dens > 0.5:
                    for e in range(8):
                        if rng.random() < dens * 0.7:
                            m = voices[arp_shape[(e * 2 + b) % 4]] + (12 if e % 3 == 0 else 0)
                            add(buf, lead(mtof(m), beat * 0.8, 0.11 * dens), tb + e * bl / 8, pan=0.4 * math.sin(e))
            if tex in ("full", "medium", "night") or (tex == "build" and pr > 0.35):
                steps = [(0, 1), (2, 0.8), (3, 0.6)] if tex == "full" else [(0, 1), (2, 0.8)]
                for step, v in steps:
                    add(buf, bass(mtof(bs + (7 if step == 3 else 0)), beat * 1.4, 0.55 * dens * v), tb + step * bl / 4)
            if tex == "full" or (tex == "build" and pr > 0.6):
                for e in range(8):
                    add(buf, shaker(0.08, 0.07 if e % 2 else 0.11, rng), tb + e * bl / 8, pan=0.5)
            if tex == "night":
                for e in range(4):
                    add(buf, shaker(0.1, 0.06, rng), tb + (e + 0.5) * bl / 4, pan=0.3)
            if tex in ("pad", "build", "night") or orch:
                v = {"pad": 0.6, "build": 0.35 + 0.5 * pr, "night": 0.3}.get(tex, 0.45) * (1.6 if orch else 1)
                add(buf, strings([mtof(m) for m in voices[:3]] + [mtof(bs + 12)], bl + 0.6, 0.16 * v), tb - 0.1)
            if tex == "full" and b % 2 == 0 and rng.random() < 0.85:
                add(buf, bell(mtof(voices[-1] + 12), 1.2, 0.12), tb + bl * 0.75, pan=0.4)
        if orch and si > 0:
            add(buf, timpani(2.2, 0.55 if mood != "sad" else 0.35), t0)
            if mood in ("playful", "finale", "build", "hope"):
                bs, voices = CH[prog[mood][0]]
                add(buf, brass([mtof(m - 12 + key) for m in voices[:3]], min(4.0, dur * 0.4), 0.2), t0 + 0.1)
        if cue.get("stinger"):
            accent(buf, "stinger" if orch else "bell", t0, key)
    for h in hits:
        accent(buf, h.get("kind", "bell"), float(h["at"]), key)
    # final chord + bell run on the film end
    bs, voices = CH["C"]
    voices = [v + key for v in voices]
    for k, m in enumerate(voices + [72 + key, 76 + key]):
        add(buf, epiano(mtof(m), 3.5, 0.18), total - 3.6 + 0.04 * k)
    for k in range(8):
        add(buf, bell(mtof(84 + key + [0, 4, 7, 12, 7, 4, 12, 16][k]), 1.4, 0.12), total - 3.4 + 0.12 * k,
            pan=0.5 * math.sin(k))
    if orch:
        add(buf, strings([mtof(m) for m in voices] + [mtof(48 + key)], 4.5, 0.4, attack=0.4), total - 4.2)
        add(buf, brass([mtof(m - 12) for m in voices[:3]], 4.0, 0.35), total - 4.0)
        add(buf, timpani(3.0, 0.8), total - 3.6)
    buf = buf[: int(round(total * SR))]
    level_sections(buf, secs)
    echo = np.zeros_like(buf)                            # a hint of room
    d = int(0.19 * SR)
    echo[d:] = buf[:-d] * 0.22
    buf = buf + echo
    fade = np.ones(len(buf))
    fi, fo = min(int(1.5 * SR), len(buf) // 3), min(int(2.0 * SR), len(buf) // 3)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[len(buf) - fo:] = np.linspace(1, 0, fo)
    buf *= fade[:, None]
    buf /= max(np.abs(buf).max(), 1e-9) / 0.8
    return buf.astype(np.float32)


MOOD_LEVEL = {"intro": 0.85, "playful": 1.0, "calm": 0.85, "night": 0.9, "tension": 0.95, "hope": 0.9, "sad": 0.75,
              "build": 1.0, "finale": 1.1}


def level_sections(buf, secs):
    """Even out the loudness of the cues (a thin intro is ~10 dB quieter than a full groove) to MOOD_LEVEL,
    with 0.4 s ramps between cues - so a ducked bed sits at the same level under every scene."""
    if not secs:
        return
    gains = []
    for t0, dur, c in secs:
        seg = buf[int(t0 * SR):int((t0 + dur) * SR)]
        rms = float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0
        gains.append(min(4.0, max(0.25, 0.1 * MOOD_LEVEL[c["mood"]] / rms)) if rms > 1e-6 else 1.0)
    curve = np.empty(len(buf))
    r = int(0.4 * SR)
    for i, (t0, dur, c) in enumerate(secs):
        a, b = int(t0 * SR), len(buf) if i == len(secs) - 1 else int((t0 + dur) * SR)
        curve[a:b] = gains[i]
        if i:
            lo, hi = max(0, a - r // 2), min(len(buf), a + r // 2)
            curve[lo:hi] = np.linspace(gains[i - 1], gains[i], hi - lo)
    buf *= curve[:, None]


def accent(buf, kind, t, key=0):
    if kind == "timpani":
        add(buf, timpani(2.0, 0.6), t)
    elif kind == "stinger":
        add(buf, timpani(2.0, 0.6), t)
        add(buf, brass([mtof(m + key) for m in (48, 52, 55)], 1.6, 0.3), t - 0.05)
    else:
        for k, m in enumerate((84, 88, 91, 96)):
            add(buf, bell(mtof(m + key), 1.0, 0.13), t + 0.06 * k, pan=0.3)


# ------------------------------------------------------------------ ElevenLabs Music (opt-in)

BASE_PROMPT = ("Instrumental only, no vocals. Cartoon underscore for a short animated film, clean modern mix, "
               "leaves room for dialogue. ")
MOOD_PROMPTS = {
    "intro": "Opening cue, curious and energetic: pizzicato strings and marimba ostinato, light drums, playful "
             "glockenspiel melody, building anticipation.",
    "playful": "Main groove, bouncy and mischievous: staccato pizzicato strings, marimba riffs, light drums and claps, "
               "walking bass, glockenspiel sparkles, steady and catchy so it can run under several scenes.",
    "calm": "Calm and warm: soft piano and plucked strings, gentle and unhurried, light and friendly.",
    "night": "Late-night mood, cool synth groove: soft synth bass, arpeggiated retro synths, crisp light drums.",
    "tension": "Comic suspense: ticking pizzicato, sneaky staccato bassoon and low strings, rising tension with "
               "comedic stingers, nervous but funny.",
    "hope": "Warm optimistic turn: plucked acoustic guitar, marimba, soft claps, gentle glockenspiel melody, hopeful.",
    "sad": "Short gently melancholic interlude, not depressing: solo clarinet in a minor key over soft pizzicato.",
    "build": "Uplifting build: marimba and pizzicato ostinato, drums and bass join, strings and brass rise, triumphant.",
    "finale": "Grand finale, joyful: full band with strings, marimba, glockenspiel, punchy drums, brass fanfare stabs, "
              "ends with a clear final orchestra stinger hit and a short ring-out.",
}


def _key():
    return os.environ.get("ELEVENLABS_API_KEY")


def eleven_prompt(mood, extra=""):
    return BASE_PROMPT + (extra.strip() + " " if extra else "") + MOOD_PROMPTS[mood]


def eleven_fetch(prompt, seconds, dst):
    """Request one cue; writes dst (.mp3) + dst.json (prompt, length, request id). The key is never printed."""
    import urllib.error
    import urllib.request
    key = _key()
    if not key:
        raise SystemExit("ElevenLabs: set the environment variable ELEVENLABS_API_KEY (never stored in a file)")
    body = {"prompt": prompt, "music_length_ms": int(max(10, min(300, seconds)) * 1000), "model_id": "music_v1",
            "force_instrumental": True}
    req = urllib.request.Request("https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192",
                                 data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    print(f"  ElevenLabs Music: requesting {body['music_length_ms'] / 1000:.0f} s -> {dst.name}", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
            info = {k: v for k, v in r.headers.items() if k.lower() in ("request-id", "song-id", "character-cost")}
    except urllib.error.HTTPError as err:
        raise SystemExit(f"ElevenLabs: HTTP {err.code} - {err.read()[:400].decode('utf-8', 'replace')}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    dst.with_suffix(".json").write_text(json.dumps({"prompt": prompt, "seconds": seconds, "response": info},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")


def _load_cue(path, sr):
    from media import ffmpeg
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    hop = int(0.02 * sr)
    rms = np.sqrt(np.convolve((y ** 2).mean(1), np.ones(hop) / hop, "same"))
    loud = np.nonzero(rms > 10 ** (-45 / 20))[0]
    if not len(loud):
        raise SystemExit(f"cue {path} is silent")
    a, end = max(0, loud[0] - int(0.01 * sr)), loud[-1]
    y = y[a:min(len(y), end + int(0.3 * sr))]
    end -= a
    y = y / max(1e-9, np.sqrt(np.mean(y[:end] ** 2))) * 0.12
    try:
        import librosa
        _, beats = librosa.beat.beat_track(y=y.mean(1).astype(np.float32), sr=sr, units="samples")
        bars = np.asarray(beats[::4]) if len(beats) >= 8 else np.arange(0, len(y), 2 * sr)
    except Exception:
        bars = np.arange(0, len(y), 2 * sr)
    la = int(bars[min(2, len(bars) - 1)])
    cand = bars[bars < end - 1.5 * sr]
    lb = int(cand[-1]) if len(cand) else end
    if lb - la < sr:                                    # too short to loop between bars: loop the whole cue
        la, lb = 0, end
    return y, bars, la, lb, end


def _stretch(c, start, n, sr):
    y, bars, la, lb, end = c
    xf = int(0.12 * sr)
    ramp = np.linspace(0, 1, xf)[:, None]
    stop = len(y) if start + n <= len(y) else lb
    out = y[start:stop].copy()
    looped = False
    while len(out) < n:
        looped = True
        piece = y[la:lb]
        out[-xf:] = out[-xf:] * (1 - ramp) + piece[:xf] * ramp
        out = np.concatenate([out, piece[xf:]])
    pos = lb - (len(out) - n) if looped else start + n
    return out[:n], pos, looped


def eleven_score(cues, total, cache_dir, fetch=False, extra="", sr=48000):
    secs = sections(cues, total)
    parts = []                                          # merge consecutive sections of the same mood
    for t0, dur, c in secs:
        if parts and parts[-1]["mood"] == c["mood"]:
            parts[-1]["dur"] += dur
        else:
            parts.append({"mood": c["mood"], "t0": t0, "dur": dur})
    need = {}
    for p in parts:
        need[p["mood"]] = need.get(p["mood"], 0) + p["dur"]
    files = {}
    for mood, secs_needed in need.items():
        prompt = eleven_prompt(mood, extra)
        h = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:8]
        f = Path(cache_dir) / f"{mood}_{h}.mp3"
        if not f.exists():
            if not fetch:
                raise SystemExit(f"ElevenLabs cue '{mood}' is not cached ({f.name}) - add --fetch to request it "
                                 "(costs credits; the prompt text is sent to ElevenLabs)")
            eleven_fetch(prompt, min(120, secs_needed + 6), f)
        files[mood] = f
    buf = np.zeros((int(round(total * sr)), 2))
    fade_out, fade_in = int(0.35 * sr), int(0.03 * sr)
    cont, cache = {}, {}
    for i, p in enumerate(parts):
        c = cache.setdefault(p["mood"], _load_cue(files[p["mood"]], sr))
        y, bars, la, lb, end = c
        last = i == len(parts) - 1
        n = int(round(p["dur"] * sr)) + (0 if last else fade_out)
        if last and end >= n:                          # the cue's own ending on the film end
            stop = min(len(y), end + int(0.3 * sr))
            seg, fi = y[max(0, stop - n):stop].copy(), int(0.2 * sr)
        else:
            start = 0
            if p["mood"] in cont:
                rest = bars[(bars >= cont[p["mood"]]) & (bars < lb)]
                start = int(rest[0]) if len(rest) else la
            seg, cont[p["mood"]], _ = _stretch(c, start, n, sr)
            fi = fade_in if start == 0 else int(0.15 * sr)
        seg[:fi] *= np.linspace(0, 1, fi)[:, None]
        if not last:
            seg[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 1.5
        a = int(round(p["t0"] * sr))
        b = min(len(buf), a + len(seg))
        buf[a:b] += seg[: b - a]
    buf /= max(1e-9, np.abs(buf).max()) / 0.8
    return buf.astype(np.float32)


# ------------------------------------------------------------------ CLI

def write_wav(path, y, sr):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


def cues_from_plan(plan_path, version=None):
    """(cues, total seconds, score options) from a cut plan, using cut.py's timeline (exact shot starts)."""
    import cut
    plan = cut.load_plan(plan_path, version)
    tl = cut.timeline(plan)
    m = plan.get("music") if isinstance(plan.get("music"), dict) else {}
    opts = dict(m.get("score") or {}) if isinstance(m.get("score"), dict) else {}
    return cut.score_cues(plan, tl, opts), tl["frames"] / tl["fps"], opts


def main():
    ap = argparse.ArgumentParser(description="Film score for films without a song (numpy synthesis or ElevenLabs).")
    ap.add_argument("--plan", help="cut plan (cut.py) - cues and length from its timeline")
    ap.add_argument("--version")
    ap.add_argument("--cues", help="cues.json: a list of cues (or {\"cues\": [...], ...})")
    ap.add_argument("--duration", type=float, help="film length in seconds (with --cues)")
    ap.add_argument("-o", "--out")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--style", choices=["light", "orchestral"])
    ap.add_argument("--elevenlabs", action="store_true", help="ElevenLabs Music cues instead of the synthesis (opt-in)")
    ap.add_argument("--fetch", action="store_true", help="with --elevenlabs: request missing cues (costs credits)")
    a = ap.parse_args()
    if a.plan:
        cues, total, opts = cues_from_plan(a.plan, a.version)
        base = Path(a.plan).resolve().parent
    elif a.cues and a.duration:
        d = json.loads(Path(a.cues).read_text(encoding="utf-8"))
        opts = d if isinstance(d, dict) else {}
        cues, total = (d.get("cues", []) if isinstance(d, dict) else d), a.duration
        base = Path(a.cues).resolve().parent
    else:
        raise SystemExit("score.py --plan cut.json   or   score.py --cues cues.json --duration S")
    seed = a.seed if a.seed is not None else int(opts.get("seed", 0))
    style = a.style or opts.get("style", "light")
    out = Path(a.out) if a.out else base / "music.wav"
    if a.elevenlabs:
        y = eleven_score(cues, total, base / "cache" / "music_cues", a.fetch, opts.get("prompt", ""))
        how = "ElevenLabs Music cues"
    else:
        y = compose(cues, total, seed, style, SR, opts.get("hits", ()))
        how = f"synthesis, seed {seed}: {json.dumps(LAST, ensure_ascii=False)}"
    write_wav(out, y, SR)
    for t0, dur, c in sections(cues, total):
        print(f"  {t0:7.2f} s  {c['mood']:8s} {dur:6.2f} s{'  stinger' if c.get('stinger') else ''}")
    print(f"-> {out} ({len(y) / SR:.3f} s, {how})")


if __name__ == "__main__":
    main()
