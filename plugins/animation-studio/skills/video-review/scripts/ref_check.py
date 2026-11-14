# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# ///
"""Reference check: compare a rebuilt film against a reference film AT THE MOMENTS WHERE SOMETHING HAPPENS.

Lesson from rebuilding "Prompts!": 3-5 stills per section and SSIM numbers missed behaviour between the stills - an
empty caption box while a figure broke out of the page, a narrator inset that stayed after its singer stopped, a
lettering gag that never reached the film. Effects in hand-made reference scripts often have no script of their own
(a few lines inside a scene script), so an inventory of SCRIPTS does not catch them. Two tools:

  events     <project> [--out events.json]
             candidate moments from a song project: section starts, every lyric line start, every word that triggers
             a gag / screen event / steam / sound / prop / badge, transitions -> events.json [{"t", "what"}]
  sheets     --ref ref.mp4 --mine film.mp4 (--events events.json | --checklist checklist.json) [--out refcheck/]
             [--offset 0] [--around -0.5,0,0.5,1.0] [--width 320]
             one strip per moment (frames at t + each "around" offset, reference above, rebuild below, SSIM each),
             refcheck/report.md sorted worst first, refcheck/report.json. --offset = reference time - film time.
  checklist  checklist.json is written by hand (or by Claude) from the reference CODE and from WATCHING the
             reference - one entry per visible element, with when it comes AND when/why it goes:
             [{"id": "caption-p4", "what": "comic caption box p4, couplet, top left",
               "appear": 93.1, "disappear": 99.3, "rule": "one box per panel, held until the next panel"}, ...]
             `sheets --checklist` makes strips around appear and disappear (t-0.25, t+0.25) and a report table with
             an empty "status" column to fill in (ok / different / missing) after looking at every strip.

Usage: uv run ref_check.py events <project>
       uv run ref_check.py sheets --ref r.mp4 --mine m.mp4 --events e.json
"""
import argparse
import json
import sys
from pathlib import Path

import _studio
_studio.use("song-analysis")
from frames import frame_at, ssim  # noqa: E402


def events_from_project(pdir):
    from song_project import Project, word_matches
    P = Project(pdir)
    sheet = P.sheet()
    words, lines = sheet["words"], sheet["lines"]
    ev = [{"t": float(s["from"]), "what": f"section {s['name']}"} for s in P.sections()]
    ev += [{"t": float(l["t"]), "what": f"line: {l['text'][:50]}"} for l in lines]
    for key in ("gags", "screen", "steam", "sounds", "props", "silhouettes"):
        for r in P.get(key, []) or []:
            pre = r.get("word") or r.get("show_on")
            if not pre:
                if r.get("at") is not None:
                    ev.append({"t": float(r["at"]), "what": f"{key}: {r.get('sfx', '')}"})
                continue
            last = -99
            for w in words:
                if word_matches(w["word"], pre) and w["t"] - last > 1.0:
                    ev.append({"t": float(w["t"]), "what": f"{key} '{pre}': {r.get('text') or r.get('window') or r.get('sfx') or r.get('image') or ''}"[:80]})
                    last = w["t"]
    for b in P.get("screen_badges", []) or []:
        if b.get("on"):
            t = next((w["t"] for w in words if word_matches(w["word"], b["on"])), None)
            if t is not None:
                ev.append({"t": float(t), "what": f"badge {b.get('text')}"})
    for tr in P.get("transitions", []) or []:
        if tr.get("at") is not None:
            ev.append({"t": float(tr["at"]), "what": f"transition {tr.get('kind')}"})
    ev.sort(key=lambda e: e["t"])
    out, last = [], -9
    for e in ev:                                   # merge moments closer than 0.4 s
        if out and e["t"] - last < 0.4:
            out[-1]["what"] += " | " + e["what"]
        else:
            out.append(dict(e))
            last = e["t"]
    return out


def strip(path, ts, ref, mine, offset, width):
    from PIL import Image, ImageDraw
    rows, scores = [[], []], []
    for t in ts:
        a = frame_at(ref, t + offset, width)
        b = frame_at(mine, t, width)
        scores.append(ssim(a, b)[0])
        rows[0].append(a)
        rows[1].append(b)
    h = rows[0][0].height
    img = Image.new("RGB", (width * len(ts), 2 * h + 36), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, t in enumerate(ts):
        img.paste(rows[0][i].resize((width, h)), (i * width, 18))
        img.paste(rows[1][i].resize((width, h)), (i * width, 36 + h))
        d.text((i * width + 4, 3), f"ref {t + offset:.2f}s", fill="#ffd23f")
        d.text((i * width + 4, 21 + h), f"mine {t:.2f}s SSIM {scores[i]:.2f}", fill="#7fe3ff")
    img.save(path, quality=85)
    return scores


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("events")
    e.add_argument("project")
    e.add_argument("--out", default="events.json")
    s = sub.add_parser("sheets")
    s.add_argument("--ref", required=True)
    s.add_argument("--mine", required=True)
    s.add_argument("--events")
    s.add_argument("--checklist")
    s.add_argument("--out", default="refcheck")
    s.add_argument("--offset", type=float, default=0.0)
    s.add_argument("--around", default="-0.5,0,0.5,1.0")
    s.add_argument("--width", type=int, default=320)
    a = ap.parse_args()
    if a.cmd == "events":
        ev = events_from_project(a.project)
        Path(a.out).write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(ev)} moments -> {a.out}")
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    items = []
    if a.checklist:
        for c in json.loads(Path(a.checklist).read_text(encoding="utf-8")):
            for key in ("appear", "disappear"):
                if c.get(key) is not None:
                    items.append({"t": float(c[key]), "what": f"{c.get('id', '')} {key}: {c.get('what', '')}",
                                  "rule": c.get("rule", ""), "around": [-0.25, 0.25]})
    if a.events:
        around = [float(x) for x in a.around.split(",")]
        items += [dict(x, around=around) for x in json.loads(Path(a.events).read_text(encoding="utf-8"))]
    if not items:
        sys.exit("give --events and/or --checklist")
    res = []
    for i, it in enumerate(items):
        ts = [max(0.0, it["t"] + o) for o in it["around"]]
        name = f"m{i:03d}_{it['t']:.2f}.jpg"
        sc = strip(out / name, ts, a.ref, a.mine, a.offset, a.width)
        res.append({"t": it["t"], "what": it["what"], "rule": it.get("rule", ""), "min_ssim": round(min(sc), 3),
                    "sheet": name, "status": ""})
        print(f"{it['t']:8.2f}  SSIM min {min(sc):.2f}  {it['what'][:70]}")
    (out / "report.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Reference check", "", f"reference `{a.ref}` (offset {a.offset:+.2f} s) vs rebuild `{a.mine}`", "",
          "Worst first. Look at EVERY strip; fill in status (ok / different / missing) and what differs.", "",
          "| t | min SSIM | moment | rule | sheet | status |", "|---|---|---|---|---|---|"]
    for r in sorted(res, key=lambda r: r["min_ssim"]):
        md.append(f"| {r['t']:.2f} | {r['min_ssim']:.2f} | {r['what'].replace('|', '/')} | {r['rule']} | "
                  f"[{r['sheet']}]({r['sheet']}) | |")
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(res)} strips -> {out}/report.md")


if __name__ == "__main__":
    main()
