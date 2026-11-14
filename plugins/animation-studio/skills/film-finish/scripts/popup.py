# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# ///
"""Pop-up video version (like the 1980s "Pop-up Videos"): info cards about how the film was made pop up at free spots
of the finished film, each with a pop sound, held long enough to read.

  python popup.py [--project .] [--draft] [--to s]
--draft   writes a first set of cards into project.json "popups" from the project's own data (ideas that were built,
          the tools behind each section) – Claude then rewrites them as short, surprising facts and places them.
          Nothing is invented about tools that were not used.
Without --draft: builds film_popup.mp4 (+ POPUPS.md, the card list) from the finished cut (cache/film_raw.mp4 from
build.py film, before the look) – the look is applied once afterwards, the original audio tracks stay.
project.json:
  "popups": [{"at": 12.0, "tag": "Rhubarb Lip Sync", "text": "1556 mouth shapes, computed from lead and backing vocals",
              "place": "top_right"}]
  at = song seconds (or "word": "tokens" = when that word is sung); place = top_left | top_right | top |
  bottom_left | bottom_right | mid_right | auto (alternates top corners; bottom only where no lyrics run).
  Reading time per card: max(4.5 s, 2 s + 0.33 s per word). Two cards never share a place at the same time.
Version with credits: when "credits" is set and credits.mp4 exists, also film_popup_with_credits.mp4 = film_popup.mp4 +
credits, with optional cards over the credits part (pop sound included):
  "popup_credits": [{"tag": "ElevenLabs", "text": "The laugh comes from ...", "sound": "assets/sfx/laugh.wav",
                     "duration": 5.5, "place": "top_right"}]
  timing: "at" = credits seconds | "segment": "post" (+ "at" = seconds into the post-credits scene) | "sound" = the
  moment that sound plays in the credits (cross-correlation, + "lead" 0.2 s). --no-credits skips this version.
Card look: cream card, ink outline, red tool tag, slight tilt, soft shadow; pop-in with a small overshoot wobble.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402
from encoding import h264  # noqa: E402
from media import check_video, duration, ffmpeg  # noqa: E402
from song_project import Project, word_matches  # noqa: E402

W, H = 1280, 720
PLACES = {"top_right": (1040, 95, -3), "top_left": (250, 100, 3), "top": (640, 85, -2),
          "bottom_left": (290, 610, 2), "bottom_right": (1050, 615, -2), "mid_right": (1040, 330, 2)}
FONTS = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
FONTS_B = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
HERE = Path(__file__).resolve().parent


def font(c, size):
    for f in c:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


F_X, F_T = font(FONTS, 24), font(FONTS_B, 22)


def hold(text):
    return max(4.5, 2.0 + 0.33 * len(text.split()))


def card(tag, text, angle):
    rows, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if F_X.getlength(t) > 380:
            rows.append(cur)
            cur = w
        else:
            cur = t
    rows.append(cur)
    bw, bh = 420, 58 + 32 * len(rows)
    img = Image.new("RGBA", (bw + 12, bh + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, bw + 8, bh + 8), 14, fill=(0, 0, 0, 110))
    d.rounded_rectangle((0, 0, bw, bh), 14, fill="#fffdf4", outline="#2b1d14", width=4)
    tw = F_T.getlength(tag) + 28
    d.rounded_rectangle((14, 12, 14 + tw, 44), 10, fill="#e0473f")
    d.text((28, 15), tag, font=F_T, fill="white")
    for i, r in enumerate(rows):
        d.text((20, 52 + i * 32), r, font=F_X, fill="#2b1d14")
    return img.rotate(angle, expand=True, resample=Image.BICUBIC)


def draft(P):
    """First cards from the project's own data; Claude rewrites them into short facts."""
    out = []
    for idea in P.get("ideas", []):
        if idea.get("status") == "done":
            sec = next((s for s in P.sections() if s["name"] == idea.get("where")), None)
            out.append({"at": round((sec["from"] if sec else 0.0) + 3.0, 1), "tag": "Idea",
                        "text": idea["idea"], "place": "auto"})
    techs = {"stage": "Synfig + Krita set", "room": "Synfig + Krita set"}
    for s in P.sections():
        out.append({"at": round(s["from"] + 1.5, 1), "tag": techs.get(s.get("set"), "Synfig"),
                    "text": f"Section '{s['name']}': every mouth comes from the vocals (Rhubarb), every move sits on a beat",
                    "place": "auto"})
    out.sort(key=lambda c: c["at"])
    P.p["popups"] = out
    P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} draft cards written to project.json 'popups' - rewrite them as short facts, then run popup.py")


def plan(P, t_start, film_dur):
    words = P.sheet().get("words", []) if (P.analysis / "song_sheet.json").exists() else []
    lyric_secs = [(s["from"], s["to"]) for s in P.sections() if s.get("lyrics")]
    cards, auto = [], 0
    for c in P.get("popups", []):
        at = c.get("at")
        if at is None and c.get("word"):
            at = next((w["t"] for w in words if word_matches(w["word"], c["word"])), None)
        if at is None:
            continue
        t0 = at - t_start
        if not (0 <= t0 < film_dur):
            continue
        place = c.get("place", "auto")
        if place == "auto":
            place = ("top_right", "top_left")[auto % 2]
            auto += 1
        if place.startswith("bottom") and any(a <= at < b for a, b in lyric_secs):
            place = place.replace("bottom", "top")       # lyrics run at the bottom here
        cx, cy, ang = PLACES.get(place, PLACES["top_right"])
        cards.append([t0, min(t0 + hold(c["text"]), film_dur), card(c.get("tag", "Info"), c["text"], ang), (cx, cy), place, c])
    for i, a in enumerate(cards):                         # never two cards on the same spot at once
        for b in cards[i + 1:]:
            if b[0] < a[1] and b[4] == a[4]:
                b[0] = a[1] + 0.2
                b[1] = b[0] + hold(b[5]["text"])
    return [c for c in cards if c[0] < film_dur]


def overlay_cards(src, cards, n, fps, out):
    """Decode src, draw the live cards on every frame (pop-in with overshoot wobble, pop-out), encode out (no audio)."""
    dec = subprocess.Popen([ffmpeg(), "-v", "error", "-i", str(src), "-frames:v", str(n), "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", *h264(), "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    f = 0
    while f < n:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        t = f / fps
        live = [c for c in cards if c[0] <= t < c[1]]
        if not live:
            enc.stdin.write(buf)
            f += 1
            continue
        img = Image.frombuffer("RGB", (W, H), buf).convert("RGBA")
        for t0, t1, cimg, (cx, cy), _, _ in live:
            u, out_u = (t - t0) * fps, (t1 - t) * fps
            s = out_u / 4 if out_u < 4 else 0.2 + u / 5 if u < 5 else 1.0 + 0.12 * np.exp(-(u - 5) / 2) * np.cos((u - 5) * 1.5)
            s = max(s, 0.01)
            cc = cimg.resize((max(1, int(cimg.width * s)), max(1, int(cimg.height * s))), Image.LANCZOS)
            x = int(min(max(cx - cc.width / 2, 8), W - cc.width - 8))
            y = int(min(max(cy - cc.height / 2, 8), H - cc.height - 8))
            img.alpha_composite(cc, (x, y))
        enc.stdin.write(img.convert("RGB").tobytes())
        f += 1
    dec.stdout.close()
    dec.wait()
    enc.stdin.close()
    enc.wait()
    return f


def pop_sound(P):
    ear = config.get("earshot")
    pop = P.cache / "sfx_bank" / "ui_pop__blip.wav"
    if ear and not pop.exists():
        pop.parent.mkdir(exist_ok=True)
        subprocess.run(config.cmdline([ear, "sfx", "render", "ui_pop/blip", "-o", str(pop), "--sr", "48000"]),
                       capture_output=True)
    return pop if pop.exists() else None


def with_pops(P, pic, audio_src, cards, dur, out):
    """Picture pic + audio of audio_src + one pop per card (earshot bank; without earshot the cards stay silent)."""
    pop = pop_sound(P)
    if cards and pop:
        delays = "".join(f"[2:a]adelay={int(c[0] * 1000)}|{int(c[0] * 1000)},volume=0.55[p{i}];" for i, c in enumerate(cards))
        mix = ("[1:a]aresample=48000,aformat=channel_layouts=stereo[m];[m]" + "".join(f"[p{i}]" for i in range(len(cards)))
               + f"amix=inputs={len(cards) + 1}:normalize=0:duration=first[a]")
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(pic), "-i", str(audio_src), "-i", str(pop), "-filter_complex",
                        delays + mix, "-map", "0:v", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", str(out)], check=True)
    else:
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(pic), "-i", str(audio_src), "-map", "0:v", "-map", "1:a",
                        "-t", f"{dur:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)


def credit_cards(P, credits):
    """project.json "popup_credits": cards over the credits (credits seconds). "at": s, or "segment": "post" | "gag" |
    "text" (+ "nth": 0, "at" = seconds into that segment, from cache/credits/timeline.json), or "sound": "x.wav"
    (found in the credits' sound track by cross-correlation, + "lead" s, default 0.2)."""
    specs = P.get("popup_credits", [])
    if not specs:
        return []
    tl_f = P.cache / "credits" / "timeline.json"
    tl = json.loads(tl_f.read_text(encoding="utf-8")) if tl_f.exists() else {"segments": [], "fps": P.fps}
    dur = duration(credits)
    out = []
    for c in specs:
        at = float(c.get("at", 0.0))
        if c.get("sound"):
            from media import decode
            env = lambda y: np.abs(y[: len(y) // 24 * 24]).reshape(-1, 24).mean(1)     # 2 kHz envelope
            a_, b_ = env(decode(credits, 48000)), env(decode(P.path(c["sound"]), 48000))
            if len(b_) < len(a_):
                cc_ = np.correlate(a_ - a_.mean(), b_ - b_.mean(), "valid")
                at = float(np.argmax(cc_)) / 2000 + float(c.get("lead", 0.2))
        elif c.get("segment"):
            segs = [sg for sg in tl["segments"] if sg[0] == c["segment"]]
            sg = segs[int(c.get("nth", 0))] if len(segs) > int(c.get("nth", 0)) else None
            if sg is None:
                print(f"  credit card '{c.get('tag')}': segment {c['segment']} not in the credits - skipped")
                continue
            at += sg[1] / tl.get("fps", P.fps)
        place = c.get("place", "top_right")
        cx, cy, ang = PLACES.get(place, PLACES["top_right"])
        out.append([at, min(at + float(c.get("duration", hold(c["text"]))), dur), card(c.get("tag", "Info"), c["text"], ang),
                    (cx, cy), place, c])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--to", type=float, help="only up to this film second (quick test)")
    ap.add_argument("--no-credits", action="store_true", help="do not build film_popup_with_credits.mp4")
    a = ap.parse_args()
    P = Project(a.project)
    if a.draft:
        return draft(P)
    base = P.cache / "film_raw.mp4"
    if not base.exists():
        raise SystemExit("cache/film_raw.mp4 missing - run build.py film first")
    t_start = min(s["from"] for s in P.sections())
    dur = a.to or duration(base)
    cards = plan(P, t_start, dur)
    fps = P.fps
    pic = P.cache / "popup_picture.mp4"
    overlay_cards(base, cards, int(dur * fps), fps, pic)
    raw = P.cache / "popup_raw.mp4"
    with_pops(P, pic, base, cards, dur, raw)
    out = P.dir / "film_popup.mp4"
    import build
    build.look(P, raw, P.cache / "popup_tmp.mp4")
    out = build.place(P.cache / "popup_tmp.mp4", out)
    err = check_video(out)
    print(f"-> {out.name}: {len(cards)} cards, {dur:.1f} s, {'0 decode errors' if not err else err[:200]}; list POPUPS.md")
    ccards = []
    credits = P.dir / (P.get("credits") or {}).get("out", "credits.mp4")
    if P.get("credits") and credits.exists() and not a.no_credits and not a.to:
        # the version with credits: film_popup.mp4 + credits.mp4 (cards from "popup_credits" over the credits part)
        ccards = credit_cards(P, credits)
        cdur = duration(credits)
        cpart = credits
        if ccards:
            cpic = P.cache / "popup_credits_picture.mp4"
            overlay_cards(credits, ccards, round(cdur * fps), fps, cpic)
            cpart = P.cache / "popup_credits.mp4"
            with_pops(P, cpic, credits, ccards, cdur, cpart)
        tmp = P.cache / "popup_with_credits_tmp.mp4"
        fc = (f"[0:v]fps={fps},format=yuv420p,setsar=1[v0];[1:v]fps={fps},format=yuv420p,setsar=1[v1];"
              "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];"
              "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(out), "-i", str(cpart), "-filter_complex", fc, "-map", "[v]",
                        "-map", "[a]", *h264(), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)], check=True)
        out2 = build.place(tmp, P.dir / "film_popup_with_credits.mp4")
        err2 = check_video(out2)
        print(f"-> {out2.name}: film {dur:.1f} s + credits {cdur:.1f} s, {len(ccards)} credit card(s) "
              + ", ".join(f"at credits {c[0]:.2f} s" for c in ccards) + f"; {'0 decode errors' if not err2 else err2[:200]}")
    fmt = lambda s: f"{int(s // 60)}:{s % 60:04.1f}"
    with open(P.dir / "POPUPS.md", "w", encoding="utf-8") as fh:
        fh.write(f"# Pop-up cards – {P.get('name', '')}\n\nFilm time of film_popup.mp4. Generated from project.json "
                 "'popups' by film-finish popup.py.\n\n| # | time | shown | tag | text |\n|---|---|---|---|---|\n")
        for i, c in enumerate(cards, 1):
            fh.write(f"| {i} | {fmt(c[0])} | {c[1] - c[0]:.1f} s | {c[5].get('tag', 'Info')} | {c[5]['text']} |\n")
        for i, c in enumerate(ccards, len(cards) + 1):
            fh.write(f"| {i} | credits {fmt(c[0])} | {c[1] - c[0]:.1f} s | {c[5].get('tag', 'Info')} | {c[5]['text']} |\n")
        if ccards:
            fh.write("\nCredit cards: in film_popup_with_credits.mp4 (credits time after the film).\n")


if __name__ == "__main__":
    main()
