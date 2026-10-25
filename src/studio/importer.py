"""Import a project built with the earlier hand-made engine (Comfort Zone V4) into the studio format.

  uv run python -m studio.importer V4_DIR SCENES_JSON WALL_MODULE_JS VOCALS_WAV [--id comfort-zone-v4]

SCENES_JSON is the dumped TIMELINE of the old project (scene id, lines, start, shot, seed, look,
wall name, lyric style, held lines, camera label); WALL_MODULE_JS the old LED-wall functions bundled
as a custom wall module (exports setApi + one function per visual).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from . import store
from .pipeline import _wav

EVENT_KEYS = ("co2", "sparks", "confetti", "fireworks")


def parse_raw(lyrics_ts: str) -> list[tuple[str, str]]:
    body = lyrics_ts.split("const RAW", 1)[1].split("\n];", 1)[0]
    rows = []
    for ln in body.splitlines():
        ln = ln.strip().rstrip(",")
        if ln.startswith('["'):
            sec, text = json.loads(ln)
            rows.append((sec, text))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("scenes")
    ap.add_argument("walls")
    ap.add_argument("vocals")
    ap.add_argument("--id", default="comfort-zone-v4")
    ap.add_argument("--title", default="Comfort Zone – Live in Brüssel")
    a = ap.parse_args()
    src = Path(a.src)
    lyrics_ts = (src / "src" / "lyrics.ts").read_text(encoding="utf-8")
    rows = parse_raw(lyrics_ts)
    timing = json.loads((src / "src" / "timing.json").read_text())
    bpm = float(re.search(r"BPM = ([\d.]+)", lyrics_ts).group(1))
    offset = float(re.search(r"BEAT_OFFSET = ([\d.]+)", lyrics_ts).group(1))
    dump = json.loads(Path(a.scenes).read_text(encoding="utf-8"))
    held_raw = json.loads((src / "src" / "held.json").read_text())
    hits = json.loads((src / "src" / "hits.json").read_text())

    pid = a.id
    d = store.project_dir(pid)
    if d.exists():
        shutil.rmtree(d)
    (d / "walls").mkdir(parents=True)
    _wav(src / "public" / "song.wav", d / "audio" / "mix.wav")
    _wav(Path(a.vocals), d / "audio" / "vocals.wav")
    shutil.copy(a.walls, d / "walls" / "comfort.js")

    import wave

    with wave.open(str(d / "audio" / "mix.wav")) as w:
        dur = w.getnframes() / w.getframerate()

    lines = []
    for i, ((sec, text), x) in enumerate(zip(rows, timing, strict=False)):
        ws = text.split(" ")
        words = [{"w": w, "t": round(x["words"][k], 3), "e": round(x["ends"][k], 3)} for k, w in enumerate(ws)]
        lines.append({"id": f"l{i}", "section": sec, "text": text, "unsung": False, "singer": "lead", "words": words})

    period = 60 / bpm
    beats = [round(offset + k * period, 4) for k in range(int((dur - offset) / period) + 1)]
    grid = {
        "mode": "fixed",
        "bpm": bpm,
        "offset": offset,
        "detected": beats,
        "fixed": beats,
        "beats": beats,
        "beatsPerBar": 4,
        "downbeatPhase": 0,
        "source": "legacy",
    }

    held = []
    for li, name in dump["held"]:
        if name in held_raw:
            held.append({"name": name, "line": f"l{li}", "word": len(lines[li]["words"]) - 1, **held_raw[name]})

    scenes, events, seen = [], [], set()

    def ev(kind, t, until=None):
        key = (kind, round(t, 2), round(until, 2) if until else None)
        if key in seen:
            return
        seen.add(key)
        e = {"type": kind, "at": {"kind": "time", "t": round(t, 3)}}
        if until is not None:
            e["until"] = {"kind": "time", "t": round(until, 3)}
        events.append(e)

    for k, s in enumerate(dump["scenes"]):
        look = dict(s["look"])
        for t in look.pop("co2", []) or []:
            ev("co2", t)
        sp = look.pop("sparks", None)
        if sp:
            ev("sparks", sp[0], sp[1])
        c = look.pop("confetti", None)
        if c is not None:
            ev("confetti", c)
        for t in look.pop("fireworks", []) or []:
            ev("fireworks", t)
        sc = {
            "id": f"s{k + 1}",
            "name": s["id"],
            "start": {"kind": "auto"} if s["start"] is None else {"kind": "time", "t": round(s["start"], 3)},
            "lines": [f"l{i}" for i in s["lines"]],
            "shot": s["shot"],
            "seed": s["seed"],
            "look": look,
            "wall": {"type": "custom", "module": "walls/comfort.js", "fn": s["wall"]},
            "lyr": s["lyr"],
            "cam": s["cam"],
        }
        if s.get("lineOpts"):
            sc["held"] = {f"l{li}": o["held"] for li, o in s["lineOpts"].items() if o.get("held")}
        scenes.append(sc)

    project = {
        "format": 1,
        "id": pid,
        "title": a.title,
        "storyline": "Comfort Zone als Live-Konzert in Brüssel (TV-Übertragung): die Geschichte des Songs läuft auf der LED-Wand.",
        "stylePrompt": "Falco meets Neue Deutsche Härte",
        "world": "concert",
        "status": "ready",
        "audio": {"mix": "audio/mix.wav", "vocals": "audio/vocals.wav", "stems": {}, "duration": round(dur, 3)},
        "grid": grid,
        "lyrics": {"lead": 0.08, "lines": lines},
        "hits": hits,
        "held": held,
        "looks": {},
        "scenes": scenes,
        "events": events,
        "settings": {"readHold": 0.3},
    }
    store.save(pid, project, keep_history=False)
    # inputs for a later re-analysis
    inp = d / "inputs"
    inp.mkdir(exist_ok=True)
    shutil.copy(d / "audio" / "mix.wav", inp / "song.wav")
    lyr, last = [], None
    for sec, text in rows:
        if sec != last:
            lyr.append(f"[{sec}]")
            last = sec
        lyr.append(text)
    (inp / "meta.json").write_text(
        json.dumps(
            {
                "title": a.title,
                "lyrics": "\n".join(lyr),
                "storyline": project["storyline"],
                "stylePrompt": project["stylePrompt"],
                "song": "song.wav",
                "stems": [],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"imported {pid}: {len(lines)} lines, {len(scenes)} scenes, {len(events)} events, {len(held)} held notes, {dur:.1f} s")


if __name__ == "__main__":
    sys.exit(main())
