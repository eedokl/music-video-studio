"""Lip-sync measurement: how well does a singing clip's mouth follow the vocals? Used to pick seeds and offsets.

Mouth openness per frame (MediaPipe FaceLandmarker): inner-lip gap (landmarks 13/14) divided by mouth width (78/308).
Vocal curve per film frame (24 fps) from the song project:
  rhubarb  Rhubarb mouth shapes on the lead vocals (analysis/lead_mouth.json): X/A 0, B .3, C .6, D 1, E .7, F .35,
           G .25, H .5, smoothed [.25 .5 .25]  (same as the Europe 2031 reference analysis)
  level    loudness envelope of the lead vocals (analysis/vocals_lead.wav), 98th percentile = 1
  mix      mean of both correlations - better in loud choruses where separated vocals carry choir/bleed
  both     Rhubarb on lead AND backing vocals (per frame the wider mouth) - for calls/shouts that live on the backing
           stem ("Hey! Hey!"). CAUTION: on a short window (1.8 s) a placement fit on this curve overfitted
           (r 0.63 on it, -0.47 on the reference's curve); the lead-only fit held up (0.25 / 0.75). Use it for scoring
           whole takes, and fit placements on windows of >= 1.5 bars.
Lip score of a clip for a shot [t0, t1): the clip is laid on the song exactly like the cut does (clips.frame_index),
then Pearson r against the vocal curve for lags -6..+6 frames.
  lag > 0: the picture shows the vocals of `lag` frames earlier = the mouth is LATE -> show the clip with dt = +lag/24 s.
  range = 95th - 5th percentile of the openness: < 0.1 means the mouth stays (almost) closed -> reject the clip.
Rating (seed selection, as Europe 2031 V2): best lag within +-3 frames, minus 0.02 per frame of offset; the lag is only
used when it improves r by >= 0.08 over lag 0; -0.2 when the mouth stays closed; +0.05 for S2V (more expressive).

Needs Python 3.12 with mediapipe:  uv run --no-project --python 3.12 --with mediapipe --with opencv-python-headless
  python mouth.py score <clip.mp4> [...] --project <song project> --from 9.73 --to 12.89 [--curve rhubarb|level|mix]
  python mouth.py curve <clip.mp4>        (mouth openness per frame, cached in <clip>.mouth.json)
  python mouth.py fit <clip.mp4> --project P --from t0 --to t1 [--write]
         a clip WITHOUT its own vocals (old Wan clip, any singing take): search entry frame and tempo 0.9-1.1 so
         that its mouth follows the vocals of [t0, t1); --write stores song_start/clip_start/tempo in <clip>.json
Config: face_landmarker = path of MediaPipe's face_landmarker.task (download it once from the MediaPipe model page).
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
import config  # noqa: E402

FPS = 24
OPEN = dict(X=0.0, A=0.0, B=0.3, C=0.6, D=1.0, E=0.7, F=0.35, G=0.25, H=0.5)
CLOSED_RANGE = 0.1


def landmarker_model():
    p = config.get("face_landmarker")
    if not p or not Path(p).exists():
        raise SystemExit("MediaPipe face_landmarker.task not configured: download it from the MediaPipe Face Landmarker "
                         "page and run `check_tools.py --set face_landmarker=<path>` (or set FACE_LANDMARKER).")
    return p


def mouth_curve(video, cache=True):
    """Mouth openness per frame of a video (NaN where no face is found). Cached next to the clip."""
    video = Path(video)
    cf = video.with_suffix(".mouth.json")
    if cache and cf.exists() and cf.stat().st_mtime >= video.stat().st_mtime:
        return np.array([np.nan if x is None else x for x in json.loads(cf.read_text())], float)
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=landmarker_model()),
                                        running_mode=vision.RunningMode.VIDEO, num_faces=1)
    vals = []
    with vision.FaceLandmarker.create_from_options(opts) as lm:
        cap = cv2.VideoCapture(str(video))
        fps = FPS     # timestamps as in the reference analysis (1000/24 per frame, also for 16/25 fps clips): with the
        i = 0         # clip's real fps MediaPipe tracks differently (S2V shot 14: r 0.514 instead of the logged 0.53)
        while True:
            ok, f = cap.read()
            if not ok:
                break
            r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)),
                                    int(i * 1000 / fps))
            if r.face_landmarks:
                p = r.face_landmarks[0]
                h, w = f.shape[:2]
                d = lambda a, b: math.hypot((p[a].x - p[b].x) * w, (p[a].y - p[b].y) * h)
                vals.append(d(13, 14) / max(d(78, 308), 1e-6))
            else:
                vals.append(float("nan"))
            i += 1
    if cache:
        cf.write_text(json.dumps([None if np.isnan(x) else round(float(x), 5) for x in vals]))
    return np.array(vals, float)


def motion_check(video):
    """Picture checks of an AI clip (claudia-live v2_auswahl/v4_messung): per frame the mean absolute grey difference
    at 160x88. cuts = jumps > 6 levels AND > 4x the median (a hidden scene cut); frozen = a run of >= 12 frames below
    0.6 (the picture stops); motion = mean difference (moving B-roll below ~3 reads as a still)."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    prev, d = None, []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (160, 88)).astype(np.float32)
        if prev is not None:
            d.append(float(np.abs(g - prev).mean()))
        prev = g
    d = np.array(d)
    if not len(d):
        return dict(motion=0.0, cuts=0, frozen=0, frozen_run=0)
    med = float(np.median(d))
    cuts = int(np.sum((d > 6) & (d > 4 * max(med, 0.5))))
    run = longest = 0
    for x in d:
        run = run + 1 if x < 0.6 else 0
        longest = max(longest, run)
    return dict(motion=round(float(d.mean()), 2), cuts=cuts, frozen=int(longest >= 12), frozen_run=int(longest))


def rhubarb_curve(mouth_json, fps=FPS):
    d = json.loads(Path(mouth_json).read_text(encoding="utf-8"))
    n = int(d["metadata"]["duration"] * fps) + 1
    k = np.zeros(n)
    active = np.zeros(n)
    for c in d["mouthCues"]:
        a, b = int(round(c["start"] * fps)), int(round(c["end"] * fps))
        k[a:b] = OPEN.get(c["value"], 0.0)
        active[a:b] = c["value"] != "X"
    return np.convolve(k, [0.25, 0.5, 0.25], mode="same"), active


def level_curve(wav, fps=FPS):
    import media
    y = media.decode(wav, 16000)
    hop = 16000 // fps
    k = len(y) // hop
    r = np.sqrt((y[:k * hop].reshape(k, hop) ** 2).mean(1))
    r = np.convolve(r, np.ones(3) / 3, mode="same")
    return r / (np.percentile(r, 98) + 1e-9)


def vocal_curves(project_dir, kind="rhubarb"):
    """-> list of curves (one for rhubarb/level, two for mix) on the song timeline of a song-analysis project."""
    a = Path(project_dir) / "analysis"
    out = []
    if kind in ("rhubarb", "mix", "both"):
        f = a / "lead_mouth.json"
        if not f.exists():
            raise SystemExit(f"{f} missing - run song-analysis analyze.py (step 4: Rhubarb on the lead vocals)")
        c = rhubarb_curve(f)[0]
        fb = a / "backing_mouth.json"
        if kind == "both" and fb.exists():
            b = rhubarb_curve(fb)[0]
            n = max(len(c), len(b))
            c = np.maximum(np.pad(c, (0, n - len(c))), np.pad(b, (0, n - len(b))))
        out.append(c)
    if kind in ("level", "mix"):
        out.append(level_curve(a / "vocals_lead.wav"))
    return out


def lip_score(clip, t0, t1, curves, meta=None, max_lag=6, mouth=None):
    """Measure one clip on the shot [t0, t1) (song seconds). meta = clip json (song_start, fps, delay_frames)."""
    meta = meta or clips.read_meta(clip)
    v = mouth_curve(clip) if mouth is None else mouth
    if not len(v):
        return dict(face=0.0, r0=None, r_best=None, lag=None, range=None, all={})
    f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    film = np.array([v[clips.frame_index(fi / FPS, meta, 0, len(v))] for fi in range(f0, f1)])
    m = ~np.isnan(film)
    face = float(m.mean()) if len(film) else 0.0
    rng = float(np.nanpercentile(film, 95) - np.nanpercentile(film, 5)) if m.any() else 0.0
    res = {}
    for lag in range(-max_lag, max_lag + 1):
        if f0 - lag < 0:
            continue
        rs = []
        for g in curves:
            seg = g[f0 - lag:f1 - lag]
            if len(seg) != len(film) or m.sum() < 10 or np.std(film[m]) < 1e-4 or np.std(seg[m]) < 1e-4:
                continue
            rs.append(float(np.corrcoef(film[m], seg[m])[0, 1]))
        if rs:
            res[lag] = float(np.mean(rs))
    if not res:
        return dict(face=round(face, 2), r0=None, r_best=None, lag=None, range=round(rng, 3), all={})
    best = max(res, key=res.get)
    return dict(face=round(face, 2), r0=round(res.get(0, float("nan")), 3), r_best=round(res[best], 3), lag=best,
                range=round(rng, 3), all={k: round(x, 3) for k, x in res.items()})


def rating(r, kind="ltx", max_lag=3):
    """Seed-selection score -> (score, lag to apply, r at that lag, closed?)."""
    al = {int(k): x for k, x in (r.get("all") or {}).items() if abs(int(k)) <= max_lag}
    closed = (r.get("range") or 0) < CLOSED_RANGE
    if not al:
        return -9.0, 0, None, closed
    lag = max(al, key=lambda k: al[k] - 0.02 * abs(k))
    if al[lag] - al.get(0, -9) < 0.08 and 0 in al:
        lag = 0
    s = al[lag] - 0.02 * abs(lag) - (0.2 if closed else 0) + (0.05 if kind == "s2v" else 0)
    return round(s, 3), lag, round(al[lag], 3), closed


def fit_placement(clip, t0, t1, curves, tempos=(0.9, 0.95, 1.0, 1.05, 1.1), step=1, fps=None):
    """Best entry frame + tempo for a clip on [t0, t1) -> dict(song_start, clip_start, tempo, fps, r, range)."""
    v = mouth_curve(clip)
    if fps is None:
        import cv2
        fps = cv2.VideoCapture(str(clip)).get(cv2.CAP_PROP_FPS) or FPS
    v = np.where(np.isnan(v), np.nanmedian(v), v)
    f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    n = f1 - f0
    best = None
    for tempo in tempos:
        span = (n - 1) / FPS * fps * tempo
        for cs in range(0, max(1, int(len(v) - 1 - span)), step):
            idx = cs + np.floor(np.arange(n) / FPS * fps * tempo + 1e-6).astype(int)
            film = v[np.clip(idx, 0, len(v) - 1)]
            if np.std(film) < 1e-4:
                continue
            rs = [float(np.corrcoef(film, g[f0:f1])[0, 1]) for g in curves if np.std(g[f0:f1]) > 1e-4]
            if rs and (best is None or np.mean(rs) > best["r"]):
                best = dict(song_start=round(t0, 3), clip_start=cs, tempo=tempo, fps=fps, r=round(float(np.mean(rs)), 3),
                            range=round(float(np.percentile(film, 95) - np.percentile(film, 5)), 3))
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["score", "curve", "fit"])
    ap.add_argument("--write", action="store_true", help="fit: store the placement in <clip>.json")
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--project", default=".")
    ap.add_argument("--from", dest="t0", type=float)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--curve", default="rhubarb", choices=["rhubarb", "level", "mix", "both"])
    a = ap.parse_args()
    if a.what == "curve":
        for c in a.clips:
            v = mouth_curve(c)
            print(c, f"{len(v)} frames, face {np.mean(~np.isnan(v)):.2f}, range "
                     f"{np.nanpercentile(v, 95) - np.nanpercentile(v, 5):.3f}")
        return
    curves = vocal_curves(a.project, a.curve)
    if a.what == "fit":
        for c in a.clips:
            b = fit_placement(c, a.t0, a.t1, curves)
            print(json.dumps(dict(clip=str(c), **(b or {}))))
            if a.write and b:
                old = clips.read_meta(c) if clips.meta_path(c).exists() else {}
                clips.write_meta(c, **dict(old, kind=old.get("kind", "placed"), delay_frames=0,
                                           **{k: b[k] for k in ("song_start", "clip_start", "tempo", "fps")}))
        return
    for c in a.clips:
        meta = clips.read_meta(c)
        t0 = a.t0 if a.t0 is not None else meta["song_start"] + meta.get("lead_in", 0)
        t1 = a.t1 if a.t1 is not None else meta["song_start"] + meta["frames"] / meta["fps"]
        r = lip_score(c, t0, t1, curves, meta)
        s, lag, rl, closed = rating(r, "s2v" if meta.get("kind") == "s2v" else "ltx")
        print(json.dumps(dict(clip=str(c), **r, score=s, use_lag=lag, closed=closed)))


if __name__ == "__main__":
    main()
