# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Compare versions of a film shot by shot, pick per shot, cut a new version without re-rendering.

  init   <a.mp4> <b.mp4> [...] --out review/review.json  + one shot source:
           --shots shots.json      shot list: [{"start": s, "end"?: s, "nr"?: n, "label"?: text}, ...] or {"shots": [...]}
                                   (also reads the keys "zeile"/"line"/"text" as label, "verfahren"/"kind" as note)
           --project <song dir>    the sections of a song project (project.json); film time = song time - first "from"
           --detect                hard cuts detected in the pictures of all versions (merged, min shot length 0.5 s)
         options: --labels V1 V2 --audio <id> (audio of the cut, default last) --default <id> (shots without a choice)
                  --previews a_small.mp4 b_small.mp4 (lighter files for the browser) --name <output file name>
  scan   review.json           per shot: how different the versions are (mean abs difference of small grey frames);
                               marks identical shots ("same") for the "only differing shots" filter. init runs it.
  proxies review.json          writes light browser copies (960 px, keyframe every 0.5 s) for versions without preview
  serve  review.json [--port 0] the comparison page (port 0 = any free port; the URL is printed)
  cut    review.json [--small] the new version from the choice (pick_cut.py)

All paths inside review.json are relative to it. The choice is stored next to it in choice.json:
  {"choice": {"<shot nr>": "<version id>"}}   (the legacy {"wahl": {"3": 2}} with 1-based indices is read too)
Usage: uv run review.py init ...
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import _studio
_studio.use()
from media import ffmpeg  # noqa: E402
from pick_cut import probe  # noqa: E402

HERE = Path(__file__).resolve().parent
SW, SH = 96, 54                     # analysis size (grey)


def rel(p, base):
    return os.path.relpath(Path(p).resolve(), base).replace("\\", "/")


def small_frames(path, fps):
    """All frames of a video as a uint8 array (n, SH, SW), grey."""
    import numpy as np
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-vf", f"fps={fps:g},scale={SW}:{SH}:flags=area",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, SH, SW)


def detect_cuts(frames, fps):
    """Hard cuts: frame difference far above its neighbourhood -> [(first frame of the new shot, strength)]."""
    import numpy as np
    f = frames.astype(np.float32)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))                          # d[i]: frame i -> i+1
    hist = np.stack([np.histogram(x, 16, (0, 256))[0] for x in frames]).astype(np.float32) / (SW * SH)
    hd = np.abs(np.diff(hist, axis=0)).sum(axis=1) * 50                     # 0..100
    score = d + hd
    cuts = []
    w = int(fps)
    for i in range(len(score)):
        lo, hi = max(0, i - w), min(len(score), i + w + 1)
        local = np.median(np.r_[score[lo:i], score[i + 1:hi]]) if hi - lo > 1 else 0
        if score[i] > 12 and score[i] > 3.5 * local + 4 and score[i] == score[max(0, i - 2):i + 3].max():
            cuts.append((i + 1, float(score[i] / (local + 1))))
    return cuts


def merge_cuts(cuts, fps, min_len=0.5):
    """Cuts of all versions -> one list; of two cuts closer than min_len the stronger one wins (a flash inside a
    shot loses against the real cut next to it); no shot shorter than min_len at the start."""
    keep = []
    for f, _ in sorted(cuts, key=lambda c: -c[1]):
        if f >= min_len * fps and all(abs(f - k) >= min_len * fps for k in keep):
            keep.append(f)
    return [0] + sorted(keep)


def shots_from_list(path, offset=0.0):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    S = d.get("shots", d) if isinstance(d, dict) else d
    res = []
    for i, s in enumerate(sorted(S, key=lambda s: float(s["start"]))):
        res.append(dict(nr=s.get("nr", i + 1), start=round(float(s["start"]) - offset, 4),
                        end=float(s["end"]) - offset if s.get("end") is not None else (s.get("ende") or None),
                        label=s.get("label") or s.get("zeile") or s.get("line") or s.get("text") or "",
                        note=s.get("note") or s.get("verfahren") or s.get("kind") or "",
                        info=s.get("info", {})))
    return res


def shots_from_project(folder):
    _studio.use("song-analysis")
    from song_project import Project
    secs = sorted(Project(folder).sections(), key=lambda a: a["from"])
    if not secs:
        raise SystemExit("the project has no sections")
    t0 = secs[0]["from"]
    return [dict(nr=i + 1, start=round(a["from"] - t0, 4), end=round(a["to"] - t0, 4), label=a.get("name", ""),
                 note=a.get("kind", ""), info={}) for i, a in enumerate(secs)]


def close_shots(S, total):
    """A shot lasts until the next one starts (the timeline has no gaps); the last one ends with the film."""
    S = [s for s in S if s["start"] < total]
    for i, s in enumerate(S):
        s["end"] = round(S[i + 1]["start"] if i + 1 < len(S) else total, 4)
    return S


def scan(rp, R, frames=None, log=print):
    """Per shot difference between the versions (vs. the first), 0..255; 'same' when below the threshold."""
    import numpy as np
    base = rp.parent
    fps = R["fps"]
    if frames is None:
        frames = {v["id"]: small_frames(base / v["file"], fps) for v in R["versions"]}
    ids = list(frames)
    n = min(len(f) for f in frames.values())
    per_frame = {v: np.abs(frames[v][:n].astype(np.int16) - frames[ids[0]][:n]).mean(axis=(1, 2)) for v in ids[1:]}
    thr = R.get("same_threshold", 1.5)
    for s in R["shots"]:
        a, b = int(round(s["start"] * fps)), max(int(round(s["end"] * fps)), int(round(s["start"] * fps)) + 1)
        a, b = min(a, n - 1), min(b, n)
        diffs = {v: float(per_frame[v][a:b].mean()) for v in per_frame} if b > a else {v: 0.0 for v in per_frame}
        s["diff"] = round(max(diffs.values()) if diffs else 0.0, 2)
        s["same"] = s["diff"] < thr
    nd = sum(not s["same"] for s in R["shots"])
    log(f"  {len(R['shots'])} shots, {nd} differ between the versions (threshold {thr})")
    return frames


def save(rp, R):
    rp.write_text(json.dumps(R, indent=1, ensure_ascii=False), encoding="utf-8")


def cmd_init(a):
    rp = Path(a.out).resolve()
    rp.parent.mkdir(parents=True, exist_ok=True)
    base = rp.parent
    files = [Path(f).resolve() for f in a.videos]
    if len(files) < 2:
        raise SystemExit("need at least two versions")
    labels = a.labels or [f"V{i + 1}" for i in range(len(files))]
    ids = [l.lower().replace(" ", "_") for l in labels]
    w, h, fps, dur = probe(files[0])
    durs = [probe(f)[3] for f in files]
    if max(durs) - min(durs) > 1.0:
        print(f"  warning: lengths differ ({', '.join(f'{d:.2f}' for d in durs)} s) - same timeline?")
    total = min(durs)
    by_label = {l.lower(): i for l, i in zip(labels, ids)}
    for opt in ("audio", "default"):                 # accept id or label; fail now, not at the cut
        v = getattr(a, opt)
        if v and v not in ids:
            if v.lower() not in by_label:
                raise SystemExit(f"--{opt} {v}: not a version (ids: {', '.join(ids)})")
            setattr(a, opt, by_label[v.lower()])
    versions = []
    for i, f in enumerate(files):
        v = dict(id=ids[i], label=labels[i], file=rel(f, base))
        if a.previews and i < len(a.previews):
            v["preview"] = rel(a.previews[i], base)
        versions.append(v)
    R = dict(title=a.title or files[0].stem, fps=fps, size=[w, h], duration=round(total, 3), versions=versions,
             audio=a.audio or ids[-1], default=a.default or ids[-1], choice_file="choice.json",
             out=a.name or f"{files[0].stem}_cut.mp4", shots=[])
    frames = None
    if a.shots:
        S = shots_from_list(a.shots, a.offset)
        R["shot_source"] = "list " + Path(a.shots).name
    elif a.project:
        S = shots_from_project(a.project)
        R["shot_source"] = "song project sections"
    else:
        frames = {v["id"]: small_frames(base / v["file"], fps) for v in versions}
        merged = merge_cuts([c for fr in frames.values() for c in detect_cuts(fr, fps)], fps)
        S = [dict(nr=i + 1, start=round(f / fps, 4), end=None, label="", note="", info={})
             for i, f in enumerate(merged)]
        R["shot_source"] = "detected cuts"
    R["shots"] = close_shots(S, total)
    scan(rp, R, frames)
    save(rp, R)
    cp = base / "choice.json"
    if not cp.exists():
        cp.write_text('{"choice": {}}', encoding="utf-8")
    print(f"-> {rp} ({len(R['shots'])} shots from {R['shot_source']}, {len(versions)} versions)")


def cmd_proxies(a):
    from encoding import h264
    rp = Path(a.review).resolve()
    R = json.loads(rp.read_text(encoding="utf-8"))
    cache = rp.parent / "cache"
    cache.mkdir(exist_ok=True)
    for v in R["versions"]:
        if v.get("preview") and (rp.parent / v["preview"]).exists():
            continue
        out = cache / f"{v['id']}_preview.mp4"
        g = int(R["fps"] / 2)
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(rp.parent / v["file"]), "-vf",
                        "scale='min(960,iw)':-2:flags=lanczos", *h264(26, "fast"), "-g", str(g), "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)
        v["preview"] = rel(out, rp.parent)
        print(f"-> {out}")
    save(rp, R)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("videos", nargs="+")
    p.add_argument("--out", default="review/review.json")
    p.add_argument("--labels", nargs="+")
    p.add_argument("--previews", nargs="+")
    p.add_argument("--audio")
    p.add_argument("--default")
    p.add_argument("--title")
    p.add_argument("--name", help="file name of the cut (next to review.json)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--shots")
    g.add_argument("--project")
    g.add_argument("--detect", action="store_true")
    p.add_argument("--offset", type=float, default=0.0, help="subtract from shot-list times (song -> film time)")
    for name in ("scan", "proxies"):
        sub.add_parser(name).add_argument("review")
    p = sub.add_parser("serve")
    p.add_argument("review")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--host", default="127.0.0.1")
    p = sub.add_parser("cut")
    p.add_argument("review")
    p.add_argument("--small", action="store_true")
    p.add_argument("--choice")
    a = ap.parse_args()
    if a.cmd == "init":
        cmd_init(a)
    elif a.cmd == "scan":
        rp = Path(a.review).resolve()
        R = json.loads(rp.read_text(encoding="utf-8"))
        scan(rp, R)
        save(rp, R)
    elif a.cmd == "proxies":
        cmd_proxies(a)
    elif a.cmd == "serve":
        import server
        server.serve(Path(a.review).resolve(), a.port, a.host)
    elif a.cmd == "cut":
        args = [sys.executable, str(HERE / "pick_cut.py"), a.review] + (["--small"] if a.small else []) + \
            (["--choice", a.choice] if a.choice else [])
        sys.exit(subprocess.run(args).returncode)


if __name__ == "__main__":
    main()
