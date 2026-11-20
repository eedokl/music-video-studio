# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""A title sting: black -> ONE shot -> black -> a title card ("X WILL RETURN"), cut to a piece of music.

  uv run sting.py analyse track.mp3                 where the music builds, hits, drops and ends (+ suggested times)
  uv run sting.py align new.mp3 old.mp3             how much later the same music starts in another file of it
  uv run sting.py build shot.mp4 --title "MONEYPENNY WILL RETURN" --audio track.mp3
                  --shot-at 7.5 --black-at 16.0 --title-at 17.3 --end 24.3 [-o sting.mp4]

build, the times (film seconds = seconds of the music):
  --shot-at    the shot appears (before it: black)
  --black-at   hard cut to black - put it on the drop of the music
  --title-at   the title card fades in;  --end = the film ends (card and music fade out)
  --clip-start seconds of the clip to skip at its start (AI clips start sluggishly: 0.3; a larger value moves the
               action earlier - this is how a take whose move comes late is put on the hit)
  --audio-offset  seconds of the music file to skip (from `align`, after the file was replaced by a better copy)
Without --audio the film is silent (a silent sound track is written) and the times default to 1.5 s black, the
whole clip, 1.3 s black, 6.5 s title.

Picture: --reveal sweep (default) lets the light travel from the left edge to the right over --reveal-seconds, so
the foreground hand appears before the face; `fade` is a plain fade-in, `none` a cut. --scope 2.39 draws cinema
bars; --fit 0.86 shows the shot a little smaller inside them so that heads are not cropped - only for shots on a
black background (use --fit 1 otherwise). Grain and a vignette are added unless --plain. --note puts one small grey
line under the title (the label for AI-made pictures belongs there).
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
import media  # noqa: E402
from encoding import h264  # noqa: E402

THIN = ["C:/Windows/Fonts/GOTHIC.TTF", "/System/Library/Fonts/Supplemental/Futura.ttc", "/System/Library/Fonts/Avenir.ttc",
        "C:/Windows/Fonts/segoeuil.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


# ---------------------------------------------------------------- sound
def level_curve(path, step=0.05, sr=8000):
    """-> (times, dB) of the RMS level in windows of `step` seconds."""
    import numpy as np
    x = media.decode(path, sr)
    n = int(step * sr)
    k = len(x) // n
    if k < 4:
        sys.exit(f"{path}: no sound to analyse")
    rms = np.sqrt((x[:k * n].reshape(k, n).astype("float64") ** 2).mean(axis=1))
    return np.arange(k) * step, 20 * np.log10(rms + 1e-6)


def analyse(path):
    """The four times a sting is cut to: hit (largest rise), drop (largest fall after it), re-entry of a quiet
    tail, end of the sound. All in seconds of the file."""
    import numpy as np
    t, db = level_curve(path)
    step = t[1] - t[0]
    w = max(1, round(0.5 / step))                       # compare the half second after a point with the one before
    c = np.concatenate([[0.0], np.cumsum(db)])
    mean = lambda a, b: (c[b] - c[a]) / max(1, b - a)   # noqa: E731
    jump = np.array([mean(i, min(len(db), i + w)) - mean(max(0, i - w), i) if w <= i <= len(db) - w else 0.0
                     for i in range(len(db))])
    floor = db.max() - 45                               # below this the file counts as silent
    sounding = np.where(db > floor)[0]
    end = float(t[sounding[-1]] + step) if len(sounding) else 0.0
    last = min(len(db) - w, int(sounding[-1]) - 2 * w) if len(sounding) else 0
    before = np.array([mean(max(0, i - w), i) for i in range(len(db))])
    after = np.array([mean(i, min(len(db), i + w)) for i in range(len(db))])
    top = after.max()
    # the hit: the largest rise INTO the loud part (within 6 dB of the loudest half second) that does not come out
    # of silence - the first note of the file and a quiet tail coming back are entries, not hits
    ok = (after >= top - 6) & (before > floor + 12)
    ok[:w] = False
    ok[max(w, last):] = False
    hit = int(np.where(ok, jump, -1e9).argmax()) if ok.any() else int(jump.argmax())
    # the drop: the largest fall out of the loud part after the hit, before the sound ends
    fall = (before >= top - 10)
    fall[:hit + w] = False
    fall[max(hit + w, last):] = False
    drop = int(np.where(fall, jump, 1e9).argmin()) if fall.any() and np.where(fall, jump, 1e9).min() < -3 else None
    tail = None
    if drop is not None:
        rest = np.where(jump[drop + w:max(drop + w, last)] > 3)[0]
        tail = drop + w + int(rest[0]) if len(rest) else None
    r = lambda i: None if i is None else round(float(t[i]), 2)   # noqa: E731
    return dict(seconds=round(float(t[-1] + step), 2), hit=r(hit), hit_db=round(float(jump[hit]), 1), drop=r(drop),
                drop_db=None if drop is None else round(float(jump[drop]), 1), tail=r(tail), end=round(end, 2),
                curve=[(round(float(t[i]), 1), round(float(db[i:i + 10].mean()))) for i in range(0, len(db), 10)])


def cmd_analyse(a):
    r = analyse(a.audio)
    print(f"{Path(a.audio).name}: {r['seconds']} s, sound until {r['end']} s")
    print("level per 0.5 s (dB): " + "  ".join(f"{t}:{d}" for t, d in r["curve"]))
    print(f"hit   {r['hit']} s  (+{r['hit_db']} dB within a second) - have the shot fully visible or its move land here")
    if r["drop"] is None:
        print("drop  none found - choose --black-at by ear / from the curve")
    else:
        print(f"drop  {r['drop']} s  ({r['drop_db']} dB) - cut to black here")
    if r["tail"] is not None:
        print(f"tail  {r['tail']} s  the sound comes back - fade the title in just before it")
    if r["drop"] is not None:
        shot = max(0.0, round(r["hit"] - 4.0, 1))
        title = r["tail"] - 0.1 if r["tail"] is not None else r["drop"] + 1.3
        print(f"suggested: --shot-at {shot} --black-at {r['drop']} --title-at {title:.1f} --end {r['end'] + 0.1:.1f}")
    print("These are levels, not hearing: a rise can be a swell half a second long. Nobody listened.")


def lag(new, old, seconds=60.0, sr=8000):
    """Seconds by which the same music starts later in `new` than in `old` (negative: earlier), and how sure."""
    import numpy as np
    a, b = (media.decode(p, sr)[: int(seconds * sr)].astype("float64") for p in (old, new))
    n = min(len(a), len(b))
    if n < sr:
        sys.exit("align needs at least a second of sound in both files")
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    size = 1 << (2 * n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(b, size) * np.conj(np.fft.rfft(a, size)), size)
    c = np.concatenate([c[-(n - 1):], c[:n]])           # lags -(n-1) .. n-1
    i = int(c.argmax())
    return (i - (n - 1)) / sr, float(c[i] / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-12))


def cmd_align(a):
    s, sure = lag(a.new, a.old)
    print(f"{Path(a.new).name} starts {s:+.3f} s against {Path(a.old).name} (match {sure:.2f})")
    if sure < 0.3:
        print("Low match: these may not be the same recording - do not rely on this offset.")
    elif s >= 0:
        print(f"Keep the times measured on the old file and add:  --audio-offset {s:.3f}")
    else:
        print(f"The new file starts earlier: add {-s:.3f} s to every time measured on the old file.")


# ---------------------------------------------------------------- picture
def title_card(text, note, out, w, h):
    """White spaced capitals on black, thin sans; shrinks to 70 % of the width."""
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in THIN if Path(f).exists()), None)
    im = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(im)
    size = round(58 * h / 720)

    def measure(sz):
        f = ImageFont.truetype(fp, sz) if fp else ImageFont.load_default()
        gap = sz * 0.06
        return f, gap, sum(d.textlength(ch, font=f) + gap for ch in text) - gap

    f, gap, tw = measure(size)
    if fp and tw > 0.7 * w:
        f, gap, tw = measure(max(12, int(size * 0.7 * w / tw)))
    x = (w - tw) / 2
    for ch in text:
        d.text((x, h / 2), ch, font=f, fill=(236, 236, 236), anchor="lm")
        x += d.textlength(ch, font=f) + gap
    if note:
        f2 = ImageFont.truetype(fp, max(10, round(15 * h / 720))) if fp else ImageFont.load_default()
        d.text((w / 2, h * 0.89), note, font=f2, fill=(90, 90, 90), anchor="mm")
    im.save(out)


def build(clip, out, title, note="", audio=None, audio_offset=0.0, shot_at=None, black_at=None, title_at=None, end=None,
          clip_start=0.3, reveal="sweep", reveal_seconds=None, scope=2.39, fit=0.86, plain=False, size=(1280, 720), fps=24):
    clip, out = Path(clip), Path(out)
    w, h = size
    length = media.duration(clip)
    if shot_at is None:
        shot_at = 1.5
    if black_at is None:
        black_at = shot_at + length - clip_start
    if title_at is None:
        title_at = black_at + 1.3
    if end is None:
        end = title_at + 6.5
    if not 0 <= shot_at < black_at <= title_at < end:
        sys.exit(f"times must run shot-at < black-at <= title-at < end (got {shot_at}, {black_at}, {title_at}, {end})")
    shot, gap, card = black_at - shot_at, title_at - black_at, end - title_at
    if clip_start + shot > length + 1.0:
        print(f"note: the clip ({length:.2f} s) is shorter than the shot ({shot:.2f} s from {clip_start} s) - "
              "its last frame is held")
    if reveal_seconds is None:
        reveal_seconds = min(3.0, shot * 0.4)
    bar = int(round((h - w / scope) / 4) * 2) if scope and w / scope < h else 0
    inner = max(2, int(round(w * fit / 2) * 2))
    chain = [f"[0:v]tpad=stop_mode=clone:stop_duration=2,trim=start={clip_start}:duration={shot},setpts=PTS-STARTPTS,"
             f"fps={fps},scale={inner}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos"]
    if not plain:
        chain.append("eq=contrast=1.06:saturation=0.92:gamma=0.94,vignette=PI/4")
    chain.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black")
    v = ",".join(chain)
    if reveal == "sweep":
        fc = (f"{v},format=gbrp[sh];"
              f"color=black:s={max(16, w // 8)}x{max(9, h // 8)}:r={fps}:d={shot},format=gray,"
              f"geq=lum='255*pow(clip((T/{reveal_seconds:.3f}*1.7-X/W)/0.45,0,1),1.6)',"
              f"scale={w}:{h}:flags=bicubic,format=gbrp[mk];[sh][mk]blend=all_mode=multiply")
    elif reveal == "fade":
        fc = f"{v},fade=t=in:st=0:d={reveal_seconds:.3f}"
    else:
        fc = v
    if not plain:
        fc += ",noise=alls=7:allf=t"
    if bar:
        fc += f",drawbox=0:0:{w}:{bar}:black:fill,drawbox=0:{h - bar}:{w}:{bar}:black:fill"
    fc += ",format=yuv420p,setsar=1[s];"
    fin, fout = min(1.2, card / 3), min(1.4, card / 3)
    fc += (f"[1:v]fps={fps},fade=t=in:st=0:d={fin:.3f},fade=t=out:st={card - fout:.3f}:d={fout:.3f},format=yuv420p,"
           f"setsar=1[t];")
    parts = []
    if shot_at > 0:
        fc += f"color=black:s={w}x{h}:r={fps}:d={shot_at},format=yuv420p,setsar=1[b0];"
        parts.append("[b0]")
    parts.append("[s]")
    if gap > 0:
        fc += f"color=black:s={w}x{h}:r={fps}:d={gap},format=yuv420p,setsar=1[b1];"
        parts.append("[b1]")
    parts.append("[t]")
    fc += f"{''.join(parts)}concat=n={len(parts)}:v=1:a=0[v]"

    ff = config.need("ffmpeg")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "title.png"
        title_card(title, note, png, w, h)
        cmd = [ff, "-y", "-v", "error", "-i", str(clip), "-loop", "1", "-t", f"{card:.3f}", "-i", str(png)]
        if audio:
            cmd += ["-ss", f"{audio_offset:.3f}", "-t", f"{end:.3f}", "-i", str(audio)]
            fc += f";[2:a]afade=t=out:st={max(0.0, end - 0.6):.3f}:d=0.6,aresample=48000,apad[a]"
        else:
            cmd += ["-f", "lavfi", "-t", f"{end:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            fc += ";[2:a]anull[a]"
        tmp = out.with_name(out.stem + ".part" + out.suffix)     # a player holding the old file must not break the build
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", *h264(17), "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-b:a", "192k", "-t", f"{end:.3f}", str(tmp)]
        subprocess.run(cmd, check=True)
    try:
        tmp.replace(out)
    except PermissionError:
        import time
        out = out.with_name(f"{out.stem}_{time.strftime('%H%M%S')}{out.suffix}")
        tmp.replace(out)
    bad = media.check_video(out)
    if bad:
        sys.exit(f"{out}: decode errors\n{bad}")
    print(f"OK {out}  {end:.2f} s: black to {shot_at:.2f} s, shot to {black_at:.2f} s (clip from {clip_start} s, reveal {reveal} "
          f"{reveal_seconds:.1f} s), title {title_at:.2f}-{end:.2f} s, {'music ' + Path(audio).name if audio else 'SILENT'}; "
          "0 decode errors")
    return out


def cmd_build(a):
    try:
        w, h = (int(x) for x in a.size.lower().split("x"))
    except ValueError:
        sys.exit("--size wants WIDTHxHEIGHT, e.g. 1280x720")
    clip = Path(a.clip).resolve()
    out = Path(a.out).resolve() if a.out else clip.with_name(clip.stem + "_sting.mp4")
    if out == clip:
        sys.exit("the output would overwrite the clip - choose another -o")
    build(clip, out, a.title, a.note, a.audio, a.audio_offset, a.shot_at, a.black_at, a.title_at, a.end, a.clip_start,
          a.reveal, a.reveal_seconds, a.scope, a.fit, a.plain, (w, h), a.fps)


def main():
    ap = argparse.ArgumentParser(description="A title sting: black, one shot, black, a title card - cut to a piece of music.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyse", help="hit, drop, tail and end of a piece of music")
    p.add_argument("audio")
    p.set_defaults(fn=cmd_analyse)
    p = sub.add_parser("align", help="offset of the same music in another file")
    p.add_argument("new")
    p.add_argument("old")
    p.set_defaults(fn=cmd_align)
    p = sub.add_parser("build", help="cut the sting")
    p.add_argument("clip")
    p.add_argument("--title", required=True)
    p.add_argument("--note", default="", help="small grey line under the title (AI label)")
    p.add_argument("--audio")
    p.add_argument("--audio-offset", type=float, default=0.0)
    p.add_argument("--shot-at", type=float)
    p.add_argument("--black-at", type=float)
    p.add_argument("--title-at", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--clip-start", type=float, default=0.3)
    p.add_argument("--reveal", choices=["sweep", "fade", "none"], default="sweep")
    p.add_argument("--reveal-seconds", type=float)
    p.add_argument("--scope", type=float, default=2.39, help="cinema bars for this aspect ratio; 0 = none")
    p.add_argument("--fit", type=float, default=0.86, help="width of the shot inside the frame (black background only)")
    p.add_argument("--plain", action="store_true", help="no grain, no vignette, no grading")
    p.add_argument("--size", default="1280x720")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("-o", "--out")
    p.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
