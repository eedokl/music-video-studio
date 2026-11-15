# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Shot plan from the song: cuts on the sung lines (snapped to beats), a technique per shot, framing and camera.

Reads the song-analysis results (analysis/song_sheet.json: beats, lines; markers.json: [Verse]/[Chorus] ...) and writes
project.json "sections" = shots (film-finish cuts one section per shot):
  {"name": "s03", "from": 9.71, "to": 12.87, "line": "PowerPoint und Strategien,", "marker": "Verse 1",
   "technique": "lipsync|broll|claudia_moving", "engine": "ltx|s2v", "framing": "medium shot", "camera": "...",
   "look": "grey_morning", "lyrics": true,
   "idea": "", "action": "", "set": "", "set_short": "", "subject": "", "motion": ""}     <- the creative brief fills these
  lipsync shots also get "manner" (how she sings: "softly", "with energy") + "action" (a small movement) from the
  look (claudia.SING_MOODS, seeded) - the brief may replace both
Rules: one shot per sung line (cut 0.08 s before the first syllable, onto a beat if one is within 0.2 s); intro and
instrumental gaps > 2.5 s become B-roll shots; shots longer than --max-len are split on the beat nearest the middle,
shorter than 1.2 s merged. Techniques are drawn with the project's creative seed (creative.rng): about --lipsync share
of the sung shots sing on camera, never three of the same in a row. --s2v: lip-sync shots with a HELD note (longest
sung word >= 1.4 s, not in a [Speaker]/spoken part, shot <= 4.7 s) get engine "s2v", at most 15 % of the sung shots
(~15 min GPU each). Set "engine" by hand for an emotional close-up the rule misses.
Framings and cameras never repeat back to back. A new seed gives a different plan; ideas recorded by the user win.
Usage: uv run plan.py [<project>] [--version studio|live] [--lipsync 0.5] [--max-len 5.0] [--no-s2v] [--force]
  S2V (Wan2.2-S2V) for held notes is on by default (rule of the Europe 2031 studio film, see the s2v block below);
  --no-s2v = LTX only.
"""
import argparse
import json

import _studio  # noqa: E402
_studio.use("song-analysis")
import creative  # noqa: E402
import claudia  # noqa: E402
from media import duration  # noqa: E402
from song_project import Project  # noqa: E402

LIVE_LOOK = {"intro": "intro", "verse": "verse", "pre": "verse", "chorus": "chorus", "refrain": "chorus",
             "bridge": "bridge", "outro": "finale", "speaker": "spoken", "spoken": "spoken"}


def snap(t, beats, tol=0.2):
    if not beats:
        return t
    b = min(beats, key=lambda x: abs(x - t))
    return b if abs(b - t) <= tol else t


def cuts_from_lines(lines, beats, length, max_len, pre=0.08, gap=2.5, min_len=1.2):
    """-> [(t0, t1, line or None)]"""
    pts = []
    for i, ln in enumerate(lines):
        pts.append((round(snap(max(0.0, ln["t"] - pre), beats), 3), ln))
        nxt = lines[i + 1]["t"] if i + 1 < len(lines) else length
        if nxt - ln["end"] > gap:
            pts.append((round(snap(ln["end"] + 0.3, beats), 3), None))
    if not pts or pts[0][0] > 1.0:
        pts.insert(0, (0.0, None))
    else:
        pts[0] = (0.0, pts[0][1])
    segs = [(t, (pts[i + 1][0] if i + 1 < len(pts) else length), ln) for i, (t, ln) in enumerate(pts)]
    out = []
    for t0, t1, ln in segs:                                       # merge too short shots into the previous one
        if out and t1 - t0 < min_len:
            a0, _, aln = out[-1]
            out[-1] = (a0, t1, aln or ln)
        else:
            out.append((t0, t1, ln))
    if len(out) > 1 and out[0][1] - out[0][0] < min_len:          # a too short intro joins the first line
        out[1] = (0.0, out[1][1], out[1][2])
        out.pop(0)
    res = []
    for t0, t1, ln in out:                                        # split long shots on a beat near the middle
        while t1 - t0 > max_len:
            mid = snap((t0 + min(t1, t0 + max_len * 2)) / 2, beats, 0.6)
            mid = mid if t0 + min_len < mid < t1 - min_len else (t0 + t1) / 2
            res.append((t0, round(mid, 3), ln))
            t0, ln = round(mid, 3), None if ln is None else dict(ln, cont=True)
        res.append((t0, t1, ln))
    return res


def marker_of(line_idx, markers):
    m = [x for x in markers if x["line"] <= line_idx]
    return m[-1]["marker"] if m else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--version", choices=["studio", "live"])
    ap.add_argument("--lipsync", type=float, help="share of sung shots with lip-sync (default 0.5)")
    ap.add_argument("--max-len", type=float, default=5.0)
    ap.add_argument("--s2v", action="store_true", help=argparse.SUPPRESS)     # old flag: S2V is on by default now
    ap.add_argument("--no-s2v", action="store_true", help="no Wan2.2-S2V shots (LTX only; S2V ~11-18 min per shot)")
    ap.add_argument("--force", action="store_true", help="replace a plan that already has creative fields")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("claudia-music-video")                 # project.json validated before any long step
    if any(s.get("idea") for s in P.sections()) and not a.force:
        raise SystemExit("project.json already has a shot plan with ideas - use --force to replace it")
    sheet = P.sheet()
    beats = [b["t"] for b in sheet.get("beats", [])]
    length = round(duration(P.song), 3)
    lines = sheet.get("lines", [])
    if not lines:
        raise SystemExit("no sung lines in analysis/song_sheet.json - check the lyrics and run analyze.py")
    p = P.p
    p.setdefault("video", "claudia-music-video")
    version = a.version or p.get("version", "studio")
    p["version"] = version
    p["look"] = "none"                      # the photographic finish (grain + vignette) is applied by render_shots.py
    brief = p.setdefault("brief", {})
    share = a.lipsync if a.lipsync is not None else brief.get("lipsync_share", 0.5)
    seed = creative.seed(P)
    r = creative.rng(P, "plan:technique")
    markers = P.markers()
    looks = list(claudia.LOOKS[version])
    default_look = brief.get("look") or creative.pick(P, "plan:look", looks)
    shots, hist = [], []
    last_framing, last_cam = None, None
    for i, (t0, t1, ln) in enumerate(cuts_from_lines(lines, beats, length, a.max_len)):
        sung = ln is not None
        if not sung:
            tech = "broll"
        elif hist[-2:] == ["lipsync", "lipsync"]:
            tech = "broll"
        elif hist[-2:] in (["broll", "broll"], ["claudia_moving", "broll"], ["broll", "claudia_moving"]):
            tech = "lipsync"
        else:                                                     # seeded, but keeps the share over the film
            n_sung = sum(1 for x in shots if x["lyrics"]) + 1
            have = sum(1 for x in shots if x["technique"] == "lipsync")
            due = share * n_sung - have
            tech = "lipsync" if (due > 0.5 or (due > -0.5 and r.random() < share)) else "broll"
        if tech == "broll" and sung and r.random() < brief.get("claudia_moving_share", 0.15):
            tech = "claudia_moving"
        engine = "ltx"
        fr = [f for f in claudia.FRAMINGS.get(tech, [""]) if f != last_framing] or [""]
        cams = [c for c in claudia.CAMERAS[tech if tech in claudia.CAMERAS else "broll"] if c != last_cam]
        framing = r.choice(fr) if tech != "broll" else ""
        cam = r.choice(cams)
        last_framing, last_cam = framing or last_framing, cam
        mk = marker_of(ln["line"], markers) if sung else ""
        lk = default_look
        if version == "live":
            key = next((v for k, v in LIVE_LOOK.items() if k in mk.lower()), None)
            lk = key or default_look
        lk = (brief.get("look_by_marker") or {}).get(mk, lk)
        name = f"s{i + 1:02d}"
        shots.append({"name": name, "from": round(t0, 3), "to": round(t1, 3),
                      # a line over two shots: both carry its text (the lip-sync prompt sings it; empty gave the
                      # model no words - user test); "cont" marks the continuation
                      "line": (ln["text"] if sung else "(instrumental)"), "cont": bool(sung and ln.get("cont")),
                      "marker": mk, "technique": tech, "engine": engine, "framing": framing, "camera": cam, "look": lk,
                      "lyrics": sung, "idea": "", "action": "", "set": "", "set_short": "", "subject": "", "motion": ""})
        if tech == "lipsync":                        # mood + a small movement from the look (V1 of the Europe 2031 run:
            used = {x.get("action") for x in shots[:-1]}
            shots[-1]["manner"], shots[-1]["action"] = claudia.sing_mood(lk, creative.rng(P, f"mood:{name}"), used)  # the brief may change them
        for idea in creative.ideas(P, name):                 # ideas already recorded for this shot (user ideas win)
            if idea.get("by") == "user" or not shots[-1]["idea"]:
                shots[-1]["idea"] = idea["idea"]
        hist.append(tech)
    if not a.no_s2v:
        # Wan2.2-S2V for held notes, the rule of the Europe 2031 studio film (planung/shotplan.py waehle()): candidates
        # hold a sung word >= 0.7 s, ranked by held seconds - 0.25 x words per second (slow lines first), at most a
        # quarter of the singing shots and 6 per film (S2V costs 11-18 min a shot); spoken / rap parts stay LTX.
        # There V3 kept S2V in 5 of 6 such shots; jobs.py renders 1 LTX seed next to every S2V clip, so the take page
        # (takes.py) can still switch a shot to LTX.
        held = []
        for s in shots:
            ws = [w for w in sheet.get("words", []) if s["from"] <= w["t"] < s["to"]]
            spoken = any(k in s["marker"].lower() for k in ("speak", "spoken", "rap"))
            if s["technique"] != "lipsync" or not ws or spoken or s["to"] - s["from"] > 4.7:
                continue
            hold = max(w["end"] - w["t"] for w in ws)
            if hold >= 0.7:
                held.append((hold - 0.25 * len(ws) / (s["to"] - s["from"]), hold, s))
        cap = min(6, max(1, round(0.25 * sum(x["technique"] == "lipsync" for x in shots))))
        for _, hold, s in sorted(held, key=lambda x: -x[0])[:cap]:
            s["engine"] = "s2v"
            s["engine_reason"] = f"held note {hold:.1f} s"
    if "lipsync" not in hist:
        k = max(range(len(shots)), key=lambda j: len(shots[j]["line"]))
        shots[k]["technique"] = "lipsync"
    p["sections"] = shots
    P.file.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    cnt = {t: sum(s["technique"] == t for s in shots) for t in ("lipsync", "broll", "claudia_moving")}
    print(f"-> {len(shots)} shots ({cnt}), seed {seed}, version {version}, look {default_look}")
    for s in shots:
        eng = s.get("engine", "ltx") if s["technique"] == "lipsync" else ""
        print(f"  {s['name']} {s['from']:7.2f}-{s['to']:7.2f} {s['technique']:14s} {eng:4s} {s['framing'] or '':22s} "
              f"{s['camera']:22s} {s['line'][:40]}" + (f"  ({s['engine_reason']})" if s.get("engine_reason") else ""))
    print("Next: write the creative brief into each shot (idea, action, set, set_short / subject, motion) - see SKILL.md")


if __name__ == "__main__":
    main()
