"""film-tools: the quick jobs on an arbitrary video - apply_look.py, encode.py (small / mail / own target with a real
two-pass encode), media.py check and sheet - on a synthetic 1920x1080 clip with sound."""
import re

from common import FPS, Test, expect, ffmpeg, frame_colours, need, script, video_frames, check_video, has_audio

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

    ctx.uv(ENCODE, src)                                    # small + mail (1920 px > the side limits -> re-encoded, not copied)
    for suffix in ("_small", "_mail"):
        f = ctx.dir / f"in{suffix}.mp4"
        expect(f.exists() and not check_video(f), f"encode.py: in{suffix}.mp4 missing or broken")
        expect(f.stat().st_size <= src.stat().st_size * 1.03,       # user test: _mail of a 1.7 MB clip came out 5.7 MB
               f"encode.py: in{suffix}.mp4 ({f.stat().st_size} B) is bigger than the input ({src.stat().st_size} B)")
    r = ctx.uv(ENCODE, src, "--mb", "0.25", "--suffix", "_tiny", "--side", "640")   # forces the two-pass encode
    tiny = ctx.dir / "in_tiny.mp4"
    expect(tiny.exists() and not check_video(tiny) and video_frames(tiny) == n, "encode.py --mb: broken output")
    expect(tiny.stat().st_size <= 0.25 * 1.024e6 or "OVER the" in r.stdout,
           f"encode.py --mb 0.25: {tiny.stat().st_size} bytes without an OVER note")
    # a phone clip: landscape pixels + a 90 degree rotation flag -> outputs must be upright portrait, not squeezed
    phone = ctx.dir / "phone.mp4"
    ctx.ff("-display_rotation", "90", "-i", src, "-c", "copy", phone)
    ctx.uv(ENCODE, phone, "--mb", "5", "--suffix", "_web", "--side", "640")
    ctx.uv(LOOK, phone, "-o", ctx.dir / "phone_look.mp4")
    for name, want in (("phone_web.mp4", (360, 640)), ("phone_look.mp4", (1080, 1920))):
        info = ctx.run([ffmpeg(), "-hide_banner", "-i", ctx.dir / name], check=False).stdout
        m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})(?: \[SAR (\d+):(\d+))?", info)
        got = (int(m.group(1)), int(m.group(2))) if m else None
        sar_ok = not m or not m.group(3) or m.group(3) == m.group(4)
        expect(got == want and sar_ok, f"rotated clip: {name} is {m.group(0) if m else '?'} instead of upright "
                                       f"{want[0]}x{want[1]} with square pixels")
    out = ctx.run(["python", MEDIA, "frame", src, "3.0", ctx.dir / "last.png"])   # 3.0 s = the container end
    expect((ctx.dir / "last.png").exists() and "1920x1080" in out.stdout,
           f"media.py frame at the very end gave no picture:\n{out.stdout}")
    out = ctx.run(["python", MEDIA, "compare", src, look])
    expect("sound: bit-identical" in out.stdout and re.search(r"PSNR \d+\.\d dB, SSIM 0\.\d{3}", out.stdout),
           f"media.py compare (look vs input):\n{out.stdout}")
    out = ctx.run(["python", MEDIA, "check", src, tiny])
    expect(out.returncode == 0 and out.stdout.count("0 decode errors") == 2, f"media.py check:\n{out.stdout}")
    bad = ctx.dir / "bad.mp4"
    bad.write_bytes(src.read_bytes()[: src.stat().st_size // 3])
    out = ctx.run(["python", MEDIA, "check", bad], check=False)
    expect(out.returncode == 1, "media.py check: a truncated file was not reported (exit code 0)")
    ctx.run(["python", MEDIA, "sheet", look, ctx.dir / "sheet.png"])
    expect((ctx.dir / "sheet.png").exists(), "media.py sheet wrote no PNG")
    out = ctx.run(["python", MEDIA, "sheet", src, ctx.dir / "strip.png", "--from", "1", "--to", "1.5", "--cols", "6",
                   "--rows", "2", "--width", "160"])
    want = ", ".join(f"{f} ({f / FPS:.2f} s)" for f in range(FPS, FPS + FPS // 2))
    expect((ctx.dir / "strip.png").exists() and want in out.stdout,
           f"media.py sheet --from 1 --to 1.5: expected frames {want}\n{out.stdout}")
    ctx.note(f"look ({n} frames, sound kept), small/mail, rotated phone clip upright, --mb 0.25 two-pass {tiny.stat().st_size / 1e6:.2f} MB, "
             "check (good + truncated), compare, sheet")


TESTS = [Test("film-tools", run_film_tools, about="apply_look, encode.py small/mail/--mb, media.py check + sheet on any video")]
