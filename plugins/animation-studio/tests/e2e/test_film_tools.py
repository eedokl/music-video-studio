"""film-tools: the quick jobs on an arbitrary video - apply_look.py, encode.py (small / mail / own target with a real
two-pass encode), media.py check and sheet - on a synthetic 1920x1080 clip with sound."""
from common import FPS, Test, expect, frame_colours, need, script, video_frames, check_video, has_audio

LOOK = script("film-finish", "apply_look.py")
ENCODE = script("film-finish", "encode.py")
MEDIA = script("studio-core", "media.py")


def run_film_tools(ctx):
    need("ffmpeg")
    src = ctx.dir / "in.mp4"
    ctx.ff("-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate={FPS}:duration=3", "-f", "lavfi", "-i",
           "sine=f=330:r=48000:d=3", "-shortest", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac",
           src)
    n = video_frames(src)

    ctx.uv(LOOK, src, "-o", ctx.dir / "in_look.mp4")
    look = ctx.dir / "in_look.mp4"
    expect(look.exists() and video_frames(look) == n and not check_video(look) and has_audio(look),
           "apply_look.py: missing output, other frame count, decode errors or no sound")
    a, b = frame_colours(src)[10], frame_colours(look)[10]
    expect(a != b, "the look did not change the picture")

    ctx.uv(ENCODE, src)                                    # small + mail (input is small enough -> copies)
    for suffix in ("_small", "_mail"):
        f = ctx.dir / f"in{suffix}.mp4"
        expect(f.exists() and not check_video(f), f"encode.py: in{suffix}.mp4 missing or broken")
    r = ctx.uv(ENCODE, src, "--mb", "0.25", "--suffix", "_tiny", "--side", "640")   # forces the two-pass encode
    tiny = ctx.dir / "in_tiny.mp4"
    expect(tiny.exists() and not check_video(tiny) and video_frames(tiny) == n, "encode.py --mb: broken output")
    expect(tiny.stat().st_size <= 0.25 * 1.024e6 or "OVER the" in r.stdout,
           f"encode.py --mb 0.25: {tiny.stat().st_size} bytes without an OVER note")
    out = ctx.run(["python", MEDIA, "check", src, tiny])
    expect(out.returncode == 0 and out.stdout.count("0 decode errors") == 2, f"media.py check:\n{out.stdout}")
    bad = ctx.dir / "bad.mp4"
    bad.write_bytes(src.read_bytes()[: src.stat().st_size // 3])
    out = ctx.run(["python", MEDIA, "check", bad], check=False)
    expect(out.returncode == 1, "media.py check: a truncated file was not reported (exit code 0)")
    ctx.run(["python", MEDIA, "sheet", look, ctx.dir / "sheet.png"])
    expect((ctx.dir / "sheet.png").exists(), "media.py sheet wrote no PNG")
    ctx.note(f"look ({n} frames, sound kept), small/mail copies, --mb 0.25 two-pass {tiny.stat().st_size / 1e6:.2f} MB, "
             "check (good + truncated), sheet")


TESTS = [Test("film-tools", run_film_tools, about="apply_look, encode.py small/mail/--mb, media.py check + sheet on any video")]
