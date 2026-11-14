# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Dialogue scripts: parse "Name: text (direction) text" into lines, spoken chunks and stage directions.

Script format (UTF-8 text, one line per speech; '#' starts a comment):
    Tim: Hallo Computer! (to computer) Bist du wach?
    (pause 0.8)
    Computer: (screen "SYSTEM: WACH") Guten Abend, Tim. (cheer) Wie kann ich helfen?
    Pip: Oh! (pause 1.1) (looks up) Ein Blatt!
Directions in round brackets (several per line, anywhere):
    (pause 1.2) / (beat)          silence inside a line (splits it into chunks) or between lines; (beat) = 0.6 s
    (to <name>) / (looks at <name>) / (looks up|down|away|camera)    where the speaker looks from here on
    (interrupts)                  the line starts before the previous one has finished (0.25 s overlap)
    (quick) / (slow)              short / long gap before this line
    (screen "TEXT")               the screen figure shows TEXT instead of its face while this line runs
    gestures: (cheer) (point) (scare) (surprise) (scratch) (nod) (sad) (shrug) (wave) (jump) (lean)
              -> the speaker acts on the next word; "(point at computer)" / "(wave tim)" = towards a figure,
              "(nod tim)" / "(scare lia)" = that LISTENER reacts at this moment
Everything that is not a direction is spoken text and becomes the subtitle.
"""
import re

GESTURES = ("cheer", "point", "scare", "surprise", "scratch", "nod", "sad", "shrug", "wave", "jump", "lean")
DIR = re.compile(r"\(([^)]*)\)")
SPEAKER = re.compile(r"^\s*([A-Za-zÄÖÜäöüß0-9_\- ]{1,30}?)\s*:\s*(.*)$")


def key(name):
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                  .replace("ß", "ss"))


def parse_direction(d, names):
    """'pause 1.2' -> {"pause": 1.2}; 'to computer' -> {"look": "computer"}; 'cheer' -> {"gesture": "cheer"} ..."""
    d = d.strip()
    low = d.lower()
    m = re.match(r"pause\s*([\d.,]+)?", low)
    if m:
        return {"pause": float((m.group(1) or "0.8").replace(",", "."))}
    if low == "beat":
        return {"pause": 0.6}
    m = re.match(r'screen\s+"?([^"]*)"?', d, re.I)
    if m:
        return {"screen": m.group(1).replace("\\n", "\n")}
    m = re.match(r"(?:to|looks? at|looking at)\s+(\w+)", low)
    if m:
        return {"look": key(m.group(1))}
    m = re.match(r"looks?\s+(up|down|away|camera|left|right)", low)
    if m:
        return {"look": m.group(1)}
    if low in ("interrupts", "quick", "slow"):
        return {low: True}
    words = low.split()
    g = None
    if words:
        w0 = words[0]
        g = w0 if w0 in GESTURES else (w0[:-1] if w0.endswith("s") and w0[:-1] in GESTURES else None)
    if g:
        rest = [key(w) for w in words[1:] if w not in ("at", "to", "the")]
        name = next((w for w in rest if w in names), None)
        if g in ("point", "wave", "lean"):          # towards somebody
            return {"gesture": g, "target": name}
        return {"gesture": g, "by": name}           # performed by somebody else (a listener reacts)
    return {"note": d}


def parse(text, names=None):
    """-> list of entries:
    {"kind": "line", "who": "tim", "text": "Hallo Computer! Bist du wach?",
     "chunks": [{"text": "Hallo Computer!", "pause_after": 0.0, "events": [{"at_word": 0, ...direction}]}, ...],
     "flags": {"interrupts": bool, "quick": bool, "slow": bool}}
    {"kind": "pause", "seconds": 0.8}
    names: known figure keys (for "(point at computer)")."""
    names = set(names or [])
    out = []
    for raw in text.splitlines():
        row = raw.strip()
        if not row or row.startswith("#"):
            continue
        m = SPEAKER.match(row)
        if not m:
            for d in DIR.findall(row):
                p = parse_direction(d, names)
                if "pause" in p:
                    out.append({"kind": "pause", "seconds": p["pause"]})
            continue
        who, body = key(m.group(1)), m.group(2)
        chunks, cur, events, flags = [], [], [], {}
        pos = 0
        for part in re.split(r"(\([^)]*\))", body):
            if not part.strip():
                continue
            if part.startswith("("):
                p = parse_direction(part[1:-1], names | {who})
                if "pause" in p:
                    if cur:
                        chunks.append({"text": " ".join(cur), "pause_after": p["pause"], "events": events})
                        cur, events = [], []
                    elif chunks:
                        chunks[-1]["pause_after"] += p["pause"]
                    else:
                        flags["pause_before"] = flags.get("pause_before", 0) + p["pause"]
                    continue
                for f in ("interrupts", "quick", "slow"):
                    if p.get(f):
                        flags[f] = True
                if "note" in p or any(p.get(f) for f in ("interrupts", "quick", "slow")):
                    continue
                events.append({"at_word": len(" ".join(cur).split()), **p})
            else:
                cur.append(" ".join(part.split()))
        if cur or events:
            chunks.append({"text": " ".join(cur), "pause_after": 0.0, "events": events})
        chunks = [c for c in chunks if c["text"].strip() or c["events"]]
        out.append({"kind": "line", "who": who, "text": " ".join(c["text"] for c in chunks if c["text"]).strip(),
                    "chunks": chunks, "flags": flags})
    return out


def speakers(entries):
    seen = []
    for e in entries:
        if e["kind"] == "line" and e["who"] not in seen:
            seen.append(e["who"])
    return seen


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(parse(open(sys.argv[1], encoding="utf-8").read()), ensure_ascii=False, indent=1))
