# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Text-to-speech with a FIXED voice per character, checked by Whisper (building block of the animation-studio plugin).

Engines (first available one of a cast entry and its "fallback" list wins):
  qwen    Qwen3-TTS (best, final choice for character voices). Needs config `tts_python` = python of a venv with
          `qwen-tts` + torch (CUDA). Each character has a REFERENCE sample; every line is cloned from it with the Base
          model, so the character sounds the same in every film. A missing reference is designed once with
          VoiceDesign from the English description ("design") - see `design` below. Takes the GPU lock.
  piper   Piper ONNX voices (CPU, fast, deterministic). Config `piper` = piper executable, `piper_voices` = folder
          with <model>.onnx + .onnx.json.
  system  Windows speech (System.Speech, SSML prosody). Always there on Windows; robotic but instant.
  elevenlabs  ElevenLabs cloud TTS (optional, opt-in per character): {"engine": "elevenlabs", "voice_id": "<id from
          your ElevenLabs voice library>", "model": "eleven_multilingual_v2", "stability": 0.5, "similarity": 0.75,
          "style": 0.0}. The API key is read ONLY from the environment variable ELEVENLABS_API_KEY (never stored in a
          file, never printed). The line text is sent to ElevenLabs - only use it when the user chose it for a figure.
          Use designed or library voices, never a clone of a real person.
Voices are described by their character only - never clone a real voice actor.

Cast: assets/cast.json (tim, lia, computer, narrator) + project.json "voices" (overrides / new characters, same keys):
  {"engine": "qwen", "design": "<English voice description>", "sample_text": "<a sentence in the film language>",
   "reference": "voices/<who>.wav" (project folder first, then this skill's assets),
   "pitch": 1.0 (resample factor, tempo kept), "ssml_pitch": "+25%" (system), "model": "<piper model>",
   "fx": "screen" | "radio" | "small" | "<ffmpeg filter>", "fallback": [ {...}, ... ]}
Post-processing for every line: pitch, fx, silence trimmed at both ends, level normalised (-20 dBFS RMS, peak -1 dB).
Whisper check: every line is transcribed (hear.py); lines under 0.8 similarity are taken again with another seed
(qwen; piper/system are deterministic and only warned about). The best take wins.

Python API (talking-character uses it):
    import voice
    res = voice.speak([{"who": "tim", "text": "Hallo!", "out": "lines/01.wav"}], project_dir=".", seed=7)
    # -> [{"who", "text", "out", "engine", "score", "heard", "words": [{"word", "t", "end"}], "duration"}]
    # optional per item: "slot": 2.4 (fit the line into 2.4 s) or "tempo": 1.08 (8 % faster), "tail": 0.28 -
    # pitch-neutral, pauses tightened, words re-timed (tempo.py); the result then has "tempo": {...}
CLI:
    python voice.py say tim "Hallo Computer!" -o hallo.wav [--project .] [--engine system] [--no-check]
    python voice.py design tim [--n 3] [--project .]     candidates voices/tim_1.wav ... (+ Whisper score, pitch)
    python voice.py pick tim 2 [--project .] [--to skill]   candidate -> voices/tim.wav (project or skill assets)
    python voice.py list [--project .]                     cast, engine per character, reference found?
    python voice.py tempo line.wav -o fit.wav --slot 2.4   pitch-neutral fit into a slot (or --factor 1.08); tempo.py
    python voice.py say tim "..." -o x.wav --slot 2.4      speak and fit in one go
"""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402
from media import decode, ffmpeg  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]
HERE = SKILL / "scripts"
CAST = SKILL / "assets" / "cast.json"
SR = 44100
LANG_NAMES = {"de": "German", "en": "English", "fr": "French", "es": "Spanish", "it": "Italian", "ja": "Japanese",
              "zh": "Chinese", "ko": "Korean", "ru": "Russian", "pt": "Portuguese"}
GOOD = 0.8
PAD = (0.03, 0.06)          # seconds of air kept before / after the voice of every line


# ------------------------------------------------------------------ cast

def cast(project_dir=None):
    """{who: entry} - plugin cast merged with project.json "voices" (entries of the same name are updated)."""
    data = json.loads(CAST.read_text(encoding="utf-8"))
    voices = {k: dict(v) for k, v in data["voices"].items()}
    if project_dir and (Path(project_dir) / "project.json").exists():
        p = json.loads((Path(project_dir) / "project.json").read_text(encoding="utf-8"))
        for k, v in (p.get("voices") or {}).items():
            voices[k] = {**voices.get(k, {}), **v}
    return voices


def fx_filter(name):
    if not name:
        return None
    presets = json.loads(CAST.read_text(encoding="utf-8")).get("fx", {})
    return presets.get(name, name)


def available(engine):
    if engine == "qwen":
        p = config.get("tts_python")
        return bool(p and Path(p).exists())
    if engine == "piper":
        p, d = config.get("piper"), config.get("piper_voices")
        return bool(p and (Path(p).exists() or shutil.which(p)) and d and Path(d).is_dir())
    if engine == "system":
        return os.name == "nt"
    if engine == "elevenlabs":
        return bool(os.environ.get("ELEVENLABS_API_KEY"))
    return False


def choose(entry, force=None):
    """The entry (with fallback fields merged) of the first available engine."""
    base = {k: v for k, v in entry.items() if k != "fallback"}
    options = [base] + [{**{k: v for k, v in base.items() if k not in ("engine", "pitch", "ssml_pitch", "model",
                                                                      "speaker", "voice")}, **f}
                        for f in entry.get("fallback", [])]
    force = force or os.environ.get("TTS_ENGINE")
    if force:
        options = [o for o in options if o.get("engine") == force] or [{**base, "engine": force}]
    for o in options:
        if available(o.get("engine", "qwen")):
            return o
    raise SystemExit("no text-to-speech engine available: set `tts_python` (Qwen3-TTS venv) or `piper` + `piper_voices` "
                     "with studio-core check_tools.py --set, or run on Windows (system voices)")


def reference_path(who, entry, project_dir):
    rel = entry.get("reference") or f"voices/{who}.wav"
    cands = []
    if project_dir:
        cands.append(Path(project_dir) / rel)
    cands.append(SKILL / "assets" / rel)
    for c in cands:
        if c.exists():
            return c
    return None


# ------------------------------------------------------------------ engines

def run_worker(mode, items):
    py = config.need("tts_python")
    with tempfile.TemporaryDirectory() as d:
        job = Path(d) / "job.json"
        job.write_text(json.dumps({"mode": mode, "items": items}, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([py, str(HERE / "tts_worker.py"), str(job)], env=env)
        if r.returncode != 0 or not job.with_suffix(".out.json").exists():
            raise SystemExit(f"Qwen3-TTS worker failed (exit {r.returncode})")


def qwen_lines(jobs, project_dir, language):
    """jobs: [(item, entry, raw_path, seed)] -> raw files (clone from each character's reference)."""
    items = []
    for it, e, raw, seed in jobs:
        ref = reference_path(it["who"], e, project_dir)
        if ref is None:
            ref = design(it["who"], e, project_dir, n=2, language=language)
        items.append({"text": it["speak"], "language": LANG_NAMES.get(language, language), "out": str(raw), "seed": seed,
                      "ref_audio": str(ref), "ref_text": e["sample_text"]})
    if items:
        run_worker("clone", items)


def piper_line(text, e, raw):
    model = Path(config.need("piper_voices")) / (e.get("model", "de_DE-thorsten-high") + ".onnx")
    cmd = [config.need("piper"), "-m", str(model), "-f", str(raw)]
    if e.get("speaker") is not None:
        cmd += ["-s", str(e["speaker"])]
    if e.get("length_scale"):
        cmd += ["--length-scale", str(e["length_scale"])]
    subprocess.run(cmd, input=text.encode("utf-8"), check=True, capture_output=True)


def system_line(text, e, raw, language):
    """Windows System.Speech with SSML prosody (pitch/rate). The voice is matched by part of its name."""
    from xml.sax.saxutils import escape
    lang = {"de": "de-DE", "en": "en-US"}.get(language, language)
    attrs = "".join(f" {k}='{e[f'ssml_{k}']}'" for k in ("pitch", "rate") if e.get(f"ssml_{k}"))   # rate='0%' = slowest!
    body = f"<prosody{attrs}>{escape(text)}</prosody>" if attrs else escape(text)
    ssml = f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}'>{body}</speak>"
    with tempfile.TemporaryDirectory() as d:
        sf = Path(d) / "line.ssml"
        sf.write_text(ssml, encoding="utf-8")
        ps = (
            "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -like '*{e.get('voice', '')}*' -and "
            f"$_.VoiceInfo.Culture.Name -like '{lang[:2]}*' }} | Select-Object -First 1; "
            f"if (-not $v) {{ $v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -like '*{e.get('voice', '')}*' }} | Select-Object -First 1 }}; "
            "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
            f"$s.SetOutputToWaveFile('{raw}'); $s.SpeakSsml([IO.File]::ReadAllText('{sf}')); $s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True)


def elevenlabs_line(text, e, raw, seed=0, language="de"):
    """ElevenLabs text-to-speech -> raw wav. Key from ELEVENLABS_API_KEY only; errors never echo the key."""
    import urllib.error
    import urllib.request
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key or not e.get("voice_id"):
        raise SystemExit("elevenlabs: set the environment variable ELEVENLABS_API_KEY and a \"voice_id\" for the figure")
    body = {"text": text, "model_id": e.get("model", "eleven_multilingual_v2"), "seed": int(seed) % 4294967295,
            "voice_settings": {"stability": e.get("stability", 0.5), "similarity_boost": e.get("similarity", 0.75),
                               "style": e.get("style", 0.0), "use_speaker_boost": True}}
    if e.get("model", "").startswith(("eleven_turbo_v2_5", "eleven_flash_v2_5")):
        body["language_code"] = language
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{e['voice_id']}?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        mp3 = urllib.request.urlopen(req, timeout=120).read()
    except urllib.error.HTTPError as err:
        raise SystemExit(f"elevenlabs: HTTP {err.code} - {err.read()[:300].decode('utf-8', 'replace')}")
    tmp = Path(raw).with_suffix(".mp3")
    tmp.write_bytes(mp3)
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(tmp), "-ac", "1", "-ar", str(SR), str(raw)], check=True)
    tmp.unlink(missing_ok=True)


# ------------------------------------------------------------------ post-processing

def write_wav(path, y, sr=SR):
    import numpy as np
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


def post(raw, out, e):
    """pitch + fx (ffmpeg) -> trim silence at both ends, normalise -> out (44.1 kHz mono). Returns seconds."""
    import numpy as np
    filt = []
    p = float(e.get("pitch", 1.0))
    if abs(p - 1.0) > 1e-3:
        r = wave.open(str(raw)).getframerate()
        filt += [f"asetrate={round(r * p)}", f"aresample={r}", f"atempo={1 / p:.5f}"]
    f = fx_filter(e.get("fx"))
    if f:
        filt.append(f)
    tmp = Path(out).with_suffix(".post.wav")
    cmd = [ffmpeg(), "-y", "-v", "error", "-i", str(raw)] + (["-af", ",".join(filt)] if filt else []) + \
          ["-ac", "1", "-ar", str(SR), str(tmp)]
    subprocess.run(cmd, check=True)
    y = decode(tmp, SR)
    tmp.unlink(missing_ok=True)
    hop = int(0.01 * SR)
    k = len(y) // hop
    if k:
        rms = np.sqrt(np.mean(y[: k * hop].reshape(k, hop) ** 2, axis=1))
        on = np.where(20 * np.log10(rms + 1e-9) > 20 * np.log10(rms.max() + 1e-9) - 40)[0]
        if len(on):
            a, b = max(0, on[0] * hop - int(PAD[0] * SR)), min(len(y), (on[-1] + 1) * hop + int(PAD[1] * SR))
            y = y[a:b]
    loud = np.sqrt(np.mean(y[np.abs(y) > 0.02 * np.abs(y).max()] ** 2)) if len(y) else 0
    if loud > 0:
        y = y * min(10 ** (-20 / 20) / loud, 10 ** (-1 / 20) / (np.abs(y).max() + 1e-9))
    n = min(int(0.008 * SR), len(y) // 2)
    if n:
        y[:n] *= np.linspace(0, 1, n)
        y[-n:] *= np.linspace(1, 0, n)
    write_wav(out, y)
    return len(y) / SR


# ------------------------------------------------------------------ Whisper check

def hear(paths_texts, language):
    """[(path, text)] -> {path: {"heard", "score", "words"}} (hear.py in the GPU python or via uv on the CPU)."""
    if not paths_texts:
        return {}
    from config import gpu_runner as runner
    with tempfile.TemporaryDirectory() as d:
        job = Path(d) / "hear.json"
        job.write_text(json.dumps([{"path": str(p), "text": t, "language": language} for p, t in paths_texts],
                                  ensure_ascii=False), encoding="utf-8")
        subprocess.run(runner(["faster-whisper", "numpy"]) + [str(HERE / "hear.py"), str(job)], check=True,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return json.loads(job.with_suffix(".out.json").read_text(encoding="utf-8"))


def spoken(text, pronounce=None):
    """Text the engine reads: stage directions removed, pronunciation fixes applied (subtitles keep the original)."""
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]|\*[^*]*\*", " ", text)
    for a, b in (pronounce or {}).items():
        t = re.sub(rf"\b{re.escape(a)}\b", b, t)
    return " ".join(t.replace("...", ",").replace("…", ",").split())


# ------------------------------------------------------------------ main API

TALK = "Natural spontaneous conversation, fluent and connected, not read aloud. "


def directed_lines(jobs, language):
    """jobs: [(item, entry, raw_path, seed)] with item["direction"] -> raw files. VoiceDesign speaks the line itself:
    the character's description + how to say THIS line. Livelier than a clone of the neutral reference, but the voice
    is designed anew for every line and wanders a little (speak() reports lines whose pitch falls out)."""
    items = []
    for it, e, raw, seed in jobs:
        if not e.get("design"):
            raise SystemExit(f"'{it['who']}' has no \"design\" (English voice description) - a directed line needs it")
        items.append({"text": it["speak"], "language": LANG_NAMES.get(language, language), "out": str(raw), "seed": seed,
                      "instruct": e["design"].strip() + " " + TALK + it["direction"].strip()})
    if items:
        run_worker("design", items)


def pitch_outliers(rows, limit=0.15):
    """rows: [(who, pitch_hz)] -> indices of lines more than `limit` away from their character's median pitch
    (a line at 154 Hz among 168-198 Hz sounded like another person - the user took it for the sat-nav)."""
    by = {}
    for i, (who, hz) in enumerate(rows):
        if hz:
            by.setdefault(who, []).append((hz, i))
    out = []
    for who, v in by.items():
        if len(v) < 3:
            continue
        med = sorted(h for h, _ in v)[len(v) // 2]
        out += [i for h, i in v if abs(h - med) / med > limit]
    return sorted(out)


def speak(items, project_dir=None, seed=0, check=True, retakes=2, language="de", engine=None, pronounce=None):
    """items: [{"who", "text", "out"}] -> results (see module doc). Same seed -> same takes."""
    voices = cast(project_dir)
    work = Path(tempfile.mkdtemp(prefix="voice_"))
    res = []
    for i, it in enumerate(items):
        if it["who"] not in voices:
            raise SystemExit(f"no voice for '{it['who']}' - add it to project.json \"voices\" (see voice skill)")
        e = choose(voices[it["who"]], engine)
        res.append({**it, "speak": spoken(it["text"], pronounce), "entry": e, "engine": e.get("engine", "qwen"),
                    "seed": seed * 1000 + i, "score": None, "take": 0})
    todo = list(range(len(res)))
    best = {}
    for take in range(retakes + 1):
        q, qd = [], []
        for i in todo:
            r = res[i]
            raw = work / f"raw_{i:03d}_{take}.wav"
            r["raw"] = raw
            if r["engine"] == "qwen" and r.get("direction"):      # one seed per character: the voice wanders less
                qd.append((r, r["entry"], raw, seed * 1000 + zlib.crc32(r["who"].encode()) % 997 + 7919 * take))
            elif r["engine"] == "qwen":
                q.append((r, r["entry"], raw, r["seed"] + 7919 * take))
            elif r["engine"] == "piper":
                piper_line(r["speak"], r["entry"], raw)
            elif r["engine"] == "elevenlabs":
                elevenlabs_line(r["speak"], r["entry"], raw, r["seed"] + 7919 * take, language)
            else:
                system_line(r["speak"], r["entry"], raw, language)
        qwen_lines(q, project_dir, language)
        directed_lines(qd, language)
        for i in todo:
            r = res[i]
            cand = work / f"take_{i:03d}_{take}.wav"
            r["duration"] = round(post(r["raw"], cand, r["entry"]), 3)
            r["cand"] = cand
        heard = hear([(res[i]["cand"], res[i]["speak"]) for i in todo], language) if check else {}
        for i in todo:
            r = res[i]
            h = heard.get(str(r["cand"]), {"heard": "", "score": None, "words": []})
            if i not in best or (h["score"] or 0) > (best[i]["score"] or 0):
                best[i] = {"cand": r["cand"], "duration": r["duration"], "take": take, **h}
        todo = [i for i in todo if check and res[i]["engine"] in ("qwen", "elevenlabs") and (best[i]["score"] or 0) < GOOD]
        if not todo:
            break
        print(f"  Whisper: {len(todo)} line(s) under {GOOD} - new take", flush=True)
    out = []
    for i, r in enumerate(res):
        b = best[i]
        Path(r["out"]).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(b["cand"], r["out"])
        extra = {}
        if r.get("slot") or r.get("tempo"):                 # optional: fit the line into a slot (tempo.py)
            import tempo
            t = tempo.fit(r["out"], r["out"], slot=r.get("slot"), factor=r.get("tempo"), words=b["words"],
                          tail=float(r.get("tail", 0.0)))
            b = {**b, "duration": t["after"], "words": t["words"]}
            extra["tempo"] = {k: v for k, v in t.items() if k != "words"}
        if r.get("direction") and r["engine"] == "qwen":
            extra["direction"], extra["pitch_hz"] = r["direction"], pitch_hz(r["out"])
        out.append({"who": r["who"], "text": r["text"], "spoken": r["speak"], "out": str(r["out"]), "engine": r["engine"],
                    "take": b["take"], "score": b["score"], "heard": b["heard"], "words": b["words"],
                    "duration": b["duration"], **extra})
        flag = "" if b["score"] is None or b["score"] >= GOOD else "   <-- CHECK"
        print(f"  {r['who']:9s} {r['engine']:6s} {b['duration']:5.2f} s  heard {b['score'] if b['score'] is not None else '-'}"
              f"  {r['speak'][:60]}{flag}", flush=True)
    shutil.rmtree(work, ignore_errors=True)
    for i in pitch_outliers([(o["who"], o.get("pitch_hz")) for o in out]):
        o = out[i]
        o["pitch_outlier"] = True
        print(f"  NOTE {o['who']}: \"{o['spoken'][:40]}\" at {o['pitch_hz']} Hz is far from this character's other lines - "
              "it may sound like another person; take it again (other seed / direction) or speak it as one item with "
              "the sentence before it", flush=True)
    return out


def pitch_hz(path):
    """Median pitch (autocorrelation) - to tell candidate voices apart."""
    import numpy as np
    y = decode(path, 16000)
    w, res = 640, []
    for i in range(0, len(y) - w, w // 2):
        f = y[i:i + w] - y[i:i + w].mean()
        if np.sqrt((f ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(f, f, "full")[w - 1:]
        lo, hi = 16000 // 400, 16000 // 60
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.3 * ac[0]:
            res.append(16000 / k)
    return round(float(np.median(res))) if res else 0


def design(who, entry, project_dir=None, n=2, language="de", seed=1):
    """VoiceDesign: n candidate references for a character -> voices/<who>_<k>.wav (+ voices/candidates.json);
    the clearest one (Whisper) becomes voices/<who>.wav unless it exists. Returns the reference path."""
    base = Path(project_dir) if project_dir else SKILL / "assets"
    vdir = base / "voices"
    vdir.mkdir(parents=True, exist_ok=True)
    if not entry.get("design") or not entry.get("sample_text"):
        raise SystemExit(f"voice '{who}' has no reference and no 'design' + 'sample_text' to make one")
    raws = [vdir / f"{who}_{k}.wav" for k in range(1, n + 1)]
    print(f"  designing the voice of {who} ({n} candidates, Qwen3-TTS VoiceDesign)", flush=True)
    run_worker("design", [{"text": entry["sample_text"], "language": LANG_NAMES.get(language, language),
                           "instruct": entry["design"], "out": str(r), "seed": seed * 100 + k}
                          for k, r in enumerate(raws, 1)])
    for r in raws:      # trim + normalise, no fx (fx is applied to every line later)
        post(r, r, {})
    heard = hear([(r, entry["sample_text"]) for r in raws], language)
    info_f = vdir / "candidates.json"
    info = json.loads(info_f.read_text(encoding="utf-8")) if info_f.exists() else {}
    for r in raws:
        h = heard.get(str(r), {})
        info[r.name] = {"who": who, "score": h.get("score"), "heard": h.get("heard"), "pitch_hz": pitch_hz(r),
                        "seconds": round(len(decode(r, 16000)) / 16000, 2), "design": entry["design"]}
        print(f"  {r.name}: Whisper {info[r.name]['score']}, {info[r.name]['pitch_hz']} Hz, {info[r.name]['seconds']} s")
    info_f.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    ref = vdir / f"{who}.wav"
    if not ref.exists():
        bestr = best_candidate(raws, info, entry["design"])
        shutil.copy(bestr, ref)
        print(f"  -> {ref} (from {bestr.name}; listen and change with `voice.py pick {who} <k>`)")
    return ref


_MALE = re.compile(r"\b(male|man|men|boy|guy|gentleman|baritone|bass|m\u00e4nnlich\w*|mann|herr|tenor)\b", re.I)
_FEMALE = re.compile(r"\b(female|woman|women|girl|lady|soprano|alto|weiblich\w*|frau|m\u00e4dchen)\b", re.I)


def best_candidate(raws, info, design):
    """The clearest candidate (Whisper) - but among the ones heard about as well (within 0.05 of the best), one whose
    pitch fits a gender the design names (user test: a "man" design got a 302 Hz take that sounded like a woman):
    male about 85-180 Hz, female about 165-300 Hz. Without such a word: just the clearest."""
    sc = lambda r: info[r.name]["score"] or 0
    top = max(sc(r) for r in raws)
    near = [r for r in raws if sc(r) >= top - 0.05]
    m, f = bool(_MALE.search(design)), bool(_FEMALE.search(design))
    if m != f:
        lo, hi = (85, 180) if m else (165, 300)
        fits = [r for r in near if info[r.name].get("pitch_hz") and lo <= info[r.name]["pitch_hz"] <= hi]
        if fits:
            return max(fits, key=sc)
        print(f"  (no candidate with a {'male' if m else 'female'} pitch {lo}-{hi} Hz - taking the clearest; "
              "make more with --n 4 or adjust the design)")
    return max(raws, key=sc)


# ------------------------------------------------------------------ CLI

# ------------------------------------------------------------------ a whole dialogue as one take (ElevenLabs)

def dialogue(turns, out, project_dir=None, seed=0, language="de", model="eleven_v3", split=None, dry_run=False):
    """turns: [{"who", "text", "name"?}] -> ONE take in which the cloud model plays the exchange itself (ElevenLabs
    Text to Dialogue; stage tags in square brackets inside the text, e.g. "[deadpan] ..."). Every speaker's cast entry
    needs {"engine": "elevenlabs", "voice_id": "..."}. Writes out (mp3) and out.json with the time of every turn;
    split = folder for one wav per turn (<name>.wav; the pauses stay inside the pieces, so played back to back it is
    the take as spoken). Cloud: the text leaves the machine and costs credits - ask the user first."""
    import base64
    import urllib.error
    import urllib.request
    voices = cast(project_dir)
    inputs = []
    for t in turns:
        e = voices.get(t["who"]) or {}
        if not e.get("voice_id"):
            raise SystemExit(f"dialogue: '{t['who']}' has no \"voice_id\" in project.json \"voices\"")
        inputs.append({"text": t["text"], "voice_id": e["voice_id"]})
    body = {"inputs": inputs, "model_id": model, "language_code": language, "seed": int(seed) % 4294967295}
    if dry_run:
        return body
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("dialogue: set the environment variable ELEVENLABS_API_KEY")
    req = urllib.request.Request("https://api.elevenlabs.io/v1/text-to-dialogue/with-timestamps?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as err:
        raise SystemExit(f"elevenlabs: HTTP {err.code} - {err.read()[:300].decode('utf-8', 'replace')}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(d["audio_base64"]))
    segs = []
    for sgm in d.get("voice_segments") or []:
        t = turns[sgm["dialogue_input_index"]]
        segs.append({"who": t["who"], "name": t.get("name") or f"{len(segs) + 1:02d}", "text": t["text"],
                     "from": round(sgm["start_time_seconds"], 3), "to": round(sgm["end_time_seconds"], 3)})
    out.with_suffix(".json").write_text(json.dumps({"model": model, "seed": seed, "turns": segs}, ensure_ascii=False,
                                                   indent=1), encoding="utf-8")
    if split:
        Path(split).mkdir(parents=True, exist_ok=True)
        for g in segs:
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-ss", f"{g['from']:.3f}", "-to", f"{g['to']:.3f}", "-i", str(out),
                            "-ac", "1", "-ar", str(SR), str(Path(split) / f"{g['name']}.wav")], check=True)
    return segs


def main():
    ap = argparse.ArgumentParser(description="Text-to-speech with a fixed voice per character.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("say")
    s.add_argument("who")
    s.add_argument("text")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--project")
    s.add_argument("--engine", choices=["qwen", "piper", "system", "elevenlabs"])
    s.add_argument("--language", default="de")
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--no-check", action="store_true")
    s.add_argument("--slot", type=float, help="fit the line into this many seconds (pitch-neutral, tempo.py)")
    s.add_argument("--tempo", type=float, help="speed factor (>1 faster) instead of --slot")
    s.add_argument("--direction", help="how to say it, in English (Qwen VoiceDesign speaks the line itself; livelier, "
                                       "the voice wanders a little)")
    tp = sub.add_parser("tempo", help="pitch-neutral tempo change of a wav to fit a slot (tempo.py)")
    import tempo
    tempo.add_args(tp)
    d = sub.add_parser("design")
    d.add_argument("who")
    d.add_argument("--n", type=int, default=3)
    d.add_argument("--project")
    d.add_argument("--language", default="de")
    d.add_argument("--seed", type=int, default=1)
    pk = sub.add_parser("pick")
    pk.add_argument("who")
    pk.add_argument("k", type=int)
    pk.add_argument("--project")
    pk.add_argument("--to", choices=["project", "skill"], default="project")
    ls = sub.add_parser("list")
    ls.add_argument("--project")
    dg = sub.add_parser("dialogue", help="a whole dialogue as ONE ElevenLabs take with several speakers (cloud, opt-in)")
    dg.add_argument("turns", help='JSON file: [{"who": "oliver", "text": "[cheerful] ...", "name": "s02"}, ...]')
    dg.add_argument("-o", "--out", required=True, help="the take (mp3); the times go to <out>.json")
    dg.add_argument("--project")
    dg.add_argument("--split", help="folder for one wav per turn")
    dg.add_argument("--language", default="de")
    dg.add_argument("--seed", type=int, default=0)
    dg.add_argument("--dry-run", action="store_true", help="print the request, send nothing")
    a = ap.parse_args()
    if a.cmd == "say":
        item = {"who": a.who, "text": a.text, "out": a.out}
        if a.slot or a.tempo:
            item.update({k: v for k, v in (("slot", a.slot), ("tempo", a.tempo)) if v})
        if a.direction:
            item["direction"] = a.direction
        r = speak([item], a.project, a.seed, not a.no_check, language=a.language, engine=a.engine)[0]
        print(json.dumps({k: r[k] for k in ("out", "engine", "duration", "score", "heard", "tempo", "direction", "pitch_hz") if k in r},
                         ensure_ascii=False))
    elif a.cmd == "tempo":
        import tempo
        tempo.run_args(a)
    elif a.cmd == "dialogue":
        turns = json.loads(Path(a.turns).read_text(encoding="utf-8"))
        r = dialogue(turns, a.out, a.project, a.seed, a.language, split=a.split, dry_run=a.dry_run)
        if a.dry_run:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            for g in r:
                print(f"  {g['name']:6s} {g['who']:9s} {g['from']:6.2f}-{g['to']:6.2f}  {g['text'][:60]}")
            print("->", a.out)
    elif a.cmd == "design":
        e = cast(a.project).get(a.who)
        if not e:
            raise SystemExit(f"'{a.who}' is not in the cast - add design + sample_text to project.json \"voices\"")
        design(a.who, e, a.project, a.n, a.language, a.seed)
    elif a.cmd == "pick":
        src_dir = (Path(a.project) if a.project else SKILL / "assets") / "voices"
        dst_dir = (SKILL / "assets" if a.to == "skill" else Path(a.project or ".")) / "voices"
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_dir / f"{a.who}_{a.k}.wav", dst_dir / f"{a.who}.wav")
        print("->", dst_dir / f"{a.who}.wav")
    else:
        for who, e in cast(a.project).items():
            try:
                c = choose(e)
                eng = c.get("engine")
            except SystemExit:
                eng = "-"
            ref = reference_path(who, e, a.project)
            print(f"{who:10s} engine {eng:7s} reference {'yes: ' + str(ref) if ref else 'no (designed on first use)'}")


if __name__ == "__main__":
    main()
