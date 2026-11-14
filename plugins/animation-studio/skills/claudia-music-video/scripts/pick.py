# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Choose the material by measurement -> selection.json (hand choices in selection.json "manual" always win).

  start  Claudia start images: canon check (ai-video canon.py) - ONE clay streak on the image left (her right),
         nothing orange on the other side beyond the clip, ONE headset boom (on the streak side, none on the other
         cheek); best value wins. No variant passes -> v1 + warning (look at sheet_start.jpg).
         Shots seen from behind ("from behind" in the framing): the streak is on the image right.
         --repair-mic: when NO variant passes only because of the microphone (two booms / boom on the wrong cheek),
         the best variant with a correct streak is repaired (ai-video mic_repair.py: retouch the wrong boom, FLUX
         texture refine; else Qwen-Edit "change only the microphone") -> ai/start/<shot>_v<k>m.png, which is then
         measured and picked like any variant (GPU lock taken and released by the repair).
  broll  B-roll stills: the first variant without letterbox bars, unless chosen by hand (look at sheet_broll.jpg:
         FLUX invents lettering on charts, screens and signs - pick another variant by hand)
  clips  lip-sync shots: every LTX seed (and S2V) with the chosen start image is measured against the vocals
         (ai-video mouth.py): rating = r at the best lag within +-3 frames - 0.02/frame - 0.2 if the mouth stays closed
         (+0.05 S2V). Clips whose mouth stays closed (range < 0.1), with a hidden scene cut or a frozen stretch
         (mouth.motion_check) are rejected when any other candidate is fine.
         The chosen lag is stored: lag > 0 = mouth late -> the cut shows the clip dt = +lag/24 s later.
         moving / claudia_moving shots: the clip made from the picked image, checked for hidden cuts, frozen
         stretches and too little motion (< 3) - warnings say "re-render with another seed".
         placed shots ("clip": an existing singing clip without its sound, e.g. an old Wan clip): entry frame and
         tempo 0.9-1.1 fitted to the vocal curve (mouth.fit_placement), stored in the clip's json.
  auto   start + broll (night-run hook between the image and the video phases)
  all    everything; then contact sheets: sheet_start.jpg, sheet_broll.jpg, sheet_clips.jpg (with the numbers)
selection.json: {"start": {"s02": "ai/start/s02_v2.png"}, "broll": {...}, "clip": {"s02": {"file": ..., "lag": 0,
  "score": 0.59, "r": 0.59, "range": 0.21}}, "manual": {"start": {"s05": "ai/start/s05_v1.png"}, "clip": {"s07": {"file":
  "ai/lipsync/s07_v2_s1.mp4", "lag": 2}}}}
Usage: uv run pick.py auto|start|broll|clips|all [<project>] [--curve rhubarb|level|mix] [--repair-mic]
"""
import argparse
import json
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video")
import canon  # noqa: E402
import claudia  # noqa: E402
import clips  # noqa: E402
import mouth  # noqa: E402
import sheets  # noqa: E402
from song_project import Project  # noqa: E402


def load(P):
    f = P.dir / "selection.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save(P, sel):
    (P.dir / "selection.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")


def relp(P, p):
    return Path(p).resolve().relative_to(P.dir).as_posix()


def done(files):
    """Without unfinished renders (night_run writes <name>.part.<ext> first, comfy.py encodes to <name>.encoding.mp4)."""
    return [f for f in files if ".part." not in f.name and ".encoding." not in f.name]


def side_of(s):
    return "image_right" if "behind" in (s.get("framing") or "").lower() else "image_left"


def pick_start(P, sel, log, rows, repair_mic=False):
    man = (sel.get("manual") or {}).get("start") or {}
    out = sel.setdefault("start", {})
    for s in P.sections():
        if s["technique"] not in ("lipsync", "claudia_moving"):
            continue
        name = s["name"]
        if s.get("start_image"):                     # given start image (re-shoot): nothing to choose
            out[name] = s["start_image"]
            log.append(f"start {name}: given {s['start_image']}")
            continue
        cands = done(sorted((P.dir / "ai" / "start").glob(f"{name}_v*.png")))
        if not cands:
            continue
        res = {c: canon.measure(c, claudia.STREAK, side_of(s)) or {} for c in cands}
        for c, m in res.items():
            rows.append((c, f"streak {'yes' if m.get('streak') else 'NO'}  wrong side {'YES' if m.get('wrong') else 'no'}"
                            f"  mic {'TWO/WRONG SIDE' if m.get('mic_both') else ('missing?' if m.get('mic_missing') else 'ok')}"
                            f"  value {m.get('value', -1):.2f}"))
        if name in man:
            out[name] = man[name]
            log.append(f"start {name}: by hand {man[name]}")
            save(P, sel)
            continue
        ok = [c for c in cands if res[c].get("streak") and not res[c].get("wrong") and not res[c].get("mic_both")]
        if not ok and repair_mic:
            fix = [c for c in cands if res[c].get("streak") and not res[c].get("wrong") and res[c].get("face")]
            if fix:
                import mic_repair
                src = max(fix, key=lambda c: res[c].get("value", -1))
                try:
                    r = mic_repair.repair(src, P.dir / "ai" / "start" / "mic_repair", side_of(s),
                                          edit_prompt=claudia.MIC_EDIT, edit_neg=claudia.MIC_EDIT_NEG, color=claudia.STREAK)
                except (SystemExit, Exception) as ex:    # one broken repair must not lose the other shots' picks
                    r = {"ok": False, "note": f"failed ({type(ex).__name__}: {str(ex)[:160]})"}
                log.append(f"start {name}: mic repair of {src.name}: " + (r["method"] if r["ok"] else r.get("note", "failed")))
                if r["ok"]:
                    dst = src.with_name(src.stem + "m.png")
                    dst.write_bytes(Path(r["out"]).read_bytes())
                    res[dst] = canon.measure(dst, claudia.STREAK, side_of(s)) or {}
                    cands.append(dst)
                    rows.append((dst, f"MIC REPAIRED ({r['method']}) - check the cheek by eye  value {res[dst].get('value', -1):.2f}"))
                    log.append(f"start {name}: {dst.name} is a mic repair - look at the cheek/jaw on sheet_start.jpg (the retouch "
                               "can leave a patch where the boom crossed the hair edge); reject it in selection.json manual if so")
                    ok = [dst] if mic_repair.passes(res[dst]) else []
        best = max(ok, key=lambda c: res[c].get("value", -1)) if ok else cands[0]
        out[name] = relp(P, best)
        log.append(f"start {name}: {best.name}" + ("" if ok else "  (NO variant passes: streak on the image left, one mic - check by eye, "
                                                         "or make new variants)") +
                   "  [" + ", ".join(f"{c.stem[-2:]} {res[c].get('value', -1):.2f}" for c in cands) + "]")
        save(P, sel)                                  # per shot: a crash later keeps the picks made so far


def letterbox(path):
    """FLUX sometimes paints cinema bars: dark full-width bands at the top and bottom."""
    import cv2
    from cvio import imread
    g = imread(path, cv2.IMREAD_GRAYSCALE)
    if g is None:
        return False
    h = g.shape[0]
    band = max(4, h // 30)
    return bool(g[:band].mean() < 12 and g[-band:].mean() < 12 and g[h // 3:2 * h // 3].mean() > 30)


def pick_broll(P, sel, log, rows):
    man = (sel.get("manual") or {}).get("broll") or {}
    out = sel.setdefault("broll", {})
    for s in P.sections():
        if s["technique"] != "broll":
            continue
        if s.get("start_image"):
            out[s["name"]] = s["start_image"]
            continue
        cands = done(sorted((P.dir / "ai" / "broll").glob(f"{s['name']}_v*.png")))
        bars = {c: letterbox(c) for c in cands}
        rows += [(c, "LETTERBOX bars" if bars[c] else "") for c in cands]
        if s["name"] in man:
            out[s["name"]] = man[s["name"]]
        elif cands and s["name"] not in out:
            ok = [c for c in cands if not bars[c]] or cands
            out[s["name"]] = relp(P, ok[0])
        if cands:
            log.append(f"broll {s['name']}: {out[s['name']]}")


def pick_clips(P, sel, log, rows, curve):
    man = (sel.get("manual") or {}).get("clip") or {}
    out = sel.setdefault("clip", {})
    curves = None
    for s in P.sections():
        name, tech = s["name"], s["technique"]
        if name in man:
            out[name] = man[name]
            log.append(f"clip {name}: by hand {man[name]}")
            continue
        if tech == "typo":
            continue
        if tech == "placed":                          # existing singing clip: entry frame + tempo by mouth curve
            c = P.path(s["clip"])
            curves = curves or mouth.vocal_curves(P.dir, curve)
            meta = clips.read_meta(c) if clips.meta_path(c).exists() else {}
            if "clip_start" not in meta or meta.get("song_start") != s["from"]:
                b = mouth.fit_placement(c, s["from"], s["to"], curves)
                meta = dict(meta, kind="placed", delay_frames=0,
                            **{k: b[k] for k in ("song_start", "clip_start", "tempo", "fps")})
                clips.write_meta(c, **meta)
            r = mouth.lip_score(c, s["from"], s["to"], curves, meta, max_lag=0)
            out[name] = {"file": s["clip"], "lag": 0, "r": r["r0"], "range": r["range"]}
            rows.append((c, f"placed: entry {meta['clip_start']} tempo {meta.get('tempo', 1)}  r {r['r0']}"))
            log.append(f"clip {name}: placed {Path(s['clip']).name} entry {meta['clip_start']} "
                       f"tempo {meta.get('tempo', 1)} r {r['r0']}")
            continue
        src = (sel.get("start") if tech != "broll" else sel.get("broll") or {}) or {}
        img = src.get(name)
        tag = Path(img).stem.split("_")[-1] if img else None
        if tech in ("broll", "claudia_moving"):
            c = P.dir / "ai" / "moving" / f"{name}_{tag}.mp4" if tag else None
            if c and c.exists():
                q = mouth.motion_check(c)
                warn = [w for w, bad in (("HIDDEN CUT", q["cuts"]), ("FROZEN", q["frozen"]),
                                         ("little motion", q["motion"] < 3)) if bad]
                out[name] = {"file": relp(P, c), "lag": 0, "qa": q, "warn": warn}
                rows.append((c, f"moving  motion {q['motion']}  cuts {q['cuts']}  frozen run {q['frozen_run']}  "
                                + " ".join(warn)))
                log.append(f"clip {name}: {c.name}  motion {q['motion']} cuts {q['cuts']} frozen {q['frozen']}"
                           + (f"  -> {', '.join(warn)}: re-render with another seed" if warn else ""))
            continue
        cands = sorted((P.dir / "ai" / "lipsync").glob(f"{name}_{tag}_s*.mp4")) + \
            [f for d in ("s2v", "infinitetalk", "humo", "minimax_h3") for f in sorted((P.dir / "ai" / d).glob(f"{name}_{tag}.mp4"))]
        cands = done(cands)
        if not cands:
            continue
        curves = curves or mouth.vocal_curves(P.dir, curve)
        rated = []
        for c in cands:
            if not clips.meta_path(c).exists():       # unfinished render (killed before its json): not a candidate
                log.append(f"  {c.parent.name + '/' + c.name:36s} skipped - no {clips.meta_path(c).name} (re-render it)")
                continue
            meta = clips.read_meta(c)
            r = mouth.lip_score(c, s["from"], s["to"], curves, meta)
            score, lag, rl, closed = mouth.rating(r, "s2v" if meta.get("kind") == "s2v" else "ltx")
            q = mouth.motion_check(c)
            closed = closed or bool(q["cuts"] or q["frozen"])   # hidden scene cut / picture stops: reject
            rated.append((score, c, lag, rl, closed, r))
            rows.append((c, f"r0 {r['r0']}  best {r['r_best']}@{r['lag']}  range {r['range']}  face {r['face']}  "
                            f"score {score}{'  REJECTED' if closed else ''}  cuts {q['cuts']} frozen {q['frozen']}"))
            log.append(f"  {c.parent.name + '/' + c.name:36s} r0 {r['r0']}  r@{lag} {rl}  range {r['range']}  face {r['face']}  score {score}"
                       + ("  mouth closed" if closed else ""))
        if not rated:
            continue
        open_ = [x for x in rated if not x[4]] or rated
        score, c, lag, rl, closed, r = max(open_, key=lambda x: x[0])
        out[name] = {"file": relp(P, c), "lag": lag, "score": score, "r": rl, "r0": r["r0"], "range": r["range"]}
        log.append(f"clip {name}: {c.parent.name}/{c.name}  lag {lag:+d}  score {score}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["auto", "start", "broll", "clips", "all"])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--repair-mic", action="store_true", help="start: repair the mic when no variant passes (GPU)")
    ap.add_argument("--curve", choices=["rhubarb", "level", "mix", "both"], help="vocal curve (default project lip_curve or rhubarb)")
    a = ap.parse_args()
    P = Project(a.project)
    sel = load(P)
    log, rs, rb, rc = [], [], [], []
    if a.what in ("auto", "start", "all"):
        pick_start(P, sel, log, rs, a.repair_mic)
    if a.what in ("auto", "broll", "all"):
        pick_broll(P, sel, log, rb)
    if a.what in ("clips", "all"):
        pick_clips(P, sel, log, rc, a.curve or P.get("lip_curve", "rhubarb"))
    save(P, sel)
    with open(P.dir / "picks.log", "a", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")
    print("\n".join(log))
    if a.what == "all":
        for nm, rows in (("start", rs), ("broll", rb), ("clips", rc)):
            if rows:
                for w in sheets.sheet(P.dir / f"sheet_{nm}.jpg", rows):
                    print("->", w.name)


if __name__ == "__main__":
    main()
