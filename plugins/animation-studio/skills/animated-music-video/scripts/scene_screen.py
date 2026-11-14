"""The Computer's screen in scene.py: the face, text screens and tints on cue words, corner badges, the usage meter and
app windows popping out over the screen (c = scene_context.SceneContext; the events are collected in its build).
"""
from pathlib import Path

import numpy as np

import creative  # noqa: E402
from song_project import allowed, word_matches
from sif import V, anim, group, hexc, image
from computer import computer, screen_texts, screen_badges, meter_keys, screen_meter
from scene_context import box, as_list


def tint_layers(c):
    x0, y0, x1, y1 = c.SCREEN
    return [box("Screen tint", x0, y0, x1, y1, hexc(col), amount=anim("real", c.keys(c.span_keys((t0, t1)))))
            for t0, t1, col in c.tint_ev]


def screen_face(c, k, rect=None):
    S, E, F = c.S, c.E, c.F
    blinks = [F(t) for t in np.arange(S + 1.7, E, 5.3)]
    bounce = [F(b["t"]) for b in c.beats if (c.act(k, b["t"]) or c.in_dance(b["t"])) and not c.quiet(b["t"])]
    face_on = [(0, 1.0, "constant")]
    for t0, t1, _, _ in c.screen_ev:
        face_on += [(F(t0), 0.0, "constant"), (F(t1), 1.0, "constant")]
    return computer(tuple(rect or c.SCREEN), fps=c.fps, blink=blinks, bounce=bounce, mouth_cues=c.cues_in_window(k),
                    face_on=c.keys(face_on))


def screen_texts_layers(c):
    return screen_texts(c.SCREEN, c.screen_ev, c.F, c.P.cache, tag=f"screen_{c.section}") if c.screen_ev else []


def badge_layers(c):
    """project.json "screen_badges": [{"text": "FREE", "bg": "#3a7d44"}, {"text": "PRO", "on": "pro", "bg": "#2f6fb5"}]
    - a label in the screen corner that changes on a word and keeps its state across sections."""
    spec = c.P.get("screen_badges", [])
    if not spec or not any(c.figs_cfg[k].get("kind") == "screen" for k in c.names):
        return []
    times = []
    for i, b in enumerate(spec):
        t = 0.0 if not b.get("on") else next((w["t"] for w in c.words if word_matches(w["word"], b["on"])
                                               and w["t"] >= (times[-1] if times else 0.0)), None)
        times.append(t if t is not None else 1e9)
    items = [(t0, times[i + 1] if i + 1 < len(times) else 1e9, b["text"], b.get("color", "#ffffff"), b.get("bg", "#3a7d44"))
             for i, (t0, b) in enumerate(zip(times, spec)) if t0 < 1e9]
    return screen_badges(c.SCREEN, items, c.F, c.N, c.P.cache, tag=f"badge_{c.section}")


def meter_layers(c):
    """project.json "screen_meter": {"fill_on": ["limit"], "empty_on": ["upgrade"], "start": 0.55, "creep": 0.0,
    "label": "TOKENS", "style": "bar"|"segments", "sections": [...]} - a usage bar on the Computer's screen; it fills
    and turns red (blinking) on a fill word and empties on an empty word; the state carries over between sections."""
    P, keys = c.P, c.keys
    spec = P.get("screen_meter")
    if not spec or not any(c.figs_cfg[k].get("kind") == "screen" for k in c.names) or \
            (spec.get("sections") and c.section not in spec["sections"]):
        return []
    ev = []
    for kind_, key in (("fill", "fill_on"), ("empty", "empty_on")):
        for pre in as_list(spec.get(key)):
            last = -99
            for w in c.words:
                if word_matches(w["word"], pre) and w["t"] - last > 1.5:
                    ev.append((w["t"], kind_))
                    last = w["t"]
    style = spec.get("style") or creative.pick(P, "meter_style", ("bar", "segments"))
    lv, rd, bl = meter_keys(ev, c.F, c.N, start=float(spec.get("start", 0.55)), creep=float(spec.get("creep", 0.0)),
                            t_start=c.S, fps=c.fps)
    return screen_meter(c.SCREEN, keys(lv), keys(rd), keys(bl), label=spec.get("label"), style=style, out_dir=P.cache,
                        tag=f"meter_{c.section}")


def window_layers(c):
    """project.json "screen" events with "window": "Context Window" (+ "rows": 5, "color": title bar colour,
    "min": 1.5) - instead of text ON the screen an app window pops out over the screen (scale 0 -> 1.12 -> 1) on
    the word and stays until the line ends (at least `min` s)."""
    from PIL import Image as PILImage, ImageDraw as PILDraw, ImageFont as PILFont
    P, S, E, F, lines = c.P, c.S, c.E, c.F, c.lines
    x0, y0, x1, y1 = c.SCREEN
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ww, wh = (x1 - x0) * 1.12, (y0 - y1) * 1.05
    out = []
    for i, ev in enumerate(P.get("screen", [])):
        if not ev.get("window") or not allowed(ev, c.section):
            continue
        png = P.cache / f"window_{c.section}_{i}.png"
        W_, H_ = 640, int(640 * wh / ww)
        im = PILImage.new("RGBA", (W_, H_), (0, 0, 0, 0))
        d = PILDraw.Draw(im)
        d.rounded_rectangle((0, 0, W_ - 1, H_ - 1), 14, fill="#f3f6fb", outline="#2b1d14", width=5)
        tb = int(H_ * 0.15)
        d.rounded_rectangle((0, 0, W_ - 1, tb), 14, fill=ev.get("color", "#7a8ba8"), outline="#2b1d14", width=5)
        fnt = None
        for f_ in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if Path(f_).exists():
                fnt = PILFont.truetype(f_, int(tb * 0.62))
                break
        d.text((24, tb * 0.17), str(ev["window"]), font=fnt or PILFont.load_default(), fill="#ffffff")
        for j, x_ in enumerate((W_ - 30, W_ - 62, W_ - 94)):
            d.ellipse((x_ - 11, tb / 2 - 11, x_ + 11, tb / 2 + 11), fill=("#ff6b6b", "#ffd23f", "#6bd36b")[j])
        rows = int(ev.get("rows", 5))
        for j in range(rows):
            yy = tb + (H_ - tb) * (j + 0.7) / (rows + 0.4)
            d.rounded_rectangle((36, yy, 36 + (W_ - 72) * (0.92 if j % 2 == 0 else 0.68), yy + (H_ - tb) * 0.07), 6,
                                fill="#b8c4d8")
        im.save(png)
        ks = [(0, (0, 0))]
        last = -99
        for w in c.words:
            if word_matches(w["word"], ev["word"]) and S <= w["t"] < E and w["t"] - last > 1.0:
                last = w["t"]
                ln = lines[w["line"]] if w.get("line") is not None and w["line"] < len(lines) else None
                t1 = max(ln["end"] if ln else w["t"] + 1.6, w["t"] + float(ev.get("min", 1.5)))
                fc = F(w["t"])
                ks += [(fc - 1, (0, 0), "linear"), (fc + 3, (1.12, 1.12)), (fc + 6, (0.97, 0.97)), (fc + 9, (1, 1)),
                       (F(t1) - 3, (1, 1), "halt"), (F(t1) + 1, (0, 0), "linear")]
        if len(ks) > 1:
            img = image(f"Window {i}", png.as_posix(), (cx - ww / 2, cy + wh / 2), (cx + ww / 2, cy - wh / 2))
            out.append(group(f"Window {i}", [img], origin=(cx, cy), offset=V(cx, cy), scale=anim("vector", c.keys(ks))))
    return out
