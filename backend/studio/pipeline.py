"""Analysis pipeline as a background job: audio → measured timing → project.json.

Steps (each runs one of the proven scripts in backend/pipeline as a subprocess with uv):
  prepare     convert the song (+ optional stems) to WAV, pick the lead vocal stem
  separate    Demucs vocal separation – skipped when a lead-vocal stem was uploaded
  transcribe  Whisper word timestamps (on the vocal stem if given, else on the mix) + head re-check
  align       known lyrics ↔ transcription (records how many words of each line were heard)
  refine      snap word starts to vocal onsets; cap word ends before the next line
  beats       beat grid (drum stem if given): detected beats, fitted tempo, downbeat phase
  hits        riff hits (drum stem if given)
  voice       lines nobody sings → unsung; backing-vocal lines; held-note candidates measured
  assemble    project.json with grid, lyrics, hits, held notes and a first storyboard
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import traceback
import wave
from pathlib import Path

import numpy as np

from . import store, storyboard
from .config import PIPELINE, ffmpeg
from .lyrics_text import parse, plain

STEPS = ["prepare", "separate", "transcribe", "align", "refine", "beats", "hits", "voice", "assemble", "engine"]
UV_LIGHT = ["--with", "numpy", "--with", "imageio-ffmpeg", "--with", "scipy"]
UV_WHISPER = ["--with", "faster-whisper", "--with", "numpy", "--with", "imageio-ffmpeg"]
UV_DEMUCS = ["--python", "3.11", "--with", "demucs", "--with", "torch==2.5.1", "--with", "torchaudio==2.5.1", "--with", "soundfile", "--with", "imageio-ffmpeg"]
UV_LIBROSA = ["--with", "librosa", "--with", "numpy", "--with", "imageio-ffmpeg"]

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def job(pid: str) -> dict | None:
    with _jobs_lock:
        j = _jobs.get(pid)
        return dict(j, log=j["log"][-400:]) if j else None


def _set(pid: str, **kw):
    with _jobs_lock:
        _jobs[pid].update(kw)


def _log(pid: str, msg: str):
    msg = msg.rstrip()
    if not msg:
        return
    with _jobs_lock:
        _jobs[pid]["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")


def _run(pid: str, args: list[str], cwd: Path):
    _log(pid, "$ " + " ".join(a if " " not in a else f'"{a}"' for a in args[:3]) + " …")
    p = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    assert p.stdout
    for line in p.stdout:
        for part in line.replace("\r", "\n").split("\n"):
            part = part.strip()
            # tqdm progress bars: keep only every ~10 %
            if "%|" in part and not re.search(r"\b(\d0|100)%\|", part):
                continue
            _log(pid, part)
    if p.wait() != 0:
        raise RuntimeError(f"{Path(args[-1]).name if args else 'step'} failed (exit {p.returncode}) – see log")


def _uv(pid: str, deps: list[str], script: str, *args: str, cwd: Path):
    _run(pid, ["uv", "run", "--no-project", *deps, "python", str(PIPELINE / script), *args], cwd)


def _wav(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(src), "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(dst)], check=True)


def _duration(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def _rms_db(p: Path, hop_s: float = 0.05) -> tuple[np.ndarray, float]:
    with wave.open(str(p)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    x = x.reshape(-1, ch).mean(axis=1)
    hop = int(sr * hop_s)
    m = len(x) // hop
    r = np.sqrt((x[: m * hop].reshape(m, hop) ** 2).mean(axis=1)) + 1e-6
    return 20 * np.log10(r), hop_s


def classify_stem(name: str) -> str:
    n = name.lower()
    if re.search(r"back|background|choir|bgv|harmon", n):
        return "backing"
    if re.search(r"vocal|vox|voice|lead", n):
        return "lead"
    if re.search(r"drum|perc|kick|snare", n):
        return "drums"
    if "bass" in n:
        return "bass"
    return re.sub(r"[^a-z0-9]+", "-", Path(n).stem).strip("-") or "stem"


def start(pid: str, from_step: str = "prepare") -> bool:
    with _jobs_lock:
        if _jobs.get(pid, {}).get("status") == "running":
            return False
        _jobs[pid] = {"kind": "analysis", "status": "running", "step": from_step, "steps": STEPS, "log": [], "started": time.time(), "error": None}
    threading.Thread(target=_work, args=(pid, from_step), daemon=True).start()
    return True


def _work(pid: str, from_step: str):
    d = store.project_dir(pid)
    a = d / "analysis"
    a.mkdir(exist_ok=True)
    inp = d / "inputs"
    meta = json.loads((inp / "meta.json").read_text(encoding="utf-8"))
    try:
        for step in STEPS[STEPS.index(from_step):]:
            _set(pid, step=step)
            _log(pid, f"== {step}")
            globals()[f"_step_{step}"](pid, d, a, inp, meta)
        _set(pid, status="done", step="done")
        _log(pid, "analysis finished")
    except Exception as e:  # noqa: BLE001 – report any failure to the UI
        _log(pid, traceback.format_exc())
        _set(pid, status="error", error=str(e))
        try:
            p = store.load(pid)
            p["status"] = "error"
            store.save(pid, p, keep_history=False)
        except Exception:
            pass


# ---------------------------------------------------------------- steps
def _step_prepare(pid, d, a, inp, meta):
    _wav(inp / meta["song"], d / "audio" / "mix.wav")
    stems = {}
    for f in meta.get("stems", []):
        kind = classify_stem(f)
        dst = d / "audio" / "stems" / f"{kind}.wav"
        _wav(inp / "stems" / f, dst)
        stems[kind] = f"audio/stems/{kind}.wav"
        _log(pid, f"stem {f} → {kind}")
    meta["stemMap"] = stems
    if stems:
        meta["stemCheck"] = _check_stems(pid, d, stems)
    (inp / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = parse(meta["lyrics"])
    (a / "lyrics.txt").write_text(plain(rows), encoding="utf-8")
    (a / "rows.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    _log(pid, f"{len(rows)} lyric lines, song {_duration(d / 'audio' / 'mix.wav'):.1f} s")


def _read(p: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(p)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    return x.reshape(-1, ch), sr


def _env(x: np.ndarray, sr: int, fps: int = 100) -> np.ndarray:
    m = x.mean(axis=1) if x.ndim == 2 else x
    h = sr // fps
    n = len(m) // h
    return np.log(np.sqrt((m[: n * h].reshape(n, h) ** 2).mean(axis=1)) + 1e-4)


def _check_stems(pid, d, stems: dict) -> dict:
    """Do the stems belong to exactly this mix? Compare the stem sum with the mix section by section.

    Suno stems of another version ("Edit") can be shifted by seconds and drift – mixing them with the
    wrong WAV would put every word off. Result: ok | shifted (constant lag, stems get shifted) |
    mismatch (stem sum becomes the soundtrack so picture and sound match)."""
    tot, sr = None, 44100
    for rel in stems.values():
        x, sr = _read(d / rel)
        tot = x if tot is None else (tot[: len(x)] + x[: len(tot)])
    mix, _ = _read(d / "audio" / "mix.wav")
    A, B = _env(tot, sr), _env(mix, sr)
    lags, cors = [], []
    win, maxlag = 1000, 800  # 10 s windows, ±8 s search
    for s in range(1500, min(len(A), len(B)) - win - maxlag, 2000):
        seg = A[s : s + win]
        seg = (seg - seg.mean()) / (seg.std() + 1e-9)
        best = (-1.0, 0)
        for lag in range(-maxlag, maxlag + 1):
            w = B[s + lag : s + lag + win]
            if len(w) < win or s + lag < 0:
                continue
            c = float(np.dot(seg, (w - w.mean()) / (w.std() + 1e-9)) / win)
            if c > best[0]:
                best = (c, lag)
        cors.append(best[0])
        lags.append(best[1] / 100)
    # only windows that clearly correlate count (quiet intros / breaks give random lags)
    good = [lg for lg, c in zip(lags, cors) if c >= 0.6] or lags
    lags_a = np.array(good)
    spread = float(lags_a.max() - lags_a.min()) if len(good) else 0
    med = float(np.median(lags_a)) if len(good) else 0
    res = {"lags": lags, "corr": [round(c, 2) for c in cors], "medianLag": med, "spread": spread, "lenStems": len(tot) / sr, "lenMix": len(mix) / sr}
    if abs(med) < 0.03 and spread < 0.08:
        res["status"] = "ok"
        _log(pid, "stems match the mix")
    elif spread < 0.08:
        res["status"] = "shifted"
        _log(pid, f"stems are shifted by {med:+.2f} s against the mix – compensating")
        for rel in stems.values():
            p = d / rel
            tmp = p.with_suffix(".shift.wav")
            flt = f"adelay={int(med * 1000)}|{int(med * 1000)}" if med > 0 else f"atrim=start={-med}"
            subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(p), "-af", flt, str(tmp)], check=True)
            tmp.replace(p)
    else:
        res["status"] = "mismatch"
        out = d / "audio" / "mix.wav"
        out.replace(d / "audio" / "mix_original.wav")
        m = np.clip(tot, -1, 1)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(m.shape[1])
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((m * 32767).astype(np.int16).tobytes())
        _log(pid, f"WARNING: the stems are a different version than the uploaded song (offset {lags_a.min():+.2f}…{lags_a.max():+.2f} s, lengths {res['lenStems']:.1f} vs {res['lenMix']:.1f} s). Using the sum of the stems as the soundtrack so picture and sound match. Upload the WAV of the same Suno version to use the original mix.")
    return res


def _step_separate(pid, d, a, inp, meta):
    lead = meta.get("stemMap", {}).get("lead")
    if lead:
        _wav(d / lead, d / "audio" / "vocals.wav")
        _log(pid, "lead vocal stem provided – no separation needed")
        return
    if meta.get("keepScenes") and not meta.get("newAudio") and (d / "audio" / "vocals.wav").exists():
        _log(pid, "re-analysis: keeping the existing vocal track")
        return
    _uv(pid, UV_DEMUCS, "separate_vocals.py", str(d / "audio" / "mix.wav"), str(a / "sep"), cwd=a)
    _wav(a / "sep" / "vocals.wav", d / "audio" / "vocals.wav")


def _step_transcribe(pid, d, a, inp, meta):
    src = d / "audio" / ("vocals.wav" if meta.get("stemMap", {}).get("lead") else "mix.wav")
    _uv(pid, UV_WHISPER, "transcribe.py", str(src), str(a / "words.json"), "--lyrics", str(a / "lyrics.txt"), "--lang", "auto", cwd=a)
    segs = json.loads((a / "words.json").read_text(encoding="utf-8"))
    first_word = next((w["s"] for s in segs for w in s["words"]), None)
    db, hop = _rms_db(d / "audio" / "vocals.wav")
    active = np.where(db > db.max() - 30)[0]
    first_voice = active[0] * hop if len(active) else 0
    if first_word is not None and first_word - first_voice > 12:
        _log(pid, f"Whisper started at {first_word:.1f} s but the voice starts at {first_voice:.1f} s – transcribing the beginning separately")
        head = a / "head.wav"
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(src), "-t", f"{first_word + 2:.2f}", str(head)], check=True)
        _uv(pid, UV_WHISPER, "transcribe.py", str(head), str(a / "words_head.json"), "--lyrics", str(a / "lyrics.txt"), "--lang", "auto", cwd=a)
        hs = json.loads((a / "words_head.json").read_text(encoding="utf-8"))
        keep = [s for s in hs if s["words"] and s["words"][-1]["e"] < first_word - 0.3]
        (a / "words.json").write_text(json.dumps(keep + segs, ensure_ascii=False), encoding="utf-8")


def _step_align(pid, d, a, inp, meta):
    _uv(pid, UV_LIGHT, "align.py", str(a / "words.json"), str(a / "lyrics.txt"), str(a / "timing_raw.json"), cwd=a)
    # Whisper sometimes skips or hallucinates a stretch (often the first verse, prompted by the chorus
    # text). Lines it did not hear in a row → transcribe exactly that stretch again, with only those
    # lines as the hint, merge the words and align once more.
    timing = json.loads((a / "timing_raw.json").read_text())
    rows = json.loads((a / "rows.json").read_text(encoding="utf-8"))
    dur = _duration(d / "audio" / "mix.wav")
    runs, cur = [], []
    for i, x in enumerate(timing):
        if x.get("matched", 0) == 0:
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    runs = [r for r in runs if len(r) >= 2 or sum(len(rows[i]["text"].split()) for i in r) >= 4]
    if not runs:
        return
    src = d / "audio" / ("vocals.wav" if meta.get("stemMap", {}).get("lead") else "mix.wav")
    segs = json.loads((a / "words.json").read_text(encoding="utf-8"))
    changed = False
    for k, run in enumerate(runs):
        prev = next((timing[j] for j in range(run[0] - 1, -1, -1) if timing[j].get("matched", 0) > 0), None)
        nxt = next((timing[j] for j in range(run[-1] + 1, len(timing)) if timing[j].get("matched", 0) > 0), None)
        t0 = max(0.0, (prev["e"] if prev else 0.0) - 0.2)
        t1 = min(dur, (nxt["t"] if nxt else dur) + 0.2)
        if t1 - t0 < 1.0:
            continue
        _log(pid, f"lines {run[0]}-{run[-1]} not heard - transcribing {t0:.1f}-{t1:.1f} s again: {rows[run[0]]['text']} ...")
        clip = a / f"gap{k}.wav"
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(src), str(clip)], check=True)
        hint = a / f"gap{k}.txt"
        hint.write_text("\n".join(rows[i]["text"] for i in run) + "\n", encoding="utf-8")
        out = a / f"gap{k}.json"
        try:
            _uv(pid, UV_WHISPER, "transcribe.py", str(clip), str(out), "--lyrics", str(hint), "--lang", "auto", cwd=a)
        except RuntimeError:
            continue
        gs = json.loads(out.read_text(encoding="utf-8"))
        for s in gs:
            s["s"] += t0
            s["e"] += t0
            for w in s["words"]:
                w["s"] += t0
                w["e"] += t0
        # replace whatever Whisper claimed for that stretch
        kept = []
        for s in segs:
            ws = [w for w in s["words"] if not (t0 + 0.1 <= w["s"] <= t1 - 0.1)]
            if ws:
                kept.append({**s, "words": ws, "s": ws[0]["s"], "e": ws[-1]["e"]})
        segs = sorted(kept + [s for s in gs if s["words"]], key=lambda s: s["s"])
        changed = True
    if changed:
        (a / "words.json").write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
        _uv(pid, UV_LIGHT, "align.py", str(a / "words.json"), str(a / "lyrics.txt"), str(a / "timing_raw.json"), cwd=a)


def _step_refine(pid, d, a, inp, meta):
    _uv(pid, UV_LIGHT, "refine_timing.py", str(d / "audio" / "vocals.wav"), str(a / "timing_raw.json"), str(a / "timing.json"), cwd=a)
    # refine_timing drops the matched counts – carry them over
    raw = json.loads((a / "timing_raw.json").read_text())
    ref = json.loads((a / "timing.json").read_text())
    for r, x in zip(raw, ref):
        x["matched"], x["total"] = r.get("matched", 0), r.get("total", 1)
    (a / "timing.json").write_text(json.dumps(ref))


def _step_beats(pid, d, a, inp, meta):
    drums = meta.get("stemMap", {}).get("drums")
    src = d / (drums or "audio/mix.wav")
    _uv(pid, UV_LIBROSA, "beats.py", str(src), str(a / "beats.json"), cwd=a)
    b = json.loads((a / "beats.json").read_text())
    b["source"] = "drums" if drums else "mix"
    (a / "beats.json").write_text(json.dumps(b))


def _step_hits(pid, d, a, inp, meta):
    drums = meta.get("stemMap", {}).get("drums")
    _uv(pid, UV_LIGHT, "analyze.py", str(d / (drums or "audio/mix.wav")), "--hits", str(a / "hits.json"), cwd=a)


def _sustain_end(db: np.ndarray, hop: float, start: float, limit: float) -> float:
    """How long the voice keeps sounding from `start` (frames above local peak − 12 dB, gaps ≤ 0.15 s)."""
    i0 = int(start / hop)
    peak = float(db[i0 : i0 + int(0.4 / hop) + 1].max()) if i0 < len(db) else -120
    thr, gap, end = peak - 12, 0, i0
    for i in range(i0, min(len(db), int(limit / hop))):
        if db[i] > thr:
            end, gap = i, 0
        else:
            gap += 1
            if gap * hop > 0.15:
                break
    return (end + 1) * hop


def _step_voice(pid, d, a, inp, meta):
    """Who sings what: unsung lines, backing-vocal lines, true word ends of held notes, held-note tracks."""
    timing = json.loads((a / "timing.json").read_text())
    rows = json.loads((a / "rows.json").read_text(encoding="utf-8"))
    db, hop = _rms_db(d / "audio" / "vocals.wav")
    back = meta.get("stemMap", {}).get("backing")
    bdb = _rms_db(d / back)[0] if back else None
    n = len(timing)
    ratio = [x.get("matched", 0) / max(1, x.get("total", 1)) for x in timing]
    order = sorted(range(n), key=lambda i: timing[i]["t"])

    def voiced(arr, t, e, thr):
        i, j = max(0, int(t / hop)), max(int(t / hop) + 1, int(e / hop))
        seg = arr[i:j]
        return float((seg > thr).sum() * hop) if len(seg) else 0.0

    heard_lv = [float(np.percentile(db[int(x["t"] / hop) : max(int(x["t"] / hop) + 1, int(x["e"] / hop))], 80)) for x in timing]
    sung_ref = float(np.median([heard_lv[i] for i in range(n) if ratio[i] >= 0.5] or [max(heard_lv)]))
    thr = sung_ref - 14
    # 1) true end of each line's last word (held notes sound longer than Whisper says)
    for k, i in enumerate(order):
        x = timing[i]
        nxt = next((timing[o]["t"] for o in order[k + 1 :] if ratio[o] >= 0.25), x["e"] + 6)
        se = _sustain_end(db, hop, x["words"][-1], nxt - 0.05)
        if se > x["ends"][-1]:
            x["ends"][-1] = round(se, 3)
            x["e"] = max(x["e"], x["ends"][-1])
    # 2) lines Whisper did not hear: only the gap between the neighbouring heard lines counts
    info = [{"unsung": False, "singer": "lead", "heard": round(r, 2)} for r in ratio]
    for k, i in enumerate(order):
        if ratio[i] >= 0.25:
            continue
        prev_e = max([timing[o]["e"] for o in order[:k] if ratio[o] >= 0.25] or [0.0])
        next_t = min([timing[o]["t"] for o in order[k + 1 :] if ratio[o] >= 0.25] or [len(db) * hop])
        lead_v = voiced(db, prev_e + 0.05, next_t - 0.05, thr)
        back_v = voiced(bdb, prev_e + 0.05, next_t - 0.05, thr) if bdb is not None else 0.0
        if next_t - prev_e < 0.5 or max(lead_v, back_v) < 0.3:
            info[i]["unsung"] = True
            _log(pid, f"line {i} is not sung (no voice between {prev_e:.1f} and {next_t:.1f} s): {rows[i]['text']}")
            continue
        arr = bdb if back_v > lead_v and bdb is not None else db
        if arr is bdb:
            info[i]["singer"] = "backing"
        # place the words evenly over the voiced part of the gap
        idx = [j for j in range(int((prev_e + 0.05) / hop), int((next_t - 0.05) / hop)) if j < len(arr) and arr[j] > thr]
        if idx and ratio[i] == 0:
            t0, t1 = idx[0] * hop, (idx[-1] + 1) * hop
            m = len(timing[i]["words"])
            step = (t1 - t0) / m
            timing[i]["words"] = [round(t0 + q * step, 3) for q in range(m)]
            timing[i]["ends"] = [round(t0 + (q + 0.9) * step, 3) for q in range(m)]
            timing[i]["t"], timing[i]["e"] = timing[i]["words"][0], timing[i]["ends"][-1]
            _log(pid, f"line {i} was not heard by Whisper – placed on the voice at {t0:.1f}–{t1:.1f} s ({'backing' if arr is bdb else 'lead'}): {rows[i]['text']}")
    # backing vocals: lines where the backing stem is clearly louder
    if bdb is not None:
        for i, x in enumerate(timing):
            if info[i]["unsung"]:
                continue
            seg_l = db[int(x["t"] / hop) : max(int(x["t"] / hop) + 1, int(x["e"] / hop))]
            seg_b = bdb[int(x["t"] / hop) : max(int(x["t"] / hop) + 1, int(x["e"] / hop))]
            if len(seg_b) and np.percentile(seg_b, 80) > np.percentile(seg_l, 80) + 3:
                info[i]["singer"] = "backing"
    (a / "timing.json").write_text(json.dumps(timing))
    (a / "voice.json").write_text(json.dumps(info))
    # 3) held notes: last words the voice sustains > 1.2 s (or the names the project already uses)
    keep_names = meta.get("keepHeld") or []
    if keep_names:
        cand = [(h["name"], int(h["row"]) if "row" in h else int(h["line"][1:])) for h in keep_names]
    else:
        long = sorted(((timing[i]["ends"][-1] - timing[i]["words"][-1], i) for i in range(n) if not info[i]["unsung"]), reverse=True)
        picked = sorted([i for dur, i in long[:4] if dur > 1.2])
        cand = []
        for k, i in enumerate(picked):
            word = re.sub(r"\W", "", rows[i]["text"].split()[-1].lower()) or "held"
            cand.append((f"{word}{k + 1}", i))
    specs = [f"{name}:{timing[i]['words'][-1] - 0.05:.2f}:{timing[i]['ends'][-1] + 0.1:.2f}" for name, i in cand]
    out = []
    if specs:
        _uv(pid, UV_LIGHT, "held.py", str(d / "audio" / "vocals.wav"), str(a / "held.json"), *specs, cwd=a)
        h = json.loads((a / "held.json").read_text())
        ids = meta.get("idMap") or [f"l{k}" for k in range(len(rows))]
        out = [{"name": name, "line": ids[i], "word": len(rows[i]["text"].split()) - 1, **h[name]} for name, i in cand if name in h]
    (a / "held_list.json").write_text(json.dumps(out))


def build_grid(b: dict) -> dict:
    mode = b.get("mode", "fixed")
    return {
        "mode": mode,
        "bpm": b["bpm"],
        "offset": b["offset"],
        "detected": b["detected"],
        "fixed": b["fixed"],
        "beats": b["fixed"] if mode == "fixed" else b["detected"],
        "beatsPerBar": b.get("beatsPerBar", 4),
        "downbeatPhase": b.get("downbeatPhase", 0),
        "residualMs": b.get("residual_ms"),
        "source": b.get("source", "mix"),
    }


def _step_assemble(pid, d, a, inp, meta):
    rows = json.loads((a / "rows.json").read_text(encoding="utf-8"))
    timing = json.loads((a / "timing.json").read_text())
    voice = json.loads((a / "voice.json").read_text())
    lines = []
    for i, (r, x, v) in enumerate(zip(rows, timing, voice)):
        ws = r["text"].split(" ")
        words = [{"w": w, "t": round(x["words"][k], 3), "e": round(x["ends"][k], 3)} for k, w in enumerate(ws)]
        lid = (meta.get("idMap") or [])[i] if i < len(meta.get("idMap") or []) else f"l{i}"
        lines.append({"id": lid, "section": r["section"], "text": r["text"], "unsung": v["unsung"], "singer": v["singer"], "heard": v["heard"], "words": words})
    beats = json.loads((a / "beats.json").read_text())
    hits = json.loads((a / "hits.json").read_text())
    held = json.loads((a / "held_list.json").read_text())
    audio = {"mix": "audio/mix.wav", "vocals": "audio/vocals.wav", "stems": meta.get("stemMap", {}), "duration": round(_duration(d / "audio" / "mix.wav"), 3)}
    if meta.get("stemCheck"):
        audio["stemCheck"] = {k: v for k, v in meta["stemCheck"].items() if k in ("status", "medianLag", "spread", "lenStems", "lenMix")}
    project = {
        "format": 1,
        "id": pid,
        "title": meta["title"],
        "storyline": meta.get("storyline", ""),
        "stylePrompt": meta.get("stylePrompt", ""),
        "world": "concert",
        "status": "ready",
        "audio": audio,
        "grid": build_grid(beats),
        "lyrics": {"lead": 0.08, "lines": lines},
        "hits": hits,
        "held": held,
        "settings": {"readHold": 0.3},
    }
    old = None
    if meta.get("keepScenes"):
        try:
            old = store.load(pid)
        except Exception:
            old = None
    if old and old.get("scenes") and meta.get("newAudio") and meta.get("updatePlan"):
        # updated song: carry the storyboard over (line identities, time anchors, new/removed lines)
        from . import update

        update.merge(old, project, meta["updatePlan"])
        u = project["lastUpdate"]
        _log(pid, f"update: {len(u['added'])} new, {len(u['changed'])} changed, {len(u['removed'])} removed lines; words shifted by {u['medianShift']:+.2f} s (median)")
    elif old and old.get("scenes"):
        # timing re-analysis: keep the storyboard and settings the user built (anchors follow the new timing)
        for k in ("scenes", "events", "looks", "settings", "title", "storyline", "stylePrompt", "world", "legacy"):
            if k in old:
                project[k] = old[k]
        project["lyrics"]["lead"] = old.get("lyrics", {}).get("lead", 0.08)
    else:
        scenes, events, looks = storyboard.build(project)
        project.update(scenes=scenes, events=events, looks=looks)
    store.save(pid, project)
    _log(pid, f"project ready: {len(lines)} lines ({sum(l['unsung'] for l in lines)} unsung), {len(project['scenes'])} scenes, {project['grid']['bpm']} BPM ({project['grid']['mode']})")


def _step_engine(pid, d, a, inp, meta):
    """Project created from an existing video folder: import its original scenes (once)."""
    src = meta.get("legacySource")
    if not src:
        return
    p = store.load(pid)
    if p.get("world") == "legacy" and p.get("legacy", {}).get("engine"):
        _log(pid, "original engine already imported – keeping it")
        return
    import contextlib
    import io

    from . import legacy

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        legacy.import_legacy(pid, Path(src))
    for line in buf.getvalue().splitlines():
        _log(pid, line)
