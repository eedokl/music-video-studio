# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Measure a talking scene: lip sync (open-mouth frames vs voice activity), duration, contact sheet - optionally
against a reference scene.

  uv run check_sync.py [--project .] [--video film.mp4]
         [--ref-mouth ref/mouth.json --ref-voice ref/voice.wav --ref-video ref/film.mp4 --ref-who pip]
Per figure (frames at the project fps; the mouth is drawn one frame early, as in the scene):
  open        frames with an open mouth (Rhubarb B-H; X rest and A closed lips count as closed)
  agreement   share of frames where "mouth open" == "voice audible" (voice_<who>.wav, studio-core media)
  precision   open frames that have voice / all open frames      recall  voiced frames with an open mouth
  silent gaps voice audible but mouth closed for >= 0.3 s (a held vowel without a mouth)
Reference: the same numbers for the reference, plus the frame agreement of both open-mouth tracks and the shift
(frames) that matches them best. Writes analysis/sync_check.json, contact_sheet.png (+ compare_sheets.png).
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis")
from media import contact_sheet, duration, ffmpeg, voice_activity  # noqa: E402
from song_project import Project  # noqa: E402

OPEN = set("BCDEFGH")


def open_track(cues, n, fps, offset=-1):
    out = np.zeros(n, bool)
    cues = sorted((float(t), s) for t, s in cues)
    for (t, s), nxt in zip(cues, cues[1:] + [(1e9, "X")]):
        a, b = max(round(t * fps) + offset, 0), min(round(nxt[0] * fps) + offset, n)
        if s in OPEN and b > a:
            out[a:b] = True
    return out


def stats(op, va):
    n = min(len(op), len(va))
    op, va = op[:n], va[:n]
    gaps, run = 0, 0
    for v, o in zip(va, op):
        run = run + 1 if (v and not o) else 0
        gaps += run == 8
    return {"frames": int(n), "open": int(op.sum()), "voiced": int(va.sum()),
            "agreement": round(float((op == va).mean()), 3) if n else 0,
            "precision": round(float((op & va).sum() / max(op.sum(), 1)), 3),
            "recall": round(float((op & va).sum() / max(va.sum(), 1)), 3), "silent_gaps": int(gaps)}


def best_shift(a, b, r=6):
    n = min(len(a), len(b))
    sc = {s: float((np.roll(a[:n], s) == b[:n]).mean()) for s in range(-r, r + 1)}
    s = max(sc, key=sc.get)
    return s, round(sc[s], 3), round(sc[0], 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--video")
    ap.add_argument("--ref-mouth")
    ap.add_argument("--ref-voice")
    ap.add_argument("--ref-video")
    ap.add_argument("--ref-who")
    a = ap.parse_args()
    P = Project(a.project)
    fps = P.fps
    video = Path(a.video) if a.video else P.dir / "film.mp4"
    ASG = P.assignment()["figures"]
    res = {"video": video.name, "duration_s": round(duration(video), 3) if video.exists() else None,
           "frames": len(list((P.dir / "scenes" / "dialogue").glob("f.*.png"))), "figures": {}}
    tracks = {}
    for k, cues in ASG.items():
        vw = P.analysis / f"voice_{k}.wav"
        if not vw.exists():
            continue
        va = voice_activity(vw, fps)
        op = open_track(cues, len(va), fps)
        tracks[k] = op
        res["figures"][k] = stats(op, va)
    if a.ref_mouth and a.ref_voice:
        rc = [(c["start"], c["value"]) for c in json.loads(Path(a.ref_mouth).read_text(encoding="utf-8"))["mouthCues"]]
        rva = voice_activity(a.ref_voice, fps)
        rop = open_track(rc, len(rva), fps)
        ref = {"stats": stats(rop, rva), "duration_s": round(duration(a.ref_video), 3) if a.ref_video else None}
        who = a.ref_who or next(iter(tracks), None)
        if who in tracks:
            s, sc, sc0 = best_shift(tracks[who], rop)
            ref["open_track_agreement"] = sc0
            ref["best_shift_frames"] = s
            ref["agreement_at_best_shift"] = sc
            ref["open_frames_ours_vs_ref"] = [int(tracks[who].sum()), int(rop.sum())]
        res["reference"] = ref
    sheet = P.dir / "contact_sheet.png"
    if video.exists():
        contact_sheet(video, sheet)
        res["contact_sheet"] = sheet.name
        if a.ref_video:
            rs = P.dir / "reference_sheet.png"
            contact_sheet(a.ref_video, rs)
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(rs), "-i", str(sheet), "-filter_complex",
                            "[0:v][1:v]hstack=inputs=2", str(P.dir / "compare_sheets.png")], check=True)
            res["compare_sheets"] = "compare_sheets.png (left reference, right plugin)"
    (P.analysis / "sync_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
