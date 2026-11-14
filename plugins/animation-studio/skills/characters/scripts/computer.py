"""The Computer - a character that is a face on a screen (two round eyes, cheeks, a mouth; no body).

    import _studio; _studio.use("toon-2d", "characters")
    from computer import computer
    layers = computer((-2.4, 3.3, 2.4, 0.2), blink=[30, 120], bounce=[(48, 1), (60, 1)], mouth_cues=cues)

rect = (x0, y0, x1, y1) of the screen in Synfig units (top-left, bottom-right; y up). Everything scales with the
screen height h: eye radius 0.16 h at +-0.22 w, cheeks at +-0.33 w, mouth 0.2 h under the centre (lip sync size 0.3 w).
Colours: dark blue screen #1d3b5c, light ink #e8fbff, pink cheeks; a dark frame #1c1f26 around it.
`bounce` frames give a small squash of the face on beats (scale about the screen bottom).
`face_on` keys (0/1, constant) hide the face, e.g. while the screen shows big text instead.
Also: screen_texts (big text instead of the face), screen_badges (corner label FREE -> PRO ...), meter_keys +
screen_meter (usage bar along the screen bottom that fills, turns red and blinks on words, empties on others).
"""
from sif import V, anim, group, circle, rect as _rect, hexc


def computer(rect, fps=24, blink=(), bounce=(), mouth_cues=None, face_on=None, look_keys=None,
             screen="#1d3b5c", ink="#e8fbff", frame="#1c1f26", cheek="#ff8fb1", smile=True,
             blink_keys=None, bounce_keys=None, tilt_keys=None, look_units="radius"):
    """blink/bounce: frame lists (simple). blink_keys / bounce_keys / tilt_keys: ready keyframe lists that replace them
    (scale vectors, angle in degrees). look_keys: [(f, (dx, dy))] in eye radii (look_units="radius") or in Synfig
    units (look_units="units")."""
    x0, y0, x1, y1 = rect
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y0 - y1
    ink_c = hexc(ink)
    bl = list(blink_keys) if blink_keys else [(0, (1, 1))]
    for f in ([] if blink_keys else blink):
        bl += [(f - 1, (1, 1)), (f + 1, (1.05, 0.1), "linear"), (f + 3, (1, 1))]
    bo = list(bounce_keys) if bounce_keys else [(0, (1, 1))]
    for f in ([] if bounce_keys else bounce):
        f = f[0] if isinstance(f, tuple) else f
        bo += [(f, (1.06, 0.94), "linear"), (f + 5, (1, 1))]
    r = 0.16 * h
    face = []
    for ex in (cx - 0.22 * w, cx + 0.22 * w):
        ey = cy + 0.18 * h
        pupil_off = anim("vector", [(k[0], (ex + k[1][0] * r, ey + k[1][1] * r)) + tuple(k[2:]) for k in look_keys]) \
            if look_keys else V(ex, ey)
        face.append(group("Eye", [circle("Eye", ink_c, r, (ex, ey)),
                                  group("Pupil", [circle("Pupil", hexc(screen), r * 0.45, (0, 0)),
                                                  circle("Glint", ink_c, r * 0.15, (-r * 0.1, r * 0.15))],
                                        offset=pupil_off)],
                          origin=(ex, ey), offset=V(ex, ey), scale=anim("vector", bl)))
    for ex in (cx - 0.33 * w, cx + 0.33 * w):
        face.append(circle("Cheek", hexc(cheek, 0.45), 0.1 * h, (ex, cy - 0.12 * h), feather=0.05 * h))
    if mouth_cues is not None:
        from lipsync import mouth_layers
        face += mouth_layers(mouth_cues, fps, center=(cx, cy - 0.2 * h), size=0.3 * w, ink=ink_c, offset_frames=-1)
    elif smile:
        from sif import outline
        mw, my = 0.16 * w, cy - 0.2 * h
        face.append(outline("Smile", ink_c, [(cx - mw, my + 0.05 * h, 0.3 * mw, -0.4 * h),
                                             (cx + mw, my + 0.05 * h, 0.3 * mw, 0.4 * h)], 0.05 * h, loop=False))
    fr = 0.06 * h
    return [_rect("Screen frame", hexc(frame), (x0 - fr, y0 + fr), (x1 + fr, y1 - fr)),
            _rect("Screen", hexc(screen), (x0, y0), (x1, y1)),
            group("Computer face", face, origin=(cx, y1), offset=V(cx, y1), scale=anim("vector", bo),
                  angle=anim("angle", tilt_keys) if tilt_keys else None,
                  amount=anim("real", face_on) if face_on else None)]


def screen_texts(rect, events, frame_of, out_dir, tag="screen"):
    """Big text on the screen instead of the face: events [(t0, t1, text, colour)] -> image layers (Pillow), each
    switched on for its time. frame_of(t) -> scene frame. Monospace, fitted into the screen."""
    if not events:
        return []
    import os
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont
    from sif import image
    x0, y0, x1, y1 = rect
    font_path = next((f for f in ("C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/consola.ttf",
                                  "/System/Library/Fonts/Menlo.ttc",
                                  "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf") if os.path.exists(f)), None)
    out = []
    for i, (t0, t1, text, col) in enumerate(events):
        W, H = 800, int(800 * (y0 - y1) / (x1 - x0))
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        size = 120
        while size > 20:
            fnt = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
            bb = d.multiline_textbbox((0, 0), text, font=fnt, align="center")
            if bb[2] - bb[0] < W * 0.88 and bb[3] - bb[1] < H * 0.8:
                break
            size -= 6
        d.multiline_text(((W - (bb[2] - bb[0])) / 2, (H - (bb[3] - bb[1])) / 2 - bb[1]), text, font=fnt, fill=col,
                         align="center")
        p = Path(out_dir) / f"{tag}_{i}.png"
        img.save(p)
        amt = anim("real", [(0, 0.0, "constant"), (frame_of(t0), 1.0, "constant"), (frame_of(t1), 0.0, "constant")])
        out.append(group(f"Screen text {i}", [image(f"Screen text {i}", p.as_posix(), (x0, y0), (x1, y1))], amount=amt))
    return out


def screen_badges(rect, badges, frame_of, n_frames, out_dir, tag="badge"):
    """A small label that stays in the screen's top-right corner and changes on cue (FREE -> PRO -> MAX, a clock,
    a level, a battery ...). badges: [(t_from, t_to, text, text_colour, bg_colour)] in song seconds; each label pops in
    (overshoot) when it starts. frame_of(t) -> scene frame."""
    if not badges:
        return []
    import os
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont
    from sif import image
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y0 - y1
    fp = next((f for f in ("C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(f)), None)
    out = []
    for i, (t0, t1, text, col, bg) in enumerate(badges):
        fnt = ImageFont.truetype(fp, 64) if fp else ImageFont.load_default()
        tw, th = fnt.getbbox(text)[2:]
        img = Image.new("RGBA", (tw + 56, th + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, img.width - 4, img.height - 4), radius=18, fill=bg, outline="#2b1d14", width=6)
        d.text((28, 14), text, font=fnt, fill=col)
        p = Path(out_dir) / f"{tag}_{i}.png"
        img.save(p)
        bh = 0.17 * h                                   # badge height in units
        bw = bh * img.width / img.height
        cx, cy = x1 - bw / 2 - 0.04 * w, y0 - bh / 2 - 0.06 * h
        f0, f1 = frame_of(t0), frame_of(t1)
        if f1 < 0 or f0 > n_frames:
            continue
        pop = [(0, (1, 1))] if f0 <= 0 else [(0, (1, 1)), (f0, (0.2, 0.2), "linear"), (f0 + 4, (1.35, 1.35)), (f0 + 9, (1, 1))]
        amt = [(0, 1.0 if f0 <= 0 else 0.0, "constant"), (max(f0, 0), 1.0, "constant"), (max(f1, 1), 0.0, "constant")]
        out.append(group(f"Badge {text}", [image(f"Badge {text}", p.as_posix(), (cx - bw / 2, cy + bh / 2), (cx + bw / 2, cy - bh / 2))],
                         origin=(cx, cy), offset=V(cx, cy), scale=anim("vector", pop), amount=anim("real", amt)))
    return out


def meter_keys(events, frame_of, n_frames, start=0.55, creep=0.0, t_start=0.0, full=1.0, empty=0.08, fps=24):
    """Level / red / blink keys of a usage meter from events [(t, "fill"|"empty")] in song seconds (all events of the
    song, also those before the section: the state carries over). creep = rise per second between events.
    Returns (level_keys, red_keys, blink_keys) for screen_meter(); frame_of(t) -> scene frame."""
    lvl, red, t_last = start, start > 0.9, 0.0
    events = sorted(events)
    for t, kind in events:                                 # state at the section start
        if t >= t_start:
            break
        lvl, red, t_last = (full, True, t) if kind == "fill" else (empty, False, t)
    lvl = min(full, lvl + creep * max(0.0, t_start - t_last))
    level = [(0, lvl)]
    reds = [(0, 1.0 if red else 0.0, "constant")]
    full_spans, cur = [], (0 if red else None)
    for t, kind in events:
        if t < t_start:
            continue
        f = frame_of(t)
        if f > n_frames:
            break
        now = level[-1][1] + creep * max(0, f - level[-1][0]) / fps
        if kind == "fill":
            level += [(f, min(full, now)), (f + 14, full, "halt")]
            reds.append((f + 10, 1.0, "constant"))
            if cur is None:
                cur = f + 14
        else:
            level += [(f, min(full, now), "halt"), (f + 10, empty, "halt")]
            reds.append((f + 4, 0.0, "constant"))
            if cur is not None:
                full_spans.append((cur, f))
                cur = None
    if cur is not None:
        full_spans.append((cur, n_frames + 1))
    if creep and level[-1][0] < n_frames:
        level.append((n_frames, min(full, level[-1][1] + creep * (n_frames - level[-1][0]) / fps), "linear"))
    blink = [(0, 1.0, "constant")]
    for a, b in full_spans:                                # full and red: the bar blinks
        for k in range(max(a, 0), min(b, n_frames + 1), 6):
            blink.append((k, 0.55 if (k - a) // 6 % 2 == 0 else 1.0, "constant"))
        blink.append((min(b, n_frames + 1), 1.0, "constant"))
    return level, reds, blink


def screen_meter(rect, level_keys, red_keys, blink_keys=None, label=None, style="bar", out_dir=None, tag="meter",
                 ok="#5fd38a", warn="#e0473f", track="#0e1a2a"):
    """Usage bar along the bottom of the screen: fills up, turns red (level/red keys from meter_keys) and blinks
    while full. style "bar" (one bar) or "segments" (battery-like blocks). label: small text left of the bar."""
    from sif import R, comp_vec, region, outline
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y0 - y1
    bx0, bx1 = x0 + 0.08 * w, x1 - 0.08 * w
    by0, by1 = y1 + 0.17 * h, y1 + 0.08 * h
    out = []
    if label and out_dir:
        import os
        from pathlib import Path
        from PIL import Image, ImageDraw, ImageFont
        from sif import image
        fp = next((f for f in ("C:/Windows/Fonts/consolab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")
                   if os.path.exists(f)), None)
        fnt = ImageFont.truetype(fp, 48) if fp else ImageFont.load_default()
        tw, th = fnt.getbbox(label)[2:]
        img = Image.new("RGBA", (tw + 8, th + 8), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((4, 0), label, font=fnt, fill="#e8fbff")
        p = Path(out_dir) / f"{tag}_label.png"
        img.save(p)
        lh = (by0 - by1) * 1.3
        lw = lh * img.width / img.height
        out.append(image("Meter label", p.as_posix(), (bx0, by0 + lh + 0.02 * h), (bx0 + lw, by0 + 0.02 * h)))
    frame_pts = [(bx0 - 0.04, by0 + 0.04, 0, 0), (bx1 + 0.04, by0 + 0.04, 0, 0), (bx1 + 0.04, by1 - 0.04, 0, 0), (bx0 - 0.04, by1 - 0.04, 0, 0)]
    out += [region("Meter track", hexc(track), frame_pts), outline("Meter frame", hexc("#e8fbff", 0.6), frame_pts, 0.03)]
    if style == "segments":
        n = 10
        sw = (bx1 - bx0) / n
        cells = []
        for i in range(n):
            pts = [(bx0 + i * sw + 0.02, by0, 0, 0), (bx0 + (i + 1) * sw - 0.02, by0, 0, 0),
                   (bx0 + (i + 1) * sw - 0.02, by1, 0, 0), (bx0 + i * sw + 0.02, by1, 0, 0)]
            cells.append(region("Cell", hexc(ok), pts))
            cells.append(region("Cell red", hexc(warn), pts, amount=anim("real", red_keys)))
        fill = cells
    else:
        pts = [(bx0, by0, 0, 0), (bx1, by0, 0, 0), (bx1, by1, 0, 0), (bx0, by1, 0, 0)]
        fill = [region("Meter fill", hexc(ok), pts), region("Meter fill red", hexc(warn), pts, amount=anim("real", red_keys))]
    cy = (by0 + by1) / 2
    out.append(group("Meter level", fill, origin=(bx0, cy), offset=V(bx0, cy),
                     scale=comp_vec(anim("real", level_keys), R(1.0)),
                     amount=anim("real", blink_keys) if blink_keys else None))
    return out
