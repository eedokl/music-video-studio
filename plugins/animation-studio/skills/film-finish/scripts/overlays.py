# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Screen overlays on top of a section: text gags (keyword -> lettering pops up) and word-by-word lyrics.

Why a separate track instead of drawing text into the scene: camera moves and panels crop text; as an overlay
applied after rendering it always stays readable, and new gags need no new scene render.
project.json:
  "gags": [{"word": "token", "text": "TOKENS!", "color": "#ffd23f", "place": "top_right", "duration": 1.3}]
          word = start of a sung word (case-insensitive); place = top_left | top_right | top | middle | auto
          (alternating); size = letter height in px of a 720-high frame, scaled with project "size" (default 64, project-wide "gag_size": 110 for big shout words). Companies only as neutral lettering, never logos.
  section: "lyrics": true -> the sung line in a box at the bottom, words appear as they are sung, the current word
           highlighted. "lyrics_style" (project or per section): "script" (default, handwritten, yellow highlight) |
           "caps" (upper case, clay highlight #D97757 - the Claudia videos) | "pop" / "rock" / "whisper" (letter by
           letter: each letter pops in as it is sung, held words stretch with the voice, the line kicks on the beat;
           rock = big Impact, red; whisper = small, pale, trembling) | {"base": "rock", "highlight": "#7fe3ff", ...}
  "lyrics_skip": ["Pro-Limit", {"contains": "Ha. Ha."}, {"index": 46}]   (project or section) lines without lyrics
           (announcements, effects); a string = start of the line text
  "lyrics_lines": [{"line": "Mein letzter", "style": "whisper"}, {"contains": "Ultra", "style": {"base": "pop",
           "size": 44, "bounce": 6}}, {"index": 71, "style": "rock"}]   (project or section) per-line style overrides
           Trailing punctuation ("Prompts!") pops in with the last letter, never at the word start.
  gags: "sections": [...] / "not_sections": [...] limit a gag to sections; word = prefix | "=exact" | "re:regex"
           (song_project.word_matches). Two gags never share a place at the same time (the later one moves to a free
           place: top_right, top_left, top, middle; a gag already shown >= 0.5 s is replaced on its spot instead).
  gags with pictures: {"word": "chips", "icon": "chip"} (built in: money, chip, kiss, heart, arrow_up, arrow_down,
           star, bolt) or {"word": "...", "image": "gags/laugh.png", "text": "HA!"} (own PNG, optional word under it)
Output: overlays/<section>.mov (PNG codec with alpha, frame 0 = section start), events in analysis/gags.json.
Usage: uv run overlays.py <section> [--project .]
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import _studio  # noqa: E402
_studio.use("song-analysis")
from media import ffmpeg  # noqa: E402
from song_project import Project, allowed, word_matches  # noqa: E402

W, H = 1280, 720                   # set from project.json "size" in main() (P.size); px values below are for 720p
FONTS_BOLD = ["C:/Windows/Fonts/impact.ttf", "/System/Library/Fonts/Supplemental/Impact.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONTS_TEXT = ["C:/Windows/Fonts/segoeprb.ttf", "C:/Windows/Fonts/arialbd.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
PLACES = {"top_left": (0.22, 0.2), "top_right": (0.78, 0.2), "top": (0.5, 0.15), "middle": (0.5, 0.42)}


def font(candidates, size):
    for s in candidates:
        if Path(s).exists():
            return ImageFont.truetype(s, size)
    return ImageFont.load_default()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gag_events(P, S, E, words, section=None):
    rules = P.get("gags", [])
    out, last, auto = [], {}, 0
    for w in words:
        if not (S <= w["t"] < E):
            continue
        for r in rules:
            if not allowed(r, section):               # "sections" / "not_sections"
                continue
            if word_matches(w["word"], r["word"]):
                key = r.get("text") or r.get("icon") or r.get("image")
                if w["t"] - last.get(key, -99) >= float(r.get("gap", 1.5)):
                    place = r.get("place", "auto")
                    dur = float(r.get("duration", 1.3))
                    if place == "auto":
                        place = ("top_right", "top_left")[auto % 2]
                        auto += 1
                    # never two overlays on the same spot at the same time: a gag shown >= 0.5 s gives its spot to the
                    # new one (rapid shout words replace each other), else the new one moves to a free spot
                    occ = [g for g in out if g["place"] == place and g["t"] < w["t"] + dur and w["t"] < g["t"] + g["duration"]]
                    if occ and all(w["t"] - g["t"] >= 0.5 for g in occ):
                        for g in occ:
                            g["duration"] = round(w["t"] - g["t"], 3)
                    elif occ:
                        busy = {g["place"] for g in out if g["t"] < w["t"] + dur and w["t"] < g["t"] + g["duration"]}
                        free = [q for q in ("top_right", "top_left", "top", "middle") if q not in busy]
                        if not free:
                            break
                        place = free[0]
                    out.append({"t": round(w["t"], 3), "text": r.get("text", ""), "color": r.get("color", "#ffd23f"),
                                "icon": r.get("icon"), "image": str(P.path(r["image"])) if r.get("image") else None,
                                "place": place, "duration": dur, "word": w["word"],
                                "size": int(r.get("size", P.get("gag_size", 64)) * P.scale)})
                    last[key] = w["t"]
                break
    return out


def draw_gag(img, g, t):
    """Pop: 0 -> 1.18 -> 1.0 within 0.25 s, hold, fade out over 0.2 s. Slightly tilted like comic lettering."""
    u = t - g["t"]
    if u < 0 or u > g["duration"]:
        return
    s = 1.18 * u / 0.12 if u < 0.12 else 1.18 - 0.18 * (u - 0.12) / 0.13 if u < 0.25 else 1.0
    alpha = 1.0 if u < g["duration"] - 0.2 else max(0.0, (g["duration"] - u) / 0.2)
    if s <= 0.05:
        return
    if g.get("icon") or g.get("image"):
        src = Image.open(g["image"]).convert("RGBA") if g.get("image") else icon(g["icon"], g["color"])
        k = 2.2 * g.get("size", 64) * s / max(src.size)
        lay = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.LANCZOS)
        if alpha < 1:
            lay.putalpha(lay.getchannel("A").point(lambda v: int(v * alpha)))
        if g.get("text"):                                   # an icon may carry a short word under it
            f = font(FONTS_BOLD, max(8, int(g.get("size", 64) * 0.6 * s)))
            tw, th = f.getbbox(g["text"])[2:]
            both = Image.new("RGBA", (max(lay.width, tw + 20), lay.height + th + 16), (0, 0, 0, 0))
            both.alpha_composite(lay, ((both.width - lay.width) // 2, 0))
            ImageDraw.Draw(both).text(((both.width - tw) // 2, lay.height), g["text"], font=f,
                                      fill=rgb(g["color"]) + (int(255 * alpha),), stroke_width=4,
                                      stroke_fill=(43, 29, 20, int(255 * alpha)))
            lay = both
    else:
        f = font(FONTS_BOLD, max(8, int(g.get("size", 64) * s)))
        tw, th = f.getbbox(g["text"])[2:]
        lay = Image.new("RGBA", (tw + 40, th + 40), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((20, 14), g["text"], font=f, fill=rgb(g["color"]) + (int(255 * alpha),),
                                 stroke_width=max(2, int(g.get("size", 64) / 10 * s)),
                                 stroke_fill=(43, 29, 20, int(255 * alpha)))
    lay = lay.rotate(-7 if g["place"].endswith("left") else 7, expand=True, resample=Image.BICUBIC)
    cx, cy = PLACES.get(g["place"], (0.5, 0.2))
    img.alpha_composite(lay, (int(cx * W - lay.width / 2), int(cy * H - lay.height / 2)))


ICONS = ("money", "chip", "kiss", "heart", "arrow_up", "arrow_down", "star", "bolt")


def icon(name, color="#ffd23f"):
    """Built-in picture gags drawn with Pillow (ink outline, flat colours) - for anything else pass "image"."""
    n, ink = 240, (43, 29, 20, 255)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = rgb(color) + (255,)
    if name == "money":
        d.text((n / 2, n / 2), "$$$", font=font(FONTS_BOLD, 150), fill=(90, 200, 90, 255), stroke_width=10,
               stroke_fill=ink, anchor="mm")
    elif name == "chip":
        d.rounded_rectangle((60, 60, 180, 180), 14, fill=(60, 66, 80, 255), outline=ink, width=8)
        for i in range(5):
            o = 72 + i * 24
            for a, b in (((o, 30), (o, 60)), ((o, 180), (o, 210)), ((30, o), (60, o)), ((180, o), (210, o))):
                d.line((a, b), fill=(200, 170, 60, 255), width=10)
        d.rectangle((95, 95, 145, 145), fill=c, outline=ink, width=4)
    elif name == "kiss":
        d.chord((40, 70, 200, 190), 180, 360, fill=(225, 40, 70, 255), outline=ink, width=8)
        d.chord((40, 110, 200, 200), 0, 180, fill=(200, 25, 55, 255), outline=ink, width=8)
        d.line((48, 150, 192, 150), fill=ink, width=7)
    elif name == "heart":
        d.ellipse((40, 50, 125, 135), fill=(230, 50, 80, 255), outline=ink, width=8)
        d.ellipse((115, 50, 200, 135), fill=(230, 50, 80, 255), outline=ink, width=8)
        d.polygon([(46, 110), (194, 110), (120, 205)], fill=(230, 50, 80, 255))
        d.line([(46, 110), (120, 205), (194, 110)], fill=ink, width=8)
    elif name in ("arrow_up", "arrow_down"):
        pts = [(120, 25), (210, 120), (155, 120), (155, 215), (85, 215), (85, 120), (30, 120)]
        if name == "arrow_down":
            pts = [(x, n - y) for x, y in pts]
        d.polygon(pts, fill=(90, 200, 90, 255) if name == "arrow_up" else (230, 70, 60, 255), outline=ink, width=8)
    elif name == "bolt":
        d.polygon([(140, 20), (60, 135), (115, 135), (90, 220), (185, 95), (128, 95)], fill=c, outline=ink, width=8)
    else:                                                     # star
        pts = [(120 + 100 * math.cos(math.radians(-90 + 36 * i)) * (1 if i % 2 == 0 else 0.45),
                120 + 100 * math.sin(math.radians(-90 + 36 * i)) * (1 if i % 2 == 0 else 0.45)) for i in range(10)]
        d.polygon(pts, fill=c, outline=ink, width=8)
    return im


def line_hit(spec, line):
    """Does a lyric line match? spec = "text prefix" | {"line": prefix} | {"contains": text} | {"index": lyric line no.}"""
    text = line.get("text", "").strip().lower()
    if isinstance(spec, str):
        return text.startswith(spec.strip().lower())
    if spec.get("index") is not None:
        return line.get("line") == int(spec["index"])
    if spec.get("contains"):
        return spec["contains"].lower() in text
    return bool(spec.get("line")) and text.startswith(spec["line"].strip().lower())


def lyric_lines(lines, words, S, E, skip=(), styles=()):
    """skip: line specs that get no lyric (announcements, effects); styles: [(spec, style)] per-line style overrides."""
    out = []
    for l in lines:
        if l["end"] < S or l["t"] > E or any(line_hit(k, l) for k in skip):
            continue
        ws = [w for w in words if w.get("line") == l["line"] and w["word"].strip("–—-")]
        st = next((st for spec, st in styles if line_hit(spec, l)), None)
        out.append({"t0": l["t"] - 0.3, "t1": l["end"] + 0.8, "words": [(w["word"], w["t"], w["end"]) for w in ws],
                    "style": st})
    for i in range(len(out) - 1):                              # a line stays until just before the next one
        out[i]["t1"] = min(out[i]["t1"] + 0.4, max(out[i + 1]["t0"] - 0.1, out[i]["t0"] + 0.5))
    return out


LYRIC_STYLES = {   # project.json "lyrics_style": a name or a dict overriding these keys
    "script": {"fonts": FONTS_TEXT, "size": 36, "upper": False, "text": "#faf6ec", "highlight": "#ffd23f",
               "box": [20, 16, 30, 150], "y": -92},
    "caps": {"fonts": ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arialbd.ttf",
                       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
             "size": 34, "upper": True, "text": "#f4f1ea", "highlight": "#D97757", "box": [10, 10, 12, 120], "y": -88},
    "pop": {"fonts": FONTS_TEXT, "size": 42, "upper": False, "text": "#ffffff", "highlight": "#ffd23f", "box": None,
            "y": -80, "reveal": "letters", "bounce": 3, "shake": 0},
    "rock": {"fonts": FONTS_BOLD, "size": 54, "upper": False, "text": "#ffffff", "highlight": "#ff5046", "box": None,
             "y": -80, "reveal": "letters", "bounce": 10, "shake": 0},
    "whisper": {"fonts": FONTS_TEXT, "size": 30, "upper": False, "text": "#bec8e1", "highlight": "#ffffff", "box": None,
                "y": -70, "reveal": "letters", "bounce": 0, "shake": 1.6},
}
SPREAD, LEAD = 0.65, 0.08          # letters spread over 65 % of a word; text a hair before the voice


def lyric_style(P, section=None):
    st = (section or {}).get("lyrics_style") or P.get("lyrics_style", "script")
    base = dict(LYRIC_STYLES.get(st if isinstance(st, str) else st.get("base", "script"), LYRIC_STYLES["script"]))
    if isinstance(st, dict):
        base.update({k: v for k, v in st.items() if k != "base"})
    if P.scale != 1:                                  # "size" other than 1280x720: same look, scaled
        for k in ("size", "y", "bounce", "shake"):
            if isinstance(base.get(k), (int, float)):
                base[k] = round(base[k] * P.scale) if k in ("size", "y") else base[k] * P.scale
    base["font"] = font(base["fonts"], base["size"])
    return base


def draw_letters(img, z, t, st, beats):
    """Letter by letter as in "Prompts!": each letter pops in (small -> big with a little overshoot) when its share of
    the word is sung, so held words ("meeeehr") run along with the voice; the line kicks on each beat."""
    f = st["font"]
    meas = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words = [(w.upper() if st["upper"] else w, a0, a1) for w, a0, a1 in z["words"]]
    space = meas.textlength(" ", font=f)
    widths = [meas.textlength(w, font=f) for w, _, _ in words]
    total = sum(widths) + space * (len(widths) - 1)
    if total > W - 80:
        f = font(st["fonts"], int(st["size"] * (W - 80) / total))
        widths = [meas.textlength(w, font=f) for w, _, _ in words]
        space = meas.textlength(" ", font=f)
        total = sum(widths) + space * (len(widths) - 1)
    fade = max(0.0, min(1.0, (t - z["t0"]) / 0.15, (z["t1"] - t) / 0.2))
    prev = max((b for b in beats if b <= t), default=-9)
    kick = max(0.0, 1 - (t - prev) / 0.18)
    y = H + st["y"] - st.get("bounce", 0) * kick
    d = ImageDraw.Draw(img)
    x = (W - total) / 2
    for (w, ws, we), ww in zip(words, widths):
        ws, we = ws - LEAD, we - LEAD
        col = rgb(st["highlight"]) if ws <= t < we + 0.05 else rgb(st["text"])
        letters = sum(1 for c in w if c.isalnum())
        k, cx, prev_at = 0, x, ws
        for c in w:
            cw = meas.textlength(c, font=f)
            # letters spread over the word; punctuation after a letter comes with that letter (not at the word start)
            at = ws + (we - ws) * SPREAD * (k / max(letters, 1)) if c.isalnum() else (prev_at if k else ws)
            prev_at = at
            k += c.isalnum()
            if t >= at:
                u = min(1.0, (t - at) / 0.12)
                sc = 0.75 + 0.25 * u + 0.18 * math.sin(u * math.pi)
                al = int(255 * min(1.0, u * 2.5) * fade)
                sh = st.get("shake", 0)
                dx, dy = math.sin(t * 41 + cx) * sh, math.cos(t * 37 + cx) * sh - (1 - u) * 10
                f2 = font(st["fonts"], max(8, int(f.size * sc)))
                ox = (cw - meas.textlength(c, font=f2)) / 2
                d.text((cx + ox + dx, y + dy + (f.size - f2.size) * 0.7), c, font=f2, fill=col + (al,),
                       stroke_width=max(2, f.size // 12), stroke_fill=(23, 18, 13, al), anchor="ls")
            cx += cw
        x += ww + space


def draw_lyrics(img, lines, t, st, beats=()):
    z = next((z for z in lines if z["t0"] <= t < z["t1"]), None)
    if not z or not z["words"]:
        return
    st = z.get("style") or st
    if st.get("reveal") == "letters":
        return draw_letters(img, z, t, st, beats)
    d = ImageDraw.Draw(img)
    f = st["font"]
    words = [(w.upper() if st["upper"] else w, a0, a1) for w, a0, a1 in z["words"]]
    text = " ".join(w for w, _, _ in words)
    tw = d.textlength(text, font=f)
    x0, y0 = (W - tw) / 2, H + st["y"]
    a = min(1.0, (t - z["t0"]) / 0.2, (z["t1"] - t) / 0.25)
    if st.get("box"):
        r, g, b, alpha = st["box"]
        d.rounded_rectangle((x0 - 22, y0 - 12, x0 + tw + 22, y0 + st["size"] + 16), radius=18, fill=(r, g, b, int(alpha * a)))
    x = x0
    for w, wt0, wt1 in words:
        if t >= wt0 - 0.08:                                   # a word appears as it is sung (a hair early)
            col = rgb(st["highlight"]) if wt0 - 0.08 <= t < wt1 + 0.1 else rgb(st["text"])
            d.text((x, y0), w, font=f, fill=col + (int(255 * a),), stroke_width=2, stroke_fill=(43, 29, 20, int(255 * a)))
        x += d.textlength(w + " ", font=f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("section")
    ap.add_argument("--project", default=".")
    a = ap.parse_args()
    global W, H
    P = Project(a.project)
    P.check("film-finish")                 # project.json validated before any long step
    W, H = P.size
    A = P.section(a.section)
    S, E, fps = float(A["from"]), float(A["to"]), P.fps
    sheet = P.sheet()
    gags = gag_events(P, S, E, sheet["words"], a.section)
    f_text = lyric_style(P, A)
    per_line = [(x, lyric_style(P, {"lyrics_style": x["style"]})) for x in P.get("lyrics_lines", []) + A.get("lyrics_lines", [])
                if x.get("style")]
    skip = P.get("lyrics_skip", []) + A.get("lyrics_skip", [])
    lines = lyric_lines(sheet["lines"], sheet["words"], S, E, skip, per_line) if A.get("lyrics") else []
    beats = [b["t"] for b in sheet.get("beats", [])]
    allg = json.loads((P.analysis / "gags.json").read_text(encoding="utf-8")) if (P.analysis / "gags.json").exists() else {}
    allg[a.section] = gags
    (P.analysis / "gags.json").write_text(json.dumps(allg, ensure_ascii=False, indent=1), encoding="utf-8")
    out = P.dir / "overlays" / f"{a.section}.mov"
    out.parent.mkdir(exist_ok=True)
    n = round((E - S) * fps)
    p = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps),
                          "-i", "-", "-c:v", "png", "-pix_fmt", "rgba", str(out)], stdin=subprocess.PIPE)
    empty = Image.new("RGBA", (W, H), (0, 0, 0, 0)).tobytes()
    for i in range(n):
        t = S + i / fps
        if not any(g["t"] <= t <= g["t"] + g["duration"] for g in gags) and not any(z["t0"] <= t < z["t1"] for z in lines):
            p.stdin.write(empty)
            continue
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_lyrics(img, lines, t, f_text, beats)
        for g in gags:
            draw_gag(img, g, t)
        p.stdin.write(img.tobytes())
    p.stdin.close()
    p.wait()
    print(f"-> {out.relative_to(P.dir)}: {n} frames, {len(gags)} gags ({', '.join(g['text'] for g in gags) or '-'}), "
          f"lyric lines {len(lines)}")


if __name__ == "__main__":
    main()
