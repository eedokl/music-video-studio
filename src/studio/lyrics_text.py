"""Parse lyrics as the user pastes them: [Section] headers, one sung line per row."""

from __future__ import annotations

import re

SECTION_IDS = ["intro", "verse1", "chorus", "verse2", "bridge", "final", "outro"]


def section_of(header: str, verses_seen: int) -> str:
    h = header.lower()
    if "intro" in h:
        return "intro"
    if "outro" in h or h.strip("[] ") == "end":
        return "outro"
    if "final" in h or "last" in h:
        return "final"
    if "pre" in h and "chorus" in h:
        return "verse1" if verses_seen <= 1 else "verse2"
    if "bridge" in h or "breakdown" in h:
        return "bridge"
    if "chorus" in h or "refrain" in h or "hook" in h or "drop" in h:
        return "chorus"
    if "speaker" in h or "spoken" in h:
        return "verse2" if verses_seen >= 2 else "verse1"
    return "verse1" if verses_seen <= 1 else "verse2"


def parse(text: str) -> list[dict]:
    """→ [{"section": .., "text": .., "header": "[Chorus]"}] (headers and (stage directions) dropped)."""
    rows, sec, verses, header = [], "verse1", 0, ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^\[.*\]$", line):
            header = line
            if re.search(r"verse|strophe", line, re.I):
                verses += 1
            sec = section_of(line, verses)
            continue
        if re.match(r"^\(.*\)$", line):
            continue
        rows.append({"section": sec, "text": line, "header": header})
    return rows


def plain(rows: list[dict]) -> str:
    """Lyrics file for align.py / transcribe.py (headers kept as comments align.py skips)."""
    out, last = [], None
    for r in rows:
        if r["header"] != last:
            out.append(r["header"] or "[Verse]")
            last = r["header"]
        out.append(r["text"])
    return "\n".join(out) + "\n"
