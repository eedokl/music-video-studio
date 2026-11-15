# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Acting from the song: a mood per lyric line (text + voice), and from it the faces the figures make.

  uv run acting_draft.py draft [--project .]     -> analysis/acting.json: one row per sung line - who sings it, how
                                                    loud the voice is against the song's own average (dB) and a mood
  uv run acting_draft.py apply [--project .]     -> project.json "expressions" (and "acting": true): the LISTENERS react
                                                    to the line (someone brags -> a skeptical look, a limit is hit ->
                                                    shock), a singer shows its own feeling on lines sung with force or when nobody listens
  uv run acting_draft.py show  [--project .]     the table again

Moods: neutral, happy, cheeky, proud, sad, angry, alarm, question. `draft` only GUESSES them from a few signal words
and the punctuation - read the table and correct it: edit "mood" in analysis/acting.json and set "by" to "ai" (you
read the lyrics) or "user" (the user said so). Rows not marked "auto" survive every later `draft`.
`apply` replaces only the expressions it wrote itself ("auto": true); expressions somebody set by hand stay and
block the automatic ones around them. Same seed, same choice of who reacts.
"""
import argparse
import json
import os
import re
import sys

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis")
import creative  # noqa: E402
from media import decode  # noqa: E402
from song_project import Project  # noqa: E402

MOODS = ("neutral", "happy", "cheeky", "proud", "sad", "angry", "alarm", "question")
REACT = {"happy": "grin", "cheeky": "grin", "proud": "skeptical", "sad": "sad", "angry": "shock", "alarm": "shock",
         "question": "skeptical"}                      # what a LISTENER's face does
OWN = {"happy": "grin", "cheeky": "grin", "sad": "sad", "angry": "angry", "alarm": "shock"}   # the singer's own face
# first guess only: word stems (German + English) that often carry a mood
SIGNALS = {
    "alarm": ("limit", "quota", "teuer", "preis", "stop", "hilfe", "help", "error", "fehler", "warn", "panik", "panic",
              "kaputt", "broken", "zu spät", "too late", "oh nein", "oh no", "feuer", "fire", "crash"),
    "angry": ("wut", "hass", "hate", "verdammt", "damn", "genug", "enough", "nie wieder", "lüge", "lie", "schuld"),
    "sad": ("allein", "alone", "leer", "empty", "traurig", "sad", "verlor", "lost", "müde", "tired", "weine", "cry",
            "vermiss", "miss you", "vorbei", "goodbye"),
    "proud": ("ich bin", "i am", "i'm the", "beste", "best", "könig", "king", "queen", "boss", "gewinn", "win",
              "niemand", "nobody", "unschlagbar"),
    "cheeky": ("haha", "hihi", "trick", "heimlich", "secret", "zwinker", "wink", "pssst"),
    "happy": ("liebe", "love", "schön", "beautiful", "super", "yeah", "party", "tanz", "dance", "frei", "free",
              "willkommen", "welcome", "sonne", "sun", "lach", "laugh", "danke", "thank"),
}
GAP = 1.0                 # s between two expressions of one figure
LONGEST = 2.2             # s an expression is held
FORCE_DB = 1.5            # a line this much louder than the song's average shows on the singer's own face


def guess(text):
    low = " " + re.sub(r"[^\w' ]+", " ", text.lower()) + " "
    for mood in ("alarm", "angry", "sad", "proud", "cheeky", "happy"):
        if any((" " + s) in low for s in SIGNALS[mood]):      # at the start of a word, never inside one
            return mood
    return "question" if text.strip().endswith("?") else "neutral"


def singers(cues, t0, t1, fps=24):
    """{figure: share of the line's frames with an open mouth}"""
    out = {}
    for k, cs in cues.items():
        n = hit = 0
        for f in range(int(t0 * fps), max(int(t1 * fps), int(t0 * fps) + 1)):
            t = f / fps
            s = "X"
            for ct, shape in cs:
                if ct > t:
                    break
                s = shape
            n += 1
            hit += s not in ("X", "A")
        out[k] = hit / max(n, 1)
    return out


def draft(P):
    sheet = P.sheet()
    cues = P.assignment().get("figures", {})
    src = next((f for f in (P.analysis / "vocals_lead.wav", P.dir / "stems" / "vocals.wav", P.song) if f.exists()), None)
    y = decode(src, sr=8000) if src else np.zeros(1)
    lines = [l for l in sheet.get("lines", []) if l.get("text", "").strip()]
    level = []
    for l in lines:
        seg = y[int(l["t"] * 8000): int(l["end"] * 8000)]
        level.append(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9) if len(seg) else -90.0)
    ref = float(np.median([v for v in level if v > -80])) if any(v > -80 for v in level) else 0.0
    f = P.analysis / "acting.json"
    old = {}
    if f.exists():
        for r in json.loads(f.read_text(encoding="utf-8")).get("lines", []):
            if r.get("by", "auto") != "auto":              # read by somebody: keep
                old[(r.get("line"), r.get("text"))] = r
    rows = []
    for l, lv in zip(lines, level):
        share = singers(cues, l["t"], l["end"], P.fps)
        who = [k for k, v in sorted(share.items(), key=lambda x: -x[1]) if v >= 0.3]
        row = {"line": l.get("line"), "t": round(float(l["t"]), 2), "end": round(float(l["end"]), 2), "text": l["text"],
               "singers": who, "energy_db": round(float(lv - ref), 1) if lv > -80 else None,
               "mood": guess(l["text"]), "by": "auto"}
        kept = old.get((row["line"], row["text"]))
        if kept and kept.get("mood") in MOODS:
            row["mood"], row["by"] = kept["mood"], kept["by"]
        rows.append(row)
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"moods": list(MOODS), "voice": src.name if src else None, "lines": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    return rows


def load(P):
    f = P.analysis / "acting.json"
    if not f.exists():
        raise SystemExit("analysis/acting.json missing - run `acting_draft.py draft` first")
    rows = json.loads(f.read_text(encoding="utf-8")).get("lines", [])
    bad = [r for r in rows if r.get("mood") not in MOODS]
    if bad:
        raise SystemExit(f"analysis/acting.json: unknown mood '{bad[0].get('mood')}' in line {bad[0].get('line')} - "
                         f"use one of {', '.join(MOODS)}")
    return rows


def show(rows):
    print(f"{'line':>4} {'time':>7} {'dB':>5}  {'mood':9s} {'by':5s} {'sings':16s} text")
    for r in rows:
        e = "" if r.get("energy_db") is None else f"{r['energy_db']:+.1f}"
        print(f"{str(r.get('line')):>4} {r['t']:7.2f} {e:>5}  {r['mood']:9s} {r.get('by', 'auto'):5s} "
              f"{','.join(r.get('singers') or ['-'])[:16]:16s} {r['text'][:70]}")
    n = sum(1 for r in rows if r["mood"] != "neutral")
    print(f"{len(rows)} lines, {n} with a mood, {sum(1 for r in rows if r.get('by', 'auto') != 'auto')} read by ai / user")


def apply(P, rows):
    figs = P.get("figures") or {}
    rig = [k for k, v in figs.items() if v.get("svg")]                # only rig figures have a face to act with
    rnd = creative.rng(P, "acting-draft")                             # may store a new "seed" in project.json: before reading it
    data = json.loads(P.file.read_text(encoding="utf-8"))
    mine = [e for e in data.get("expressions") or [] if isinstance(e, dict) and not e.get("auto")]
    busy = {k: [] for k in rig}                                       # hand-set spans block the automatic ones
    for e in mine:
        if e.get("figure") in busy and e.get("from") is not None:
            busy[e["figure"]].append((float(e["from"]), float(e.get("to", float(e["from"]) + e.get("duration", 1.5)))))
    out = []

    def free(k, t0, t1):
        return all(t1 + GAP <= a or t0 >= b + GAP for a, b in busy[k])

    def add(k, name, t0, t1, why):
        if t1 - t0 < 0.6 or not free(k, t0, t1):
            return False
        busy[k].append((t0, t1))
        out.append({"figure": k, "expression": name, "from": round(t0, 2), "to": round(t1, 2), "auto": True, "why": why})
        return True

    for r in rows:
        if r["mood"] == "neutral":
            continue
        sec = next((s for s in P.sections() if float(s["from"]) <= r["t"] < float(s["to"])), None)
        if sec is None:
            continue
        cast = [k for k in (sec.get("figures") or list(figs)) if k in rig]
        t0, t1 = r["t"], min(r["end"], float(sec["to"]))
        why = f"line {r.get('line')} ({r['mood']}): {r['text'][:40]}"
        listeners = [k for k in cast if k not in (r.get("singers") or [])]
        many = r["mood"] in ("alarm", "angry")                        # a shock runs through everybody, always
        chance = rnd.random() < 0.8                                   # other moods: not every line gets a reaction
        if listeners and r["mood"] in REACT and (many or chance):
            rnd.shuffle(listeners)
            for j, k in enumerate(listeners if many else listeners[:1]):
                add(k, REACT[r["mood"]], t0 + 0.3 + 0.12 * j, min(t1 + 0.4, t0 + 0.3 + LONGEST), why)
        reacted = any(e["why"] == why for e in out)
        if r["mood"] in OWN and ((r.get("energy_db") or 0) >= FORCE_DB or not reacted):   # nobody reacts: the singer shows it
            for k in [k for k in (r.get("singers") or []) if k in cast][:1]:
                add(k, OWN[r["mood"]], t0, min(t1, t0 + LONGEST), why + " - the singer's own face")
    data["expressions"] = mine + sorted(out, key=lambda e: e["from"])
    data.setdefault("acting", True)
    tmp = P.file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, P.file)
    per = {k: sum(1 for e in out if e["figure"] == k) for k in rig}
    print(f"-> project.json: {len(out)} automatic expressions {per}, {len(mine)} set by hand kept, "
          f'"acting": {json.dumps(data["acting"])}')
    for e in out:
        print(f"   {e['from']:7.2f}-{e['to']:6.2f}  {e['figure']:8s} {e['expression']:10s} {e['why']}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=("draft", "apply", "show"))
    ap.add_argument("--project", default=".")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("animated-music-video")        # project.json validated before any long step
    if a.step == "draft":
        show(draft(P))
        print("-> analysis/acting.json - the moods are a first guess: read the lines, correct \"mood\" "
              "(set \"by\": \"ai\" / \"user\"), then `acting_draft.py apply`")
    elif a.step == "show":
        show(load(P))
    else:
        apply(P, load(P))


if __name__ == "__main__":
    sys.exit(main())
