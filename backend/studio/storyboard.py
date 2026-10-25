"""A first storyboard without AI, so the preview works right after the analysis.

One scene per line pair (chants like "Hey!" get their own big scene), camera shots and light looks
by section, key words of the lines on the LED wall, CO2 at chorus starts, sparks on held notes,
confetti in the final chorus and a fireworks finale in the outro. The user refines it in the
editor or via the chat.
"""
from __future__ import annotations

import re

LOOKS: dict[str, dict] = {
    "intro": {"beams": ["#3d6bff", "#8fb0ff"], "wash": "#1a2a8a", "energy": 0.12, "pattern": "still", "phones": 0.7, "blackout": 0.65},
    "introUp": {"beams": ["#3d6bff", "#ffffff"], "wash": "#2a3cff", "energy": 0.35, "pattern": "up", "phones": 0.5},
    "verse1": {"beams": ["#ffcc00", "#ffffff", "#ff8a2a"], "wash": "#ff7a1a", "energy": 0.5, "pattern": "sweep"},
    "pre": {"beams": ["#3d6bff", "#8fb0ff"], "wash": "#1a3cff", "energy": 0.3, "pattern": "still", "follow": 1},
    "chorus": {"beams": ["#e3001b", "#ffcc00", "#ffffff"], "wash": "#e3001b", "energy": 0.92, "pattern": "fan", "pyro": True, "strobe": True},
    "hey": {"beams": ["#e3001b", "#ffffff"], "wash": "#ff2030", "energy": 1, "pattern": "chase", "pyro": True, "strobe": True},
    "verse2": {"beams": ["#8b4dff", "#3d8bff", "#ffffff"], "wash": "#5a2cff", "energy": 0.58, "pattern": "crowd"},
    "spoken": {"beams": ["#ffffff"], "wash": "#30303a", "energy": 0.18, "pattern": "still", "follow": 1},
    "bridge": {"beams": ["#3d6bff", "#a8c0ff"], "wash": "#0a1c5a", "energy": 0.22, "pattern": "up", "phones": 0.85, "follow": 0.8},
    "final": {"beams": ["#ffcc00", "#ffffff", "#3d6bff"], "wash": "#ffb300", "energy": 1, "pattern": "fan", "pyro": True, "strobe": True},
    "instrumental": {"beams": ["#e3001b", "#ffcc00", "#ffffff"], "wash": "#e3001b", "energy": 0.8, "pattern": "sweep", "pyro": True},
    "outro": {"beams": ["#ffcc00", "#3d6bff", "#ffffff"], "wash": "#ffb300", "energy": 0.95, "pattern": "sweep", "pyro": True},
    "ring": {"beams": ["#ffcc00", "#3d6bff"], "wash": "#ffb300", "energy": 0.6, "pattern": "up", "phones": 0.5, "ring": 1},
    "blackout": {"beams": ["#ffcc00"], "wash": "#000000", "energy": 0, "pattern": "still", "phones": 0.4, "ring": 1, "blackout": 1},
}

SHOTS = {
    "verse1": ["wall", "pit", "wide", "wall", "orbit", "singer"],
    "verse2": ["wall", "pit", "wide", "wall", "wing", "singer"],
    "chorus": ["crane", "pit", "crowd", "drums"],
    "bridge": ["wide", "wall", "singer"],
    "final": ["crane", "crowd", "drums", "pit", "wall", "singer"],
    "intro": ["crowd", "wide"],
    "outro": ["wide", "drums", "crane"],
}
CAM = {"wide": "CAM 1 · WIDE", "wall": "CAM 2 · LED", "singer": "CAM 3 · CLOSE", "orbit": "CAM 4 · STEADY", "pit": "CAM 5 · PIT", "crane": "CAM 6 · CRANE", "crowd": "CAM 7 · CROWD", "drums": "CAM 8 · DRUMS", "guitar": "CAM 9 · GUITAR", "wing": "CAM 10 · WING", "top": "CAM 11 · SKY", "bass": "CAM 12 · BASS", "keys": "CAM 13 · KEYS"}

STOP = set("the and und die der das ein eine to of in on we wir you ich is ist are with mit for für doch noch that this baby now out into".split())


def _is_chant(text: str) -> bool:
    return bool(re.match(r"^\W*hey\b", text, re.I))


def _key_words(lines: list[dict], n: int = 3) -> list[tuple[str, int, int]]:
    """longest meaningful words of the lines → (text, line index in list, word index)"""
    cand = []
    for li, l in enumerate(lines):
        for wi, w in enumerate(l["words"]):
            t = re.sub(r"[^\wÄÖÜäöüß'-]", "", w["w"])
            if len(t) >= 4 and t.lower() not in STOP:
                cand.append((len(t), t.upper(), li, wi))
    cand.sort(key=lambda c: -c[0])
    pick = sorted(cand[:n], key=lambda c: (c[2], c[3]))
    return [(c[1], c[2], c[3]) for c in pick]


def build(project: dict) -> tuple[list[dict], list[dict], dict]:
    lines = [l for l in project["lyrics"]["lines"] if not l.get("unsung")]
    dur = project["audio"]["duration"]
    held_by_line = {h["line"]: h["name"] for h in project.get("held", [])}
    scenes: list[dict] = []
    events: list[dict] = []
    sid = 0

    def add(**kw):
        nonlocal sid
        sid += 1
        sc = {"id": f"s{sid}", **kw}
        sc.setdefault("cam", CAM.get(sc.get("shot", ""), ""))
        scenes.append(sc)
        return sc

    title = project.get("title", "")
    first_t = lines[0]["words"][0]["t"] if lines else dur
    # ---- intro
    if first_t > 3:
        add(name="Intro", start={"kind": "time", "t": 0}, lines=[], shot="crowd", seed=2, look="intro", wall={"type": "title", "params": {"title": title.upper(), "subtitle": "LIVE", "stars": True, "reveal": 0.6}}, lyr="none")
        if first_t > 8:
            add(name="Lights up", start={"kind": "time", "t": round(first_t * 0.45, 2)}, lines=[], shot="wide", seed=1, look="introUp", wall={"type": "title", "params": {"title": title.upper(), "subtitle": "LIVE", "stars": True}}, lyr="none")

    # ---- lyric scenes: group by section, pairs, chants alone
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for l in lines:
        chant = _is_chant(l["text"])
        if cur and (chant or _is_chant(cur[0]["text"]) or l["section"] != cur[0]["section"] or len(cur) >= 2):
            groups.append(cur)
            cur = []
        cur.append(l)
    if cur:
        groups.append(cur)

    counters: dict[str, int] = {}
    prev_end = first_t
    chorus_starts = []
    for g in groups:
        sec = g[0]["section"]
        start_t = g[0]["words"][0]["t"]
        # instrumental gap before this group → its own scene
        if start_t - prev_end > 6 and scenes:
            add(name="Instrumental", start={"kind": "time", "t": round(prev_end + 0.6, 2)}, lines=[], shot="guitar", seed=sid, look="instrumental", wall={"type": "eq", "params": {"title": title.upper()}}, lyr="none")
        k = counters.get(sec, 0)
        counters[sec] = k + 1
        chant = _is_chant(g[0]["text"])
        shots = SHOTS.get(sec, SHOTS["verse1"])
        shot = "crowd" if chant else shots[k % len(shots)]
        look = "hey" if chant else ("chorus" if sec == "chorus" else sec if sec in LOOKS else "verse1")
        if chant:
            wall = {"type": "bigword", "params": {"text": "HEY!", "flash": True}}
        elif sec in ("chorus", "final") and k % 2 == 0:
            wall = {"type": "stars", "params": {"text": g[0]["text"].upper().rstrip(",.")[:28]}}
        else:
            kws = _key_words(g)
            wall = {"type": "words", "params": {"items": [{"text": t, "at": {"kind": "word", "line": g[li]["id"], "word": wi, "edge": "start"}} for t, li, wi in kws]}}
        sc = add(name=g[0]["text"][:40], start={"kind": "auto"}, lines=[l["id"] for l in g], shot=shot, seed=sid, look=look, wall=wall, lyr="big" if chant else "low")
        held = {l["id"]: held_by_line[l["id"]] for l in g if l["id"] in held_by_line}
        if held:
            sc["held"] = held
            for lid in held:
                ln = next(l for l in g if l["id"] == lid)
                w = len(ln["words"]) - 1
                events.append({"type": "sparks", "at": {"kind": "word", "line": lid, "word": w, "edge": "start"}, "until": {"kind": "word", "line": lid, "word": w, "edge": "end", "offset": 0.5}})
        if sec in ("chorus", "final") and k == 0:
            chorus_starts.append(g[0])
        prev_end = g[-1]["words"][-1]["e"]

    for l in chorus_starts:
        events.append({"type": "co2", "at": {"kind": "word", "line": l["id"], "word": 0, "edge": "start"}})
    finals = [l for l in lines if l["section"] == "final"] or [l for l in lines if l["section"] == "chorus"][-4:]
    if finals:
        l = finals[min(3, len(finals) - 1)]
        events.append({"type": "confetti", "at": {"kind": "word", "line": l["id"], "word": len(l["words"]) - 1, "edge": "start"}})

    # ---- outro
    last_e = lines[-1]["words"][-1]["e"] if lines else 0
    out_len = dur - last_e
    if out_len > 4:
        t0 = last_e + 0.6
        add(name="Finale", start={"kind": "time", "t": round(t0, 2)}, lines=[], shot="wide", seed=34, look="outro", wall={"type": "title", "params": {"title": title.upper(), "subtitle": "LIVE", "stars": True}}, lyr="none")
        n = max(2, int(out_len / 1.6))
        for i in range(min(10, n)):
            events.append({"type": "fireworks", "at": {"kind": "time", "t": round(t0 + 0.4 + i * min(1.6, out_len / (n + 1)), 2)}})
        if out_len > 12:
            add(name="Star ring", start={"kind": "time", "t": round(dur - min(10, out_len * 0.4), 2)}, lines=[], shot="top", seed=37, look="ring", wall={"type": "title", "params": {"title": "DANKE", "subtitle": title.upper(), "stars": True}}, lyr="none")
        add(name="Blackout", start={"kind": "time", "t": round(dur - 1.8, 2)}, lines=[], shot="wide", seed=39, look="blackout", wall={"type": "title", "params": {"title": "DANKE", "subtitle": title.upper()}}, lyr="none")
    return scenes, events, LOOKS
