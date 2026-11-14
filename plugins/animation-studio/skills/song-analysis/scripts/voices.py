# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""Who sings when? Assign the mouth shapes to the figures -> analysis/assignment.json (scenes only read this file).

Two questions, two sources:
  WHO sings      -> from the sound: earshot "man singing" vs "woman singing" every 0.5 s (analysis/gender.json),
                    not from pitch (male pop vocals often sit at 200-350 Hz)
  AS WHOM        -> from the lyrics: a section that names a figure in the 3rd person and never says "I" is narrated -
                    the male voice goes to the narrator (project.json "narrator") while the figure acts it out
Rules for the lead voice, in this order:
  1  the sung text contains an entry of "announcements", or the marker says robotic/announcer -> the "announcer" figure
     (works without lyrics too: then the Whisper words around that moment are checked)
  1b marker says narrator                                                -> the narrator
  2  marker names a figure and says whisper/spoken                       -> that figure (earshot cannot hear whispers)
  3  male -> the "male" figure (in narrated sections: the narrator); female -> the "female" figure
  4  unclear -> same as before
  5  corrections.json in the project ([{"from": s, "to": s, "figure": "tim", "reason": "..."}]) is applied last -
     the listener's ear always wins and survives every re-run
Backing vocals (only with a backing stem): always the OTHER figure (call and response).
Gaps (voice audible, mouth closed - held notes) are filled with alternating open shapes C/B.
Output: assignment.json, lines.csv (evidence per lyric line), lip-sync check (gaps >= 0.3 s).
Usage: uv run voices.py [<project>]
"""
import json
import re
import sys

import numpy as np

import _studio  # noqa: E402
_studio.use('song-analysis')
from media import voice_activity
from song_project import Project

M_THR, F_THR = 0.03, -0.01
FIRST_PERSON = re.compile(r"\b(ich|mein|meine|meinen|meinem|mir|mich|i|me|my|mine|i'm|i've|je|moi|yo|mi)\b", re.I)


def main():
    P = Project(sys.argv[1] if len(sys.argv) > 1 else ".")
    fps = P.fps
    figs = P["figures"]
    role = lambda v: next((k for k, f in figs.items() if f.get("voice") == v), None)
    MALE, FEMALE, ANN = role("male"), role("female"), role("announcer")
    NARR = P.get("narrator") if P.get("narrator") in figs else ANN
    sheet = P.sheet()
    lines, words = sheet["lines"], sheet["words"]
    markers = P.markers()

    v_lead = voice_activity(P.analysis / "vocals_lead.wav", fps)
    has_back = (P.analysis / "backing_mouth.json").exists()
    v_back = voice_activity(P.analysis / "vocals_backing.wav", fps) if has_back else np.zeros_like(v_lead)
    n = min(len(v_lead), len(v_back)) if has_back else len(v_lead)

    gt = json.loads((P.analysis / "gender.json").read_text(encoding="utf-8")) if (P.analysis / "gender.json").exists() else []
    gt_t = np.array([g["t"] for g in gt]) if gt else np.zeros(0)
    gt_d = np.array([g["d"] for g in gt]) if gt else np.zeros(0)
    if len(gt_d) > 2:
        gt_d = np.array([np.median(gt_d[max(i - 1, 0):i + 2]) for i in range(len(gt_d))])

    def gender(t0, t1):
        if not len(gt_t):
            return "?"
        m = (gt_t >= t0 - 0.25) & (gt_t <= t1 + 0.25)
        if not m.any():
            m = np.abs(gt_t - (t0 + t1) / 2) == np.abs(gt_t - (t0 + t1) / 2).min()
        d = float(gt_d[m].mean())
        return "m" if d > M_THR else "f" if d < F_THR else "?"

    marker_of = {}
    for i in range(len(lines)):
        before = [m["marker"] for m in markers if m["line"] <= i]
        marker_of[i] = before[-1] if before else ""
    names = list(figs)
    ann = [a.lower() for a in P.get("announcements", [])]
    is_ann = lambda txt: any(a in txt.lower() for a in ann)
    narrated = set()
    for lab in set(marker_of.values()):
        txts = [lines[i]["text"] for i in range(len(lines)) if marker_of[i] == lab and not is_ann(lines[i]["text"])]
        names_hero = any(re.search(rf"\b{re.escape(nm)}\b", x, re.I) for x in txts for nm in names if nm != NARR)
        if txts and names_hero and not any(FIRST_PERSON.search(x) for x in txts):
            narrated.add(lab)

    def line_at(t):
        cur = None
        for i, l in enumerate(lines):
            if l["t"] - 0.15 <= t <= l["end"] + 0.4:
                cur = i
        return cur

    def text_at(t):
        li = line_at(t)
        if li is not None:
            return lines[li]["text"]
        return " ".join(w["word"] for w in words if t - 1.5 <= w["t"] <= t + 1.5)

    def shapes(cues):
        form = ["X"] * n
        for (t, s), nxt in zip(cues, cues[1:] + [(n / fps, "X")]):
            for i in range(int(t * fps), min(int(nxt[0] * fps), n)):
                form[i] = s
        return form

    lead_cues = [(c["start"], c["value"]) for c in
                 json.loads((P.analysis / "lead_mouth.json").read_text(encoding="utf-8"))["mouthCues"]]
    lead_form = shapes(lead_cues)
    lead_who = [None] * n
    prev = FEMALE or MALE
    for (t, s), nxt in zip(lead_cues, lead_cues[1:] + [(n / fps, "X")]):
        li = line_at(t)
        lab = marker_of.get(li, "") if li is not None else ""
        g = gender(t, nxt[0])
        named = [nm for nm in names if re.search(rf"\b{re.escape(nm)}\b", lab, re.I)]
        if ANN and s != "X" and (is_ann(text_at(t)) or re.search(r"robotic|announc", lab, re.I)):
            who = ANN
        elif NARR and re.search(r"narrat|erz[aä]hl", lab, re.I):
            who = NARR
        elif named and re.search(r"whisper|spoken|fl[uü]ster", lab, re.I):
            who = named[0]
        elif g == "m" and MALE:
            who = NARR if (lab in narrated and NARR) else MALE
        elif g == "f" and FEMALE:
            who = FEMALE
        else:
            who = prev
        prev = who
        for i in range(int(t * fps), min(int(nxt[0] * fps), n)):
            lead_who[i] = who
    corr = P.dir / "corrections.json"
    if corr.exists():
        for k in json.loads(corr.read_text(encoding="utf-8")):
            for i in range(int(k["from"] * fps), min(int(k["to"] * fps) + 1, n)):
                lead_who[i] = k["figure"]
    filled = 0
    for i in range(n):
        if v_lead[i] and lead_form[i] in ("X", "A"):
            lead_form[i] = "C" if (i // 3) % 2 == 0 else "B"
            lead_who[i] = lead_who[i] or prev
            filled += 1

    back_form, back_who = ["X"] * n, [None] * n
    if has_back:
        back_form = shapes([(c["start"], c["value"]) for c in
                            json.loads((P.analysis / "backing_mouth.json").read_text(encoding="utf-8"))["mouthCues"]])
        last = MALE
        for i in range(n):
            if lead_who[i] and lead_form[i] != "X":
                last = lead_who[i]
            if v_back[i] and back_form[i] in ("X", "A"):
                back_form[i] = "C" if (i // 3) % 2 == 0 else "B"
                filled += 1
            if back_form[i] != "X" or v_back[i]:
                back_who[i] = MALE if last == FEMALE else FEMALE

    out = {"fps": fps, "figures": {k: [] for k in figs}}
    last_s = {k: None for k in figs}
    open_any = np.zeros(n, bool)
    for i in range(n):
        for k in figs:
            s = "X"
            if lead_who[i] == k and lead_form[i] != "X":
                s = lead_form[i]
            elif back_who[i] == k and back_form[i] != "X":
                s = back_form[i]
            if s not in ("X", "A"):
                open_any[i] = True
            if s != last_s[k]:
                out["figures"][k].append([round(i / fps, 3), s])
                last_s[k] = s
    (P.analysis / "assignment.json").write_text(json.dumps(out, indent=0), encoding="utf-8")

    with open(P.analysis / "lines.csv", "w", encoding="utf-8") as fh:
        fh.write("time;marker;narrated;voice;" + ";".join(f"lead_{k}" for k in figs) + ";text\n")
        for i, l in enumerate(lines):
            a, b = int(l["t"] * fps), min(int(l["end"] * fps), n)
            c = lambda k: sum(1 for j in range(a, b) if lead_who[j] == k and lead_form[j] not in ("X", "A"))
            fh.write(f"{l['t']:.1f};{marker_of[i]};{'yes' if marker_of[i] in narrated else ''};{gender(l['t'], l['end'])};"
                     + ";".join(str(c(k)) for k in figs) + f";{l['text']}\n")

    voice = v_lead[:n] | (v_back[:n] if has_back else False)
    gaps, start = [], None
    for i in range(n + 1):
        g = i < n and voice[i] and not open_any[i]
        if g and start is None:
            start = i
        elif not g and start is not None:
            if i - start >= 0.3 * fps:
                gaps.append((round(start / fps, 2), round(i / fps, 2)))
            start = None
    share = {k: sum(1 for t, s in v if s not in "XA") for k, v in out["figures"].items()}
    print(f"open mouth changes per figure: {share}; narrated sections: {sorted(narrated) or '-'}; filled frames: {filled}")
    print(f"lip-sync gaps >= 0.3 s: {len(gaps)} {gaps[:8]}")
    print("-> analysis/assignment.json, analysis/lines.csv")


if __name__ == "__main__":
    main()
