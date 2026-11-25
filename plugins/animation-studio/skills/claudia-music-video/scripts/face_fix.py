# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "onnxruntime==1.32.0", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Far faces: rebuild the small face of the picked sung takes (ai-video face_pass.py) and put the fixed clips into
selection.json. Run it after the pick (and the takes page), before render_shots.py.

In wide shots LTX smears a face under ~85 px (at 1024 wide): crooked, half-closed eyes that change every frame. The
pass re-generates only the face crop (LTX-2.3 + Lightricks pixel upscaler IC-LoRA, start-image face as anchor, vocals
riding along) and blends it back; ~1.6 s GPU per frame (4-6 min per 7-s take). Test of five ways and the first film:
references/lessons.md ("Far faces").

  uv run face_fix.py <proj> --list                  measure the picked takes, show which are "far" (CPU, no GPU)
  uv run face_fix.py <proj> [--only s04,s08]         fix the far ones -> ai/lipsync/<clip>_g.mp4 (+ .sheet.jpg)
                                                     and selection.json manual clip = the fixed clip (same lag)
  --no-select   fix but leave selection.json alone;  --redo   render the face again (GPU, e.g. another --seed)
  --blend       blend the kept pass (ai/lipsync/face_pass/<clip>/) in again - no GPU
  --max-face N  threshold in px (default 85; project.json "face_fix": {"max_face": N})
  --tracker     auto (default): MediaPipe; RetinaFace (CPU PyTorch, own uv env, ~350 MB once) only where MediaPipe
                finds no face or loses it (< 90 % of the frames) while the face is under 110 px - profiles, tiny
                faces, crowds; mediapipe / retinaface = always that one (project.json "face_fix": {"tracker": ...})
Project keys: "face_fix": false = never; shot "face_fix": true / false = always / never for that shot (true also
fixes a face above the threshold); shot "face_hint": [x, y] (0-1) = which face in the first frame when several are seen
(default: the large face nearest the middle). Moving B-roll clips (no vocals) are not fixed.
Afterwards: render_shots.py --only <fixed shots> + make_film.py. Look at the sheets: the face can look a little more
made-up, a streak near the face can widen - in that case set the shot's manual clip back to the original.
"""
import argparse
import json
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video")
import clips  # noqa: E402
import face_pass  # noqa: E402
import pick  # noqa: E402
from song_project import Project  # noqa: E402


def current(sel, name):
    """(file, lag) of the clip the cut uses for a shot: the hand choice, else the automatic pick."""
    man = ((sel.get("manual") or {}).get("clip") or {}).get(name)
    e = man or (sel.get("clip") or {}).get(name)
    return (e.get("file"), e.get("lag", 0)) if e and e.get("file") else (None, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--only", help="comma-separated shot names")
    ap.add_argument("--list", action="store_true", help="measure only, no GPU")
    ap.add_argument("--max-face", type=float)
    ap.add_argument("--tracker", choices=face_pass.TRACKERS + ("auto",))
    ap.add_argument("--seed", type=int, default=face_pass.SEED)
    ap.add_argument("--no-select", action="store_true")
    ap.add_argument("--redo", action="store_true", help="render the face again (GPU; with another --seed)")
    ap.add_argument("--blend", action="store_true", help="blend the kept pass in again (no GPU)")
    a = ap.parse_args()
    P = Project(a.project)
    cfg = P.get("face_fix", {})
    if cfg is False:
        raise SystemExit('project.json "face_fix": false - nothing to do')
    limit = a.max_face or (cfg.get("max_face") if isinstance(cfg, dict) else None) or face_pass.SMALL
    tracker = a.tracker or (cfg.get("tracker") if isinstance(cfg, dict) else None) or "auto"
    if tracker not in face_pass.TRACKERS + ("auto",):
        raise SystemExit(f'project.json "face_fix": unknown tracker {tracker!r} - one of auto, '
                         f'{", ".join(face_pass.TRACKERS)}')
    only = set(a.only.split(",")) if a.only else None
    sel = pick.load(P)
    todo, rows = [], []
    for s in P.sections():
        name = s["name"]
        if only and name not in only:
            continue
        rel, lag = current(sel, name)
        if not rel:
            continue
        clip = P.dir / rel
        meta = clips.read_meta(clip) if clips.meta_path(clip).exists() else {}
        if meta.get("face_fix_from"):                       # already fixed
            if not a.redo:
                rows.append((name, rel, "fixed", ""))
                continue
            clip = clip.with_name(meta["face_fix_from"])
            meta = clips.read_meta(clip)
        if not meta.get("audio") or not meta.get("image") or "moving" in str(meta.get("kind", "")):
            continue                                        # B-roll / still: no vocals to ride along
        if s.get("face_fix") is False:
            rows.append((name, rel, "off (shot)", ""))
            continue
        hint = s.get("face_hint")
        m, used = face_pass.measure_auto(clip, hint, tracker)
        if m["face"] is None:
            rows.append((name, rel, "no face", ""))
            continue
        far = m["low"] < limit or s.get("face_fix") is True
        size = f"median {m['face']:.0f} px, small part {m['low']:.0f} px" + (
            f", {m['hits']}/{m['frames']} frames" if m.get("frames") and m["hits"] < 0.9 * m["frames"] else "") + (
            ", retinaface" if used == "retinaface" else "")
        rows.append((name, rel, "FAR" if far else "ok", size))
        if far:
            todo.append((name, clip, lag, hint, used))
    for name, rel, state, size in rows:
        print(f"{name:6s} {state:10s} {size:34s} {rel}")
    print(f"{len(todo)} far take(s) (threshold {limit:.0f} px, tracker {tracker}): {', '.join(t[0] for t in todo) or '-'}"
          + (f" - about {len(todo) * 5} min GPU" if todo else ""))
    if a.list or not todo:
        return
    done = []
    for name, clip, lag, hint, used in todo:
        out = clip.with_name(clip.stem + "_g.mp4")
        if out.exists() and not (a.redo or a.blend):
            print(f"  {name}: {out.name} exists - kept (--blend blends the kept pass again, --redo renders it again)")
        else:
            face_pass.fix(clip, out, hint=hint, seed=a.seed, redo=a.redo, tracker=used)
        done.append((name, out, lag))
    if a.no_select:
        print("selection.json left alone (--no-select)")
    else:
        sel = pick.load(P)                                  # fresh: the takes page may have changed it meanwhile
        man = sel.setdefault("manual", {}).setdefault("clip", {})
        for name, out, lag in done:
            man[name] = {"file": pick.relp(P, out), "lag": lag}
            auto = pick.auto_of((sel.get("clip") or {}).get(name) or {})
            sel.setdefault("clip", {})[name] = dict(man[name], manual=True, **({"auto": auto} if auto else {}))
        pick.write_atomic(P.dir / "selection.json", json.dumps(sel, ensure_ascii=False, indent=1))
        print(f"selection.json: manual clip of {', '.join(d[0] for d in done)} = the face-fixed clip")
    print("look at ai/lipsync/*_g.sheet.jpg, then: render_shots.py --only "
          + ",".join(d[0] for d in done) + " and make_film.py")


if __name__ == "__main__":
    main()
