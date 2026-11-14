"""Step 1 of a talking scene: script -> voices (or a recording) -> dialogue timeline, mouths per figure, word times.

  uv run --no-project --with numpy python speak.py [--project .] [--redo] [--engine qwen|piper|system]
Reads project.json ("script", "figures", "voices", "direction", "language", "seed") and the script file.
Voices: voice building block (fixed voice per character, Whisper check, retakes). Cached in lines/ - a line is only
spoken again when its text or voice changes (or --redo).
With "recording": "<file>" in project.json (a real recording of the whole dialogue) no TTS runs: Whisper aligns the
script to the recording, each line belongs to its speaker, Rhubarb runs once on the recording.
Timeline ("direction" in project.json, seconds): lead_in 0.4, gap 0.35 (+-0.08 from the creative seed), quick 0.12,
slow 0.9, interrupts -0.25 (overlap), tail 1.4 (hold at the end). Pauses from the script are silence between
the voices (the air kept around each line, voice.PAD, counts into them).
Writes (song-analysis layout, so film-finish works unchanged):
  song.wav                    the dialogue mix (= the sound track of the film)
  analysis/dialogue.json      lines with speaker, times, chunks, words, directions (events with times)
  analysis/song_sheet.json    words + lines (subtitles via film-finish overlays.py), no beats
  analysis/assignment.json    Rhubarb mouth cues per figure on the film timeline
  analysis/voice_<who>.wav    each figure's voice alone (lip-sync check)
  project.json sections       [{"name": "dialogue", "from": 0, "to": <duration>, "lyrics": <subtitles>}]
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis", "voice")
import config  # noqa: E402
import creative  # noqa: E402
import voice  # noqa: E402
from dialogue import parse  # noqa: E402
from media import decode, ffmpeg  # noqa: E402
from song_project import Project  # noqa: E402

SR = 44100
DIRECTION = {"lead_in": 0.4, "gap": 0.35, "jitter": 0.08, "quick": 0.12, "slow": 0.9, "interrupts": -0.25, "tail": 1.4}


def rhubarb(wav, out_json, cache, pad=0.3):
    """Rhubarb mouth cues of one voice file. The file gets `pad` s of silence on both sides first: Rhubarb opens
    the mouth a little BEFORE the sound (anticipation) and cannot do that at the very start of a file."""
    mono = cache / (Path(wav).stem + "_16k.wav")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(wav), "-af", f"adelay={int(pad * 1000)}:all=1,apad=pad_dur={pad}",
                    "-ac", "1", "-ar", "16000", str(mono)], check=True)
    subprocess.run([config.need("rhubarb"), "-r", "phonetic", "-f", "json", "--extendedShapes", "GHX", "-q",
                    "-o", str(out_json), str(mono)], check=True)
    cues = [(round(c["start"] - pad, 3), c["value"]) for c in json.loads(Path(out_json).read_text(encoding="utf-8"))["mouthCues"]]
    return [(max(t, -pad), s) for t, s in cues]


def after(who, cs, voice_end):
    """Mouth cues of a chunk from the end of the same figure's previous chunk on: the Rhubarb padding cue (rest
    shape up to 0.3 s before the voice) would otherwise land inside the previous chunk and shut the mouth mid-word.
    The last cue before that point is kept, moved onto it."""
    lim = voice_end.get(who)
    if lim is None:
        return cs
    early, keep = [c for c in cs if c[0] < lim], [c for c in cs if c[0] >= lim]
    if early and (not keep or keep[0][0] > lim):
        keep.insert(0, (lim, early[-1][1]))
    return keep


def write_wav(path, y):
    voice.write_wav(path, y, SR)


def spoken_lines(P, entries, a):
    """TTS for every chunk (cached) -> {(line_idx, chunk_idx): result}."""
    figs = P["figures"]
    lines_dir = P.dir / "lines"
    lines_dir.mkdir(exist_ok=True)
    cache_f = lines_dir / "lines.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() and not a.redo else {}
    voices = voice.cast(P.dir)
    todo, keys, results = [], [], {}
    for li, e in enumerate(entries):
        if e["kind"] != "line":
            continue
        vname = figs.get(e["who"], {}).get("voice", e["who"])
        for ci, c in enumerate(e["chunks"]):
            if not c["text"].strip():
                continue
            sig = hashlib.sha1(json.dumps([vname, c["text"], voices.get(vname), P.get("pronounce"), a.engine,
                                           creative.seed(P)], ensure_ascii=False).encode()).hexdigest()[:12]
            out = lines_dir / f"{li:02d}_{ci}_{e['who']}.wav"
            k = f"{li}:{ci}"
            if k in cache and cache[k].get("sig") == sig and out.exists():
                results[(li, ci)] = {**cache[k], "out": str(out)}      # this folder, even if the project moved
                continue
            todo.append({"who": vname, "text": c["text"], "out": str(out)})
            keys.append((li, ci, sig))
    if todo:
        print(f"speaking {len(todo)} chunk(s) ...", flush=True)
        res = voice.speak(todo, P.dir, seed=creative.seed(P), language=P.get("language", "de"), engine=a.engine,
                          pronounce=P.get("pronounce"))
        for (li, ci, sig), r in zip(keys, res):
            r["sig"] = sig
            results[(li, ci)] = r
            cache[f"{li}:{ci}"] = {**r, "out": Path(r["out"]).relative_to(P.dir).as_posix()}
    cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--engine", choices=["qwen", "piper", "system"])
    a = ap.parse_args()
    P = Project(a.project)
    D = {**DIRECTION, **(P.get("direction") or {})}
    names = list(P["figures"])
    entries = parse(P.path(P["script"]).read_text(encoding="utf-8"), names)
    for e in entries:
        if e["kind"] == "line" and e["who"] not in P["figures"]:
            raise SystemExit(f"'{e['who']}' speaks in the script but is not in project.json figures")
    rng = creative.rng(P, "dialogue-gaps")
    lines_out, cues = [], {k: [] for k in names}
    tracks = {}

    if P.get("recording"):
        rec = P.path(P["recording"])
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(rec), "-ac", "1", "-ar", str(SR), str(P.song)], check=True)
        spoken = [e for e in entries if e["kind"] == "line"]
        said = [voice.spoken(e["text"], P.get("pronounce")) for e in spoken]
        # Whisper numbers only the lines with words: a direction-only line ("Lia: (nod)") must not shift the rest
        heard_no = {}
        for li, s in enumerate(said):
            if s.strip():
                heard_no[li] = len(heard_no)
        text = "\n".join(s for s in said if s.strip())
        h = voice.hear([(P.song, text)], P.get("language", "de"))[str(P.song)]
        print(f"recording: Whisper similarity to the script {h['score']}")
        all_cues = [(max(t, 0.0), s) for t, s in rhubarb(P.song, P.analysis / "recording_mouth.json", P.cache)]
        y = decode(P.song, SR)
        total = len(y) / SR
        for li, e in enumerate(spoken):
            if li not in heard_no:                         # direction only: acts right after the previous line
                at = round(lines_out[-1]["end"] + 0.12, 3) if lines_out else 0.0
                ev = [{**{k: v for k, v in x.items() if k != "at_word"}, "t": at} for c in e["chunks"]
                      for x in c["events"]]
                lines_out.append({"who": e["who"], "text": e["text"], "t": at, "end": at, "words": [], "events": ev,
                                  "chunks": []})
                continue
            ws = [w for w in h["words"] if w["line"] == heard_no[li]]
            if not ws:
                continue
            t0, t1 = ws[0]["t"], ws[-1]["end"]
            words = [{"word": w["word"], "t": w["t"], "end": w["end"]} for w in ws]
            ev, n = [], 0
            for c in e["chunks"]:
                for x in c["events"]:
                    wi = min(n + x["at_word"], len(words) - 1)
                    ev.append({**{k: v for k, v in x.items() if k != "at_word"}, "t": words[wi]["t"] if words else t0})
                n += len(c["text"].split())
            lines_out.append({"who": e["who"], "text": e["text"], "t": t0, "end": t1, "words": words, "events": ev,
                              "chunks": [{"t": t0, "end": t1, "text": e["text"], "file": str(P.song.name)}]})
        for t, s in all_cues:                              # each mouth cue belongs to the line it falls into
            owner = next((l["who"] for l in lines_out if l["words"] and l["t"] - 0.12 <= t <= l["end"] + 0.15),
                         None)
            for k in names:
                cues[k].append((t, s if k == owner else "X"))
        for k in names:
            tr = np.zeros(len(y), np.float32)
            for l in lines_out:
                if l["who"] == k:
                    a0, a1 = int(l["t"] * SR), int(l["end"] * SR)
                    tr[a0:a1] = y[a0:a1]
            tracks[k] = tr
    else:
        res = spoken_lines(P, entries, a)
        t, first = max(float(D["lead_in"]) - voice.PAD[0], 0.0), True       # lead_in / tail are measured to the voice
        placed = []                                         # (start, file, who)
        voice_end = {}                                      # who -> end of that figure's last chunk file
        for li, e in enumerate(entries):
            if e["kind"] == "pause":
                t += e["seconds"]
                continue
            f = e["flags"]
            if not first:
                gap = D["quick"] if f.get("quick") else D["slow"] if f.get("slow") else \
                    D["gap"] + rng.uniform(-D["jitter"], D["jitter"])
                if f.get("interrupts"):
                    gap = D["interrupts"]
                t += gap
            t += f.get("pause_before", 0.0)
            first = False
            line = {"who": e["who"], "text": e["text"], "t": round(t, 3), "words": [], "events": [], "chunks": []}
            for ci, c in enumerate(e["chunks"]):
                r = res.get((li, ci))
                if r is None:                               # direction only, no words
                    for x in c["events"]:
                        line["events"].append({**{k: v for k, v in x.items() if k != "at_word"}, "t": round(t, 3)})
                    t += c["pause_after"]
                    continue
                dur = r["duration"]
                ws = [{"word": w["word"], "t": round(t + w["t"], 3), "end": round(t + w["end"], 3)} for w in r["words"]] \
                    or [{"word": w, "t": round(t + dur * i / max(len(c["text"].split()), 1), 3),
                         "end": round(t + dur * (i + 1) / max(len(c["text"].split()), 1), 3)}
                        for i, w in enumerate(c["text"].split())]
                for x in c["events"]:
                    if ws and x["at_word"] >= len(ws):          # direction after the last word: in the pause
                        et = round(ws[-1]["end"] + 0.12, 3)
                    else:
                        et = ws[min(x["at_word"], len(ws) - 1)]["t"] if ws else round(t, 3)
                    line["events"].append({**{k: v for k, v in x.items() if k != "at_word"}, "t": et})
                mj = P.cache / f"mouth_{Path(r['out']).stem}.json"
                cs = rhubarb(r["out"], mj, P.cache)
                cues[e["who"]] += after(e["who"], [(round(t + ct, 3), s) for ct, s in cs], voice_end)
                voice_end[e["who"]] = round(t + dur, 3)
                line["words"] += ws
                line["chunks"].append({"t": round(t, 3), "end": round(t + dur, 3), "text": c["text"],
                                       "file": Path(r["out"]).relative_to(P.dir).as_posix(), "engine": r["engine"],
                                       "whisper": r["score"], "heard": r["heard"]})
                placed.append((t, r["out"], e["who"]))
                t += dur + (max(c["pause_after"] - sum(voice.PAD), 0.0) if c["pause_after"] else 0.0)
            line["end"] = line["chunks"][-1]["end"] if line["chunks"] else round(t, 3)
            lines_out.append(line)
            t = max(t, line["end"])
        total = max(l["end"] for l in lines_out) - voice.PAD[1] + float(D["tail"])
        n = int(total * SR) + 1
        mix = np.zeros(n, np.float32)
        tracks = {k: np.zeros(n, np.float32) for k in names}
        for t0, wav, who in placed:
            y = decode(wav, SR)
            a0 = int(round(t0 * SR))
            b = min(n, a0 + len(y))
            mix[a0:b] += y[: b - a0]
            tracks[who][a0:b] += y[: b - a0]
        peak = np.abs(mix).max()
        if peak > 0.97:
            mix *= 0.97 / peak
        write_wav(P.song, mix)

    for k in names:                                        # sorted, X between lines
        c = sorted(cues[k])
        cues[k] = [[round(max(t, 0.0), 3), s] for t, s in c] or [[0.0, "X"]]
        write_wav(P.analysis / f"voice_{k}.wav", tracks.get(k, np.zeros(10, np.float32)))
    total = round(total, 3)
    words, sheet_lines = [], []
    for i, l in enumerate(lines_out):
        for w in l["words"]:
            words.append({**w, "frame": round(w["t"] * P.fps), "end_frame": round(w["end"] * P.fps), "line": i,
                          "who": l["who"], "source": "voice"})
        sheet_lines.append({"line": i, "text": l["text"], "who": l["who"], "t": l["t"], "end": l["end"],
                            "frame": round(l["t"] * P.fps), "end_frame": round(l["end"] * P.fps)})
    (P.analysis / "dialogue.json").write_text(json.dumps({"duration": total, "lines": lines_out}, ensure_ascii=False,
                                                         indent=1), encoding="utf-8")
    (P.analysis / "song_sheet.json").write_text(json.dumps(
        {"source": "dialogue", "fps": P.fps, "duration": total, "tempo_bpm": 0, "beats": [], "accents": [], "sections": [],
         "words": words, "lines": sheet_lines}, ensure_ascii=False, indent=1), encoding="utf-8")
    (P.analysis / "assignment.json").write_text(json.dumps({"figures": cues}), encoding="utf-8")
    secs = [s for s in P.get("sections", []) if s.get("name") != "dialogue"]
    P.p["sections"] = [{"name": "dialogue", "from": 0.0, "to": total, "lyrics": P.get("subtitles", True)}] + secs
    P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> song.wav {total:.2f} s ({round(total * P.fps)} frames), {len(lines_out)} lines, "
          f"{len(words)} words, mouth cues {', '.join(f'{k} {len(v)}' for k, v in cues.items())}")
    for l in lines_out:
        sc = [c.get("whisper") for c in l["chunks"] if c.get("whisper") is not None]
        print(f"   {l['t']:6.2f}-{l['end']:6.2f}  {l['who']:9s} {l['text'][:60]}"
              + (f"   Whisper {min(sc):.2f}" if sc else "") + (f"   {len(l['events'])} directions" if l["events"] else ""))


if __name__ == "__main__":
    main()
