# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "onnxruntime==1.32.0", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Choose the material by measurement -> selection.json (hand choices in selection.json "manual" always win).

  start  shots of other characters (project.json "characters", shot "who"): no measured canon - the first variant is
         taken (a hand choice wins) and the sheet says "check by eye"; Claudia's streak / microphone check and the mic
         repair never run on them (Das Warum: the repair painted her headset and streak onto the male lead).
         With the config key face_id_model (ai-video face_id.py) their faces are compared with the character's
         "refs": the most similar variant is taken, an earlier pick stays unless it is a stranger (< 0.40) and another
         variant is not, and "WARNING ... no variant looks like <who>" says so before the clips are rendered.
         Claudia start images: canon check (ai-video canon.py) - ONE clay streak on the image left (her right),
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
Usage: uv run pick.py auto|start|broll|clips|all [<project>] [--curve rhubarb|level|mix] [--repair-mic] [--only s02,s05]
--only: pick these shots only (after a re-shoot); every other entry of selection.json stays as it is.
"""
import argparse
import json
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video")
import canon  # noqa: E402
import claudia  # noqa: E402
import clips  # noqa: E402
import face_id  # noqa: E402
import mouth  # noqa: E402
import sheets  # noqa: E402
from song_project import Project  # noqa: E402


def load(P):
    f = P.dir / "selection.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def write_atomic(path, text):
    """Temp file + replace: a reader (takes.py page, render_shots) never sees a half-written selection.json."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    for k in range(20):
        try:
            tmp.replace(path)
            return
        except PermissionError:                       # Windows: the other side has it open for a moment
            if k == 19:
                raise
            time.sleep(0.1)


def auto_of(e):
    """The automatic entry of a "clip" entry (a hand choice keeps the automatic one under "auto")."""
    return (e.get("auto") or None) if e.get("manual") else e


def save(P, sel):
    """The hand choices are read again just before writing: pick.py runs for minutes (night-run hook) and the user may
    choose on the takes page meanwhile - the page's "manual" wins, the automatic pick stays known under "auto"
    (takes.py: "back to automatic"; the page badges "automatic pick" from it)."""
    fresh = load(P)
    man = (fresh.get("manual") or {}).get("clip") or {}
    sel.setdefault("manual", {})
    sel["manual"] = dict(fresh.get("manual") or sel["manual"])
    clip = sel.setdefault("clip", {})
    for name in sorted(set(clip) | set(man)):
        auto = auto_of(clip.get(name) or {})
        if name in man:
            clip[name] = dict(man[name], manual=True, **({"auto": auto} if auto else {}))
        elif auto:
            clip[name] = auto
        else:
            clip.pop(name, None)
    write_atomic(P.dir / "selection.json", json.dumps(sel, ensure_ascii=False, indent=1))


def relp(P, p):
    return Path(p).resolve().relative_to(P.dir).as_posix()


def done(files):
    """Without unfinished renders (night_run writes <name>.part.<ext> first, comfy.py encodes to <name>.encoding.mp4)."""
    return [f for f in files if ".part." not in f.name and ".encoding." not in f.name]


OTHER_ENGINES = ("s2v", "infinitetalk", "humo", "minimax_h3", "ltx25")       # ai/<folder> of the non-LTX-2.3 takes


def multishot_faults(c, meta, q, s):
    """Picture faults of a clip that is MEANT to cut (clip json "cuts_expected", LTX-2.5 multi-shot): the wanted cuts are
    not "hidden cuts"; a missing cut (a dissolve, no cut at all) or extra ones are faults; on Claudia's shots a frame
    quarter, half and three quarters into every shot is checked for the canon - the streak gone (3 of 3 in the 8 s
    plugin test), a second hair clip (3 of 4 seeds in the trial), a second microphone, no face. Returns the list of reasons (empty = fine)."""
    want, n = int(meta.get("cuts_expected", 0)), max(int(meta.get("frames", 0)), 1)
    why = []
    if q["cut_events"] < want:
        why.append(f"cut missing ({q['cut_events']} of {want}: a dissolve or no cut)")
    elif q["cut_events"] > want:
        why.append(f"{q['cut_events'] - want} unwanted cut(s)")
    if not claudia.has_canon(s):
        return why
    edges = [0] + [f for f in q["cut_frames"] if 0 < f < n] + [n]
    for i, (a, b) in enumerate(zip(edges, edges[1:]), 1):
        res = canon.measure_frames(c, [(a + (b - a) * u) / n for u in (0.25, 0.5, 0.75)], claudia.STREAK, side_of(s))
        seen = [r for r in res if r.get("face")]
        if not seen:
            why.append(f"shot {i}: no face found")
        elif sum(bool(r.get("streak")) for r in seen) * 2 < len(seen):
            why.append(f"shot {i}: streak missing")
        elif max(r.get("clips", 0) for r in seen) >= 2:
            why.append(f"shot {i}: second hair clip")
        elif sum(bool(r.get("mic_both")) for r in seen) * 2 > len(seen):
            why.append(f"shot {i}: second microphone")
    return why


def side_of(s):
    return "image_right" if "behind" in (s.get("framing") or "").lower() else "image_left"


_REFS = {}


def face_sims(P, cast, cands):
    """Face similarity of every start image variant against the references of the shot's characters (ai-video
    face_id.py; only with the config key face_id_model): {file: value or None = no face}. Two characters with
    references: the lower of their values. Claudia is measured by her canon, not here."""
    people = [c for c in cast if c["name"] != "claudia" and c.get("refs")]
    if not people or not face_id.available():
        return {}
    for c in people:
        if c["name"] not in _REFS:
            _REFS[c["name"]] = face_id.reference([P.path(r) for r in c["refs"]])
    refs = [_REFS[c["name"]] for c in people if _REFS[c["name"]] is not None]
    if not refs:
        return {}
    out = {}
    for f in cands:
        vals = [face_id.similarity(f, r)["sim"] for r in refs]
        out[f] = None if any(v is None for v in vals) else min(vals)
    return out


def face_note(v):
    return "not found" if v is None else f"{v:.2f}" + (" STRANGER?" if v < face_id.STRANGER else "")


ONLY = None                                           # --only: the shots to pick (the others keep their entry)


def _sections(P):
    return [s for s in P.sections() if not ONLY or s["name"] in ONLY]


def pick_start(P, sel, log, rows, repair_mic=False):
    man = (sel.get("manual") or {}).get("start") or {}
    out = sel.setdefault("start", {})
    for s in _sections(P):
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
        if not claudia.has_canon(s):                 # another character: Claudia's streak / mic canon is not his
            cast = claudia.cast_of(s)
            who = "+".join(c["name"] for c in cast)
            sims = face_sims(P, cast, cands)         # {} without the config key face_id_model
            if not sims:
                rows += [(c, f"{who}: no measured canon - check face, hair and clothes by eye") for c in cands]
            else:
                rows += [(c, f"{who}: face {face_note(sims[c])} - check hair and clothes by eye") for c in cands]
            cur = out.get(name) if out.get(name) and P.path(out[name]).exists() else None
            val = lambda c: -1.0 if sims.get(c) is None else sims[c]  # noqa: E731
            best = max(cands, key=val) if sims else cands[0]
            if name in man:
                out[name] = man[name]
            elif cur is None:
                out[name] = relp(P, best)
            elif sims and val(best) >= face_id.STRANGER > val(next((c for c in cands if relp(P, c) == cur), best)):
                out[name] = relp(P, best)            # the picture picked before is a stranger, another one is not
            # else: the earlier pick stays (its clips may be rendered already)
            log.append(f"start {name}: {out[name]}  ({'by hand' if name in man else who + (', face ' + ', '.join(f'{c.stem[-2:]} {face_note(sims[c])}' for c in cands) if sims else ', no canon check - look at sheet_start.jpg')})")
            seen = [v for v in sims.values() if v is not None]
            if sims and name not in man and "from behind" not in (s.get("framing") or "").lower():
                if seen and max(seen) < face_id.STRANGER:
                    log.append(f"  WARNING {name}: no variant looks like {who} (best {max(seen):.2f} < {face_id.STRANGER})"
                               + (" - two people in the picture score lower, look at it" if len(cast) > 1 else
                                  " - frame closer (\"medium shot from the waist up\", the face lit) or make new variants "
                                  "before the clips are rendered"))
                elif not seen:
                    log.append(f"  note {name}: no face found in any variant ({who}) - check by eye")
            save(P, sel)
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
        # no variant passes: the least wrong one (streak present > streak on the right side > one mic > value), not
        # simply the first file name (user test: the fallback took the start image WITHOUT her streak)
        least_wrong = lambda c: (bool(res[c].get("streak")), not res[c].get("wrong"), not res[c].get("mic_both"),  # noqa: E731
                                 res[c].get("value", -1))
        best = max(ok, key=lambda c: res[c].get("value", -1)) if ok else max(cands, key=least_wrong)
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
    for s in _sections(P):
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
    for s in _sections(P):
        name, tech = s["name"], s["technique"]
        if name in man:                               # still rated: the takes page needs every take's lag / score
            log.append(f"clip {name}: by hand {man[name]} (the takes are rated anyway)")
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
            # every seed of the picked still (<shot>_<img>.mp4, <shot>_<img>_sd<seed>.mp4): a clean one first, then the
            # newest (a new seed is made because the old one failed); takes.py shows all of them
            cs = done(sorted((P.dir / "ai" / "moving").glob(f"{name}_{tag}.mp4"))
                      + sorted((P.dir / "ai" / "moving").glob(f"{name}_{tag}_*.mp4"))) if tag else []
            best = None
            for c in cs:
                q = mouth.motion_check(c)
                warn = [w for w, bad in (("HIDDEN CUT", q["cuts"]), ("FROZEN", q["frozen"]),
                                         ("little motion", q["motion"] < 3)) if bad]
                rows.append((c, f"moving  motion {q['motion']}  cuts {q['cuts']}  frozen run {q['frozen_run']}  "
                                + " ".join(warn)))
                if len(cs) > 1:
                    log.append(f"  moving {c.name}  motion {q['motion']} cuts {q['cuts']} frozen {q['frozen']}"
                               + (f"  -> {', '.join(warn)}" if warn else ""))
                rank = (not warn, c.stat().st_mtime)
                if best is None or rank > best[0]:
                    best = (rank, c, q, warn)
            if best and img and P.path(img).exists() and {"HIDDEN CUT", "FROZEN"} & set(best[3]):
                # user test 0.5.3: the automatic pick became a clip with a hidden cut - the still with the depth move
                # is the better automatic pick then (the clips stay on the takes page)
                _, c, q, warn = best
                out[name] = {"still": True, "warn": warn}
                log.append(f"clip {name}: still - every moving clip has {', '.join(warn)} (best {c.name})")
            elif best:
                _, c, q, warn = best
                out[name] = {"file": relp(P, c), "lag": 0, "qa": q, "warn": warn}
                log.append(f"clip {name}: {c.name}  motion {q['motion']} cuts {q['cuts']} frozen {q['frozen']}"
                           + (f"  -> {', '.join(warn)}: re-render with another seed (project.json shot \"seed\"), "
                              "or take the still on the takes page" if warn else ""))
            continue
        cands = sorted((P.dir / "ai" / "lipsync").glob(f"{name}_{tag}_s*.mp4")) + \
            [f for d in OTHER_ENGINES
             for f in sorted((P.dir / "ai" / d).glob(f"{name}_{tag}.mp4")) + sorted((P.dir / "ai" / d).glob(f"{name}_{tag}_sd*.mp4"))]
        cands = done(cands)
        known = {c.resolve() for c in cands}
        extra = [f for f in done(sorted((P.dir / "ai" / "lipsync").glob(f"{name}_*_s*.mp4"))
                                 + [g for d in OTHER_ENGINES
                                    for g in sorted((P.dir / "ai" / d).glob(f"{name}_*.mp4"))])
                 if f.resolve() not in known and clips.meta_path(f).exists()]   # other start images: page only
        if not cands and not extra:
            continue
        curves = curves or mouth.vocal_curves(P.dir, curve)
        rated = []
        for c in cands + extra:                       # extra: the hand pick on another start image - rated for the
            #                                           takes page (lag, score), never the automatic pick
            if not clips.meta_path(c).exists():       # unfinished render (killed before its json): not a candidate
                log.append(f"  {c.parent.name + '/' + c.name:36s} skipped - no {clips.meta_path(c).name} (re-render it)")
                continue
            meta = clips.read_meta(c)
            r = mouth.lip_score(c, s["from"], s["to"], curves, meta)
            score, lag, rl, mouth_shut = mouth.rating(r, "s2v" if meta.get("kind") == "s2v" else "ltx")
            q = mouth.motion_check(c)
            # the reason is logged as it is (user test: "mouth closed" stood for every rejection, also hidden cuts)
            if meta.get("cuts_expected"):                 # a clip that is meant to cut (engine ltx25)
                why = [w for w, bad in (("mouth closed", mouth_shut), ("frozen picture", q["frozen"])) if bad] + \
                    multishot_faults(c, meta, q, s)
            else:
                why = [w for w, bad in (("mouth closed", mouth_shut), (f"{q['cuts']} hidden cut(s)?", q["cuts"]),
                                        ("frozen picture", q["frozen"])) if bad]
            closed = bool(why)                            # rejected: hidden scene cut / picture stops / mouth shut
            if c not in extra:
                rated.append((score, c, lag, rl, closed, r))
            rows.append((c, f"r0 {r['r0']}  best {r['r_best']}@{r['lag']}  range {r['range']}  face {r['face']}  "
                            f"score {score}{'  REJECTED: ' + ', '.join(why) if why else ''}"))
            log.append(f"  {c.parent.name + '/' + c.name:36s} r0 {r['r0']}  r@{lag} {rl}  range {r['range']}  face {r['face']}  score {score}"
                       + (("  " + ", ".join(why)) if why else ""))
        if not rated:
            continue
        open_ = [x for x in rated if not x[4]] or rated
        if s.get("engine", "ltx") == "ltx" and any(x[1].parent.name == "lipsync" for x in open_):
            # the plan says LTX (test: after an engine switch the old S2V take won the automatic pick)
            open_ = [x for x in open_ if x[1].parent.name == "lipsync"]
        score, c, lag, rl, closed, r = max(open_, key=lambda x: x[0])
        out[name] = {"file": relp(P, c), "lag": lag, "score": score, "r": rl, "r0": r["r0"], "range": r["range"]}
        log.append(f"clip {name}: {c.parent.name}/{c.name}  lag {lag:+d}  score {score}")
        if all((x[3] or 0) < 0 for x in rated) and curve in ("rhubarb", "mix"):
            log.append(f"  WARNING {name}: every take correlates NEGATIVELY with the {curve} curve - the curve, not the "
                       "clips, may be off (user test: -0.6 with rhubarb, +0.77 with the level): pick again with --curve level")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["auto", "start", "broll", "clips", "all"])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--repair-mic", action="store_true", help="start: repair the mic when no variant passes (GPU)")
    ap.add_argument("--curve", choices=["rhubarb", "level", "mix", "both"],
                    help="vocal curve (default project lip_curve or mix = Rhubarb + vocal level, as the live film used: "
                         "Rhubarb alone went negative in loud choruses where the lips were right)")
    ap.add_argument("--only", help="shots, e.g. s02,s05 - the other shots keep their entry")
    a = ap.parse_args()
    P = Project(a.project)
    claudia.setup(P)
    global ONLY
    ONLY = {n.strip() for n in a.only.split(",") if n.strip()} if a.only else None
    unknown = sorted((ONLY or set()) - {s["name"] for s in P.sections()})
    if unknown:
        raise SystemExit(f"--only: no such shot: {', '.join(unknown)}")
    sel = load(P)
    log, rs, rb, rc = [], [], [], []
    if a.what in ("auto", "start", "all"):
        pick_start(P, sel, log, rs, a.repair_mic)
    if a.what in ("auto", "broll", "all"):
        pick_broll(P, sel, log, rb)
    if a.what in ("clips", "all"):
        pick_clips(P, sel, log, rc, a.curve or P.get("lip_curve", "mix"))
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
