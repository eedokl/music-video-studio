"""film-finish sting.py: a title sting (black -> one shot -> black -> title card) cut to a synthetic piece of music with
a known build, hit, drop and quiet tail; plus `align` on a copy of the music that starts a quarter second later."""
import re

from common import FPS, Test, audio_samples, check_video, expect, frame_colours, has_audio, need, script, video_frames

STING = script("film-finish", "sting.py")
HIT, DROP, TAIL, END = 3.0, 6.0, 6.8, 9.0


def run_sting(ctx):
    need("ffmpeg")
    clip = ctx.dir / "shot.mp4"
    ctx.ff("-f", "lavfi", "-i", f"testsrc2=size=1024x576:rate={FPS}:duration=4", "-c:v", "libx264", "-crf", "14",
           "-pix_fmt", "yuv420p", clip)
    # music: a quiet build, 12 dB louder from the hit, silence after the drop, a quiet tail, then nothing
    vol = (f"if(lt(t\\,{HIT})\\,0.05\\,if(lt(t\\,{DROP})\\,0.4\\,if(lt(t\\,{TAIL})\\,0\\,if(lt(t\\,{END})\\,0.05\\,0))))")
    music = ctx.dir / "music.wav"
    ctx.ff("-f", "lavfi", "-i", f"aevalsrc={vol}*(sin(2*PI*220*t)+0.6*sin(2*PI*331*t))/1.6:s=48000:d={END + 1.5}",
           "-ac", "2", music)
    late = ctx.dir / "music_late.wav"
    ctx.ff("-i", music, "-af", "adelay=250:all=1", late)

    out = ctx.uv(STING, "analyse", music).stdout
    got = {k: float(v) for k, v in re.findall(r"^(hit|drop|tail)\s+([\d.]+) s", out, re.M)}
    expect(set(got) == {"hit", "drop", "tail"}, f"sting.py analyse found {sorted(got)} instead of hit, drop and tail:\n{out}")
    for name, want in (("hit", HIT), ("drop", DROP), ("tail", TAIL)):
        expect(abs(got[name] - want) <= 0.35, f"sting.py analyse: {name} at {got[name]} s, the music has it at {want} s\n{out}")
    expect("suggested: --shot-at" in out, "sting.py analyse printed no suggested times")

    out = ctx.uv(STING, "align", late, music).stdout
    m = re.search(r"--audio-offset ([\d.]+)", out)
    expect(m and abs(float(m.group(1)) - 0.25) <= 0.005, f"sting.py align: expected --audio-offset 0.250\n{out}")

    film = ctx.dir / "sting.mp4"
    shot_at, black_at, title_at, end = 1.0, DROP, TAIL, END
    ctx.uv(STING, "build", clip, "--title", "TESTCARD WILL RETURN", "--note", "synthetic", "--audio", late,
           "--audio-offset", "0.25", "--shot-at", shot_at, "--black-at", black_at, "--title-at", title_at, "--end", end,
           "--clip-start", "0", "--reveal-seconds", "1.5", "-o", film)
    n = video_frames(film)
    expect(film.exists() and not check_video(film) and has_audio(film), "sting.py build: missing, broken or silent film")
    expect(abs(n - round(end * FPS)) <= 2, f"sting.py build: {n} frames instead of about {round(end * FPS)}")
    lum = [sum(c) / 3 for c in frame_colours(film)]
    at = lambda s: lum[min(n - 1, int(s * FPS))]                      # noqa: E731
    expect(at(0.5) < 4, f"the film does not start black (brightness {at(0.5):.1f})")
    expect(at(shot_at + 0.2) < at(shot_at + 2.5) * 0.5, "the reveal does not start dark and brighten")
    expect(at(black_at - 0.5) > 25, f"the shot is not visible before the cut to black ({at(black_at - 0.5):.1f})")
    expect(at(black_at + 0.3) < 4, f"no black after the shot ({at(black_at + 0.3):.1f})")
    expect(1 < at(title_at + 1.6) < 25, f"no title card on black ({at(title_at + 1.6):.1f})")
    a = audio_samples(film)
    loud = lambda t0, t1: max(abs(x) for x in a[int(t0 * 48000):int(t1 * 48000)])   # noqa: E731
    expect(loud(HIT + 0.3, HIT + 1) > 3 * loud(HIT - 1, HIT - 0.3),
           "the music is not on film time: no jump in level at the hit (is --audio-offset applied?)")

    silent = ctx.dir / "silent.mp4"
    ctx.uv(STING, "build", clip, "--title", "NO MUSIC", "--reveal", "fade", "--fit", "1", "--scope", "0", "--plain",
           "--size", "640x360", "-o", silent)
    expect(silent.exists() and not check_video(silent) and has_audio(silent), "sting.py build without --audio: broken film")
    expect(abs(video_frames(silent) - round((1.5 + 3.7 + 1.3 + 6.5) * FPS)) <= 2, "silent sting: wrong default length")
    ctx.note(f"analyse hit {got['hit']} / drop {got['drop']} / tail {got['tail']} s (music: {HIT} / {DROP} / {TAIL}), "
             f"align 0.250 s, film {n} frames with music on time, silent 640x360 variant")


TESTS = [Test("film-finish-sting", run_sting, about="sting.py: analyse a track, align a second copy, cut shot + title card to it")]
