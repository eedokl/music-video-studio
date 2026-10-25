"""Update an existing video to a slightly changed song (new Suno render, tweaked lyrics/timing).

plan()   matches the new lyric rows to the existing lines by text, so unchanged and slightly changed
         lines keep their id – scenes, events and anchors stay attached. New lines get new ids,
         removed lines disappear.
merge()  after the new analysis: keeps the storyboard, drops removed lines from scenes, puts new lines
         into the scene of the line before them, carries time anchors (intro/outro scenes, timed
         events) over to the new timing via the shift of the matched words, and records a summary.
"""
from __future__ import annotations

import copy
import difflib
import re

import numpy as np


def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def plan(old: dict, rows: list[dict]) -> dict:
    """→ {"ids": id per new row, "status": per new row (same|changed|new), "removed": [old ids], "matched": {new_i: old_id}}"""
    old_lines = old.get("lyrics", {}).get("lines", [])
    a = [_norm(l["text"]) for l in old_lines]
    b = [_norm(r["text"]) for r in rows]
    ids: list[str | None] = [None] * len(rows)
    status = ["new"] * len(rows)
    used: set[str] = set()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                ids[j1 + k] = old_lines[i1 + k]["id"]
                status[j1 + k] = "same"
        elif op == "replace":
            # pair changed lines by similarity (best first)
            pairs = sorted(((difflib.SequenceMatcher(a=a[i], b=b[j]).ratio(), i, j) for i in range(i1, i2) for j in range(j1, j2)), reverse=True)
            taken_i: set[int] = set()
            for r, i, j in pairs:
                if r < 0.55 or i in taken_i or ids[j] is not None:
                    continue
                ids[j] = old_lines[i]["id"]
                status[j] = "changed"
                taken_i.add(i)
    used = {x for x in ids if x}
    removed = [l["id"] for l in old_lines if l["id"] not in used]
    nums = [int(m.group(1)) for l in old_lines if (m := re.fullmatch(r"l(\d+)", l["id"]))]
    nxt = (max(nums) + 1) if nums else 0
    for j in range(len(rows)):
        if ids[j] is None:
            ids[j] = f"l{nxt}"
            nxt += 1
    return {"ids": ids, "status": status, "removed": removed}


def _time_map(old: dict, new: dict):
    """old song time → new song time, from matched word starts (piecewise linear, monotone)."""
    old_by = {l["id"]: l for l in old.get("lyrics", {}).get("lines", [])}
    pts = []
    for l in new["lyrics"]["lines"]:
        o = old_by.get(l["id"])
        if not o or l.get("unsung") or o.get("unsung") or _norm(o["text"]) != _norm(l["text"]):
            continue
        for wo, wn in zip(o["words"], l["words"]):
            pts.append((wo["t"], wn["t"]))
    pts.sort()
    # keep it monotone (drop crossing points)
    mono = []
    for p in pts:
        if not mono or (p[0] > mono[-1][0] + 1e-3 and p[1] > mono[-1][1] + 1e-3):
            mono.append(p)
    if len(mono) < 2:
        return (lambda t: t), 0.0
    xo = np.array([p[0] for p in mono])
    xn = np.array([p[1] for p in mono])

    def f(t: float) -> float:
        if t <= xo[0]:
            # before the first word: stretch the intro proportionally (0:00 stays 0:00)
            return float(t * xn[0] / xo[0]) if xo[0] > 0.5 else float(t + (xn[0] - xo[0]))
        if t >= xo[-1]:
            return float(t + (xn[-1] - xo[-1]))
        return float(np.interp(t, xo, xn))

    return f, float(np.median(xn - xo))


def merge(old: dict, new: dict, info: dict) -> dict:
    """Carry the storyboard of `old` over to the freshly analysed `new` project (in place)."""
    ids_new = {l["id"] for l in new["lyrics"]["lines"]}
    order = [l["id"] for l in new["lyrics"]["lines"]]
    tmap, shift = _time_map(old, new)
    for k in ("scenes", "events", "looks", "settings", "title", "storyline", "stylePrompt", "world", "legacy"):
        if k in old:
            new[k] = copy.deepcopy(old[k])
    new["lyrics"]["lead"] = old.get("lyrics", {}).get("lead", 0.08)

    def fix_anchor(a: dict | None):
        if not a:
            return a
        if a.get("kind") == "time":
            a["t"] = round(tmap(a["t"]), 3)
        elif a.get("kind") == "word" and a.get("line") not in ids_new:
            return None
        return a

    # scenes: drop removed lines, add new lines to the scene of the line before them
    scene_of: dict[str, dict] = {}
    for sc in new.get("scenes", []):
        sc["lines"] = [x for x in sc.get("lines", []) if x in ids_new]
        for x in sc["lines"]:
            scene_of[x] = sc
        st = fix_anchor(sc.get("start"))
        sc["start"] = st if st else {"kind": "auto"}
    added = [order[j] for j, s in enumerate(info["status"]) if s == "new"]
    for lid in added:
        i = order.index(lid)
        prev = next((order[k] for k in range(i - 1, -1, -1) if order[k] in scene_of), None)
        target = scene_of.get(prev) if prev else (new["scenes"][0] if new.get("scenes") else None)
        if target is not None:
            pos = target["lines"].index(prev) + 1 if prev in target["lines"] else len(target["lines"])
            target["lines"].insert(pos, lid)
            scene_of[lid] = target
    # events
    evs = []
    for ev in new.get("events", []):
        ev["at"] = fix_anchor(ev.get("at"))
        if not ev["at"]:
            continue
        if ev.get("until"):
            ev["until"] = fix_anchor(ev["until"])
        evs.append(ev)
    new["events"] = evs
    # imported engines: the original code addresses lines by its own index
    if new.get("legacy", {}).get("lineMap"):
        from .legacy import word_map

        if new["legacy"].get("origLines"):
            # re-map the original engine's lines onto the new lyrics at word level (merged/split lines)
            new["legacy"]["lineMap"] = word_map(new["legacy"]["origLines"], new["lyrics"]["lines"])
        else:
            new["legacy"]["lineMap"] = [x if (x if isinstance(x, str) else (x or {}).get("id")) in ids_new else None for x in new["legacy"]["lineMap"]]
    texts = {l["id"]: l["text"] for l in new["lyrics"]["lines"]}
    new["lastUpdate"] = {
        "added": [{"id": x, "text": texts[x]} for x in added],
        "changed": [{"id": order[j], "text": texts[order[j]]} for j, s in enumerate(info["status"]) if s == "changed"],
        "removed": [{"id": x, "text": t} for x, t in ((l["id"], l["text"]) for l in old.get("lyrics", {}).get("lines", [])) if x in info["removed"]],
        "medianShift": round(shift, 3),
        "legacyNote": bool(new.get("world") == "legacy" and added),
    }
    return new
