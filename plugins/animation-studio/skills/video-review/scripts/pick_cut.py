# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Frame-picking cut: build a new version of a film from N finished versions with the same timeline - no re-render.

Every output frame is copied from the version chosen for its shot; the audio is copied (not re-encoded) from one
version. All versions are decoded in lock-step as raw YUV (no colour conversion), only the chosen frame is written.
Works for any film as long as the versions share the timeline (same fps, same shot boundaries); different sizes
are scaled to the size of the audio version.

Library use (stdlib only, ffmpeg from config):
    import _studio; _studio.use("video-review")
    from pick_cut import pick_cut
    pick_cut({"v1": "a.mp4", "v2": "b.mp4"}, [(0, "v1"), (68, "v2"), ...], audio="v2", out="c.mp4")
segments: (first frame, version id) sorted by frame; a segment lasts until the next one starts.

CLI (a review.json from review.py):
    python pick_cut.py review.json [--choice choice.json] [--out file.mp4] [--small]
"""
import argparse
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import _studio
_studio.use()
from encoding import h264, hint  # noqa: E402
from media import ffmpeg  # noqa: E402


def probe(path):
    """(width, height, fps, duration) of a video from ffmpeg's banner."""
    err = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                         errors="replace").stderr
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
    if not m:
        raise SystemExit(f"{path}: no video stream")
    fps = re.search(r"([\d.]+) fps", err)
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    return int(m.group(1)), int(m.group(2)), float(fps.group(1)) if fps else 24.0, dur


def _decoder(path, w, h, size):
    vf = ["-vf", f"scale={w}:{h}:flags=lanczos"] if size != (w, h) else []
    return subprocess.Popen([ffmpeg(), "-v", "error", "-i", str(path), *vf, "-f", "rawvideo", "-pix_fmt", "yuv420p",
                             "-"], stdout=subprocess.PIPE, bufsize=0)


def _read(pipe, n):
    buf = bytearray(n)
    view, got = memoryview(buf), 0
    while got < n:
        k = pipe.readinto(view[got:])
        if not k:
            return None
        got += k
    return buf


def pick_cut(versions, segments, audio, out, fps=None, crf=18, log=print):
    """versions {id: path}; segments [(first_frame, id)]; audio = version id (its audio is copied) or None.
    Returns {"frames": n, "per_version": {id: frames}, "seconds": t}."""
    t0 = time.time()
    ids = list(versions)
    segs = sorted((int(f), v) for f, v in segments)
    if not segs or segs[0][0] != 0:
        raise ValueError("segments must start at frame 0")
    for _, v in segs:
        if v not in versions:
            raise ValueError(f"unknown version '{v}' (have {ids})")
    ref = audio if audio in versions else ids[0]
    w, h, f0, _ = probe(versions[ref])
    fps = fps or f0
    for v in ids:
        vw, vh, vf, _ = probe(versions[v])
        if abs(vf - fps) > 0.01:
            raise SystemExit(f"{versions[v]}: {vf} fps, expected {fps} - versions must share the timeline")
        if (vw, vh) != (w, h):
            log(f"  note: {Path(versions[v]).name} is {vw}x{vh}, scaled to {w}x{h}")
    frame_bytes = w * h * 3 // 2
    dec = {v: _decoder(versions[v], w, h, probe(versions[v])[:2]) for v in ids}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + "_tmp" + out.suffix)
    a_in = ["-i", str(versions[audio]), "-map", "0:v", "-map", "1:a?", "-c:a", "copy", "-shortest"] if audio else \
        ["-map", "0:v"]
    enc = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{w}x{h}",
                            "-r", f"{fps:g}", "-i", "-", *a_in, *h264(crf), "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    count = {v: 0 for v in ids}
    k, n = 0, 0
    log(f"  cutting {len(segs)} segments from {len(ids)} versions, {hint()}")
    while True:
        frames = {v: _read(p.stdout, frame_bytes) for v, p in dec.items()}   # read all: keeps them in sync
        if any(fr is None for fr in frames.values()):
            break
        while k + 1 < len(segs) and segs[k + 1][0] <= n:
            k += 1
        v = segs[k][1]
        enc.stdin.write(frames[v])
        count[v] += 1
        n += 1
        if n % int(fps * 30) == 0:
            log(f"  {n / fps:6.1f} s")
    enc.stdin.close()
    enc.wait()
    for p in dec.values():
        p.kill()
    if enc.returncode:
        raise SystemExit("ffmpeg encoder failed")
    tmp.replace(out)
    return {"frames": n, "per_version": count, "seconds": round(time.time() - t0, 1)}


def first_frame(t, fps):
    """First frame that belongs to a shot starting at t seconds: smallest f with f / fps >= t - 1e-6."""
    f = max(0, math.ceil((t - 1e-6) * fps) - 1)
    while f / fps < t - 1e-6:
        f += 1
    return f


def segments_from_review(R, choice):
    """review.json shots + choice {shot nr: version id or 1-based index} -> [(first_frame, id)]."""
    ids = [v["id"] for v in R["versions"]]
    fps = R.get("fps", 24)
    default = R.get("default") or ids[-1]
    segs = []
    for s in R["shots"]:
        c = choice.get(str(s["nr"]), choice.get(s["nr"]))
        if c not in ids and (isinstance(c, int) or (isinstance(c, str) and c.isdigit())):   # legacy 1-based index
            c = ids[int(c) - 1] if 1 <= int(c) <= len(ids) else None
        elif c is not None and c not in ids:
            print(f"  warning: shot {s['nr']}: unknown version '{c}' - default {default} used", file=sys.stderr)
            c = None
        segs.append((first_frame(s["start"], fps) if segs else 0, c or default))
    return segs


def load_choice(path):
    """choice file: {"choice": {nr: id}} or the legacy {"wahl": {nr: 1|2}} of older comparison pages."""
    d = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
    return d.get("choice", d.get("wahl", {}))


def small_version(src, out, dur, mb=29.0):
    """< mb MB copy (1280 wide max) via film-finish's two-pass target encoder."""
    _studio.use("film-finish")
    from encode import encode_target
    w, h, _, _ = probe(src)
    if Path(src).stat().st_size < mb * 1e6:
        import shutil
        shutil.copy(src, out)
        return out
    sw = min(w, 1280)
    sh = int(round(h * sw / w / 2) * 2)
    r = encode_target(Path(src), Path(out), mb, sw, sh, 128, dur)
    if not r.met:
        print(f"   {Path(out).name}: {r.size_mb:.1f} MB - OVER the {mb:g} MB target ({r.note})")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("review", help="review.json (review.py init)")
    ap.add_argument("--choice", help="choice file (default: the one named in review.json)")
    ap.add_argument("--out", help="output file (default: review.json 'out')")
    ap.add_argument("--small", action="store_true", help="also write <out>_small.mp4 (< 29 MB)")
    a = ap.parse_args()
    rp = Path(a.review).resolve()
    R = json.loads(rp.read_text(encoding="utf-8"))
    base = rp.parent
    choice = load_choice(Path(a.choice) if a.choice else base / R.get("choice_file", "choice.json"))
    versions = {v["id"]: base / v["file"] for v in R["versions"]}
    out = Path(a.out) if a.out else base / R.get("out", "cut.mp4")
    segs = segments_from_review(R, choice)
    res = pick_cut(versions, segs, R.get("audio"), out, fps=R.get("fps"))
    per_shot = {}
    for s, (_, v) in zip(R["shots"], segs):
        per_shot[v] = per_shot.get(v, 0) + 1
    lines = [f"{s['nr']:>3}  {v}" for s, (_, v) in zip(R["shots"], segs)]
    lines.append("")
    lines.append("shots per version: " + ", ".join(f"{v} {n}" for v, n in per_shot.items()))
    lines.append(f"frames per version: " + ", ".join(f"{v} {n}" for v, n in res["per_version"].items()))
    lines.append(f"{res['frames']} frames in {res['seconds']} s -> {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
    if a.small or R.get("small"):
        sm = out.with_name(out.stem + "_small.mp4")
        small_version(out, sm, res["frames"] / R.get("fps", 24))
        lines.append(f"small version -> {sm.name} ({sm.stat().st_size / 1e6:.1f} MB)")
    text = "\n".join(lines) + "\n"
    out.with_suffix(".log").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    sys.exit(main())
