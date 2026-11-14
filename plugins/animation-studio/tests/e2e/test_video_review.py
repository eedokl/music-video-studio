"""video-review: two synthetic versions of a 3-shot film -> review.py init --detect -> choice.json -> review.py cut;
every output frame must come from the version picked for its shot, the sound is the sound version's, unchanged."""
from common import (FPS, Test, audio_samples, expect, frame_colours, need, read_json, script, video_frames,
                    check_video, write_json)

REVIEW = script("video-review", "review.py")

V1 = ["red", "green", "blue"]
V2 = ["yellow", "cyan", "magenta"]
RGB = {"red": (255, 0, 0), "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0), "cyan": (0, 255, 255),
       "magenta": (255, 0, 255)}


def version(ctx, out, colours, freq):
    inputs, graph = [], ""
    for i, c in enumerate(colours):
        inputs += ["-f", "lavfi", "-i", f"color=c={c}:s=640x360:r={FPS}:d=1"]
        graph += f"[{i}:v]"
    inputs += ["-f", "lavfi", "-i", f"sine=f={freq}:r=48000:d=3"]
    ctx.ff(*inputs, "-filter_complex", graph + f"concat=n={len(colours)}:v=1:a=0[v]", "-map", "[v]", "-map",
           f"{len(colours)}:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out)


def nearest(rgb):
    return min(RGB, key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb, RGB[k])))


def run_review(ctx):
    need("ffmpeg")
    d = ctx.dir
    version(ctx, d / "v1.mp4", V1, 330)
    version(ctx, d / "v2.mp4", V2, 660)
    rv = d / "review" / "review.json"
    ctx.uv(REVIEW, "init", d / "v1.mp4", d / "v2.mp4", "--labels", "V1", "V2", "--audio", "v2", "--default", "v2",
           "--name", "v3.mp4", "--out", rv, "--detect")
    R = read_json(rv)
    starts = [round(s["start"] * FPS) for s in R["shots"]]
    expect(starts == [0, 24, 48], f"--detect found shots starting at frames {starts}, expected [0, 24, 48]")
    nrs = [s["nr"] for s in R["shots"]]
    write_json(rv.parent / "choice.json", {"choice": {str(nrs[0]): "v1", str(nrs[2]): "v1"}})   # shot 2: default v2
    ctx.uv(REVIEW, "cut", rv, timeout=600)
    out = rv.parent / R.get("out", "v3.mp4")
    expect(out.exists(), f"{out.name} missing")
    expect(not check_video(out), f"{out.name}: decode errors")
    n = video_frames(out)
    expect(n == 3 * FPS, f"{out.name}: {n} frames, expected {3 * FPS}")
    got = [nearest(c) for c in frame_colours(out)]
    want = [V1[0]] * 24 + [V2[1]] * 24 + [V1[2]] * 24
    bad = [i for i, (g, w) in enumerate(zip(got, want)) if g != w]
    expect(not bad, f"frames from the wrong version: {bad[:10]} (got {[got[i] for i in bad[:5]]})")
    a_out, a_v2 = audio_samples(out), audio_samples(d / "v2.mp4")
    expect(len(a_out) > 0 and a_out[:len(a_out) - 4800] == a_v2[:len(a_out) - 4800],
           "the cut's sound is not the unchanged sound of the audio version v2")
    ctx.note(f"shots detected at frames {starts}; all {n} frames from the picked version (V1/V2/V1), sound = V2")


TESTS = [Test("video-review", run_review, about="review.py init --detect -> choice.json -> review.py cut, per-frame provenance")]
