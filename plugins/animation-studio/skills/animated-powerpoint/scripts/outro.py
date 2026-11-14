"""Outro on the slide: the film comes back to the slide, pushes in on one figure's face, an iris closes on it, the
figure winks, the iris closes and a title card ends the film (reference: the finale of the ai_efficiency film).

  outro.py clips/<name>/outro.json [--no-look]

outro.json (paths relative to it):
  {"deck": "../../deck/deck.json", "slide": 5, "figures_dir": "../../figures", "figure": "fritz",
   "eye": 1,                      which pupil of parts.json winks (0 = left in the picture, 1 = right; default 1)
   "from_image": "last.png",      optional: last frame of the scene before - it shrinks and turns into the slide
   "frames": 162, "fps": 24, "size": [1920, 1080],
   "zoom": 2.3, "wink": [99, 101, 108, 110],     half closed, closed, half open, open
   "iris": [80, 98],              iris starts / holds on the face (radius 1200 -> 440 px), closes after the wink
   "title": ["Who keeps changing my office?", "1 year of efficiency with AI  -  what's next?"], "title_at": 126,
   "title_color": [250, 249, 244], "subtitle_color": null (= the figure's accent colour), "look": "none"|"standard",
   "sound": true}                  glockenspiel + ping on the wink (earshot)
The wink is drawn from the slide itself: the eye is covered with the skin colour sampled around it, a squashed copy of
the eye (half) or a happy ink arc (closed) is put on top - no redrawing of the figure.
Outputs frames_outro/f_NNNN.png, <name>.mp4 (+ sound), first.png/last.png, check.json.
Usage: uv run --no-project --with pillow --with numpy --with scipy python outro.py clips/finale/outro.json
"""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import _studio
_studio.use("film-finish")
import config  # noqa: E402
from encoding import h264  # noqa: E402


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def eye_on_slide(fig_dir, k):
    """(cx, cy, rx, ry) of pupil k in slide pixels (measured on eyes.png)."""
    from scipy import ndimage as ndi
    fj = json.loads((fig_dir / "figure.json").read_text(encoding="utf-8"))
    pj = json.loads((fig_dir / "parts.json").read_text(encoding="utf-8"))
    t, (x0, y0) = fj["to_slide"], fj["crop"][:2]
    a = np.asarray(Image.open(fig_dir / "eyes.png"))[..., 3] > 128
    lab, n = ndi.label(a)
    if not pj.get("eyes") or n == 0:
        raise SystemExit(f"figure {fig_dir.name} has no pupils in parts.json / eyes.png - the outro winks one eye")
    k = min(max(int(k), 0), len(pj["eyes"]) - 1)                # one-eyed figure: its only eye winks
    ex, ey = pj["eyes"][k]
    best = min(range(1, n + 1), key=lambda i: np.hypot(*(np.array(ndi.center_of_mass(lab == i))[::-1] - (ex, ey))))
    ys, xs = np.nonzero(lab == best)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    rx, ry = (xs.max() - xs.min()) / 2, (ys.max() - ys.min()) / 2
    S = lambda x, y: (t["ox"] + t["ax"] * (x0 + x), t["oy"] + t["ay"] * (y0 + y))
    (sx, sy), (sx2, sy2) = S(cx, cy), S(cx + rx, cy + ry)
    other = pj["eyes"][1 - k] if len(pj["eyes"]) > 1 else pj["eyes"][k]
    return (sx, sy, sx2 - sx, sy2 - sy), S(*other)


def wink_states(slide, eye):
    """Slide in three states: open, half, closed."""
    cx, cy, rx, ry = eye
    s = slide.size[0] / 3840                                     # numbers below are for a 4K slide
    arr = np.asarray(slide).astype(np.float32)
    R = int(60 * s + 2 * max(rx, ry))
    yy, xx = np.mgrid[int(cy) - R:int(cy) + R + 1, int(cx) - R:int(cx) + R + 1]
    d = np.hypot((xx - cx) / (rx + 8 * s), (yy - cy) / (ry + 8 * s))
    patch = arr[int(cy) - R:int(cy) + R + 1, int(cx) - R:int(cx) + R + 1]
    ring = patch[(d > 1.1) & (d < 1.5)]
    light = ring[ring.mean(1) > 200]
    skin = tuple(int(v) for v in np.median(light if len(light) else ring, 0))
    ink = (22, 22, 24)
    out = {"open": slide}
    for st in ("half", "closed"):
        mask = Image.new("L", slide.size, 0)
        ImageDraw.Draw(mask).ellipse((cx - rx - 6 * s, cy - ry - 6 * s, cx + rx + 6 * s, cy + ry + 6 * s), fill=255)
        im = Image.composite(Image.new("RGB", slide.size, skin), slide, mask.filter(ImageFilter.GaussianBlur(3 * s)))
        dr = ImageDraw.Draw(im)
        w = max(2, round(10 * s))
        if st == "half":
            e = slide.crop((int(cx - rx - 2), int(cy - ry - 2), int(cx + rx + 2), int(cy + ry + 2)))
            e = e.resize((e.size[0], max(4, e.size[1] * 2 // 5)), Image.LANCZOS)
            im.paste(e, (int(cx - rx - 2), int(cy + ry / 3 - e.size[1] / 2)))
            dr.line([(cx - rx - 4 * s, cy + 3 * s), (cx + rx + 4 * s, cy + 3 * s)], fill=ink, width=max(2, round(9 * s)))
        else:
            dr.arc((cx - rx - 8 * s, cy - 12 * s, cx + rx + 8 * s, cy + 30 * s), 190, 350, fill=ink, width=w)
            dr.line([(cx + rx + 9 * s, cy + 4 * s), (cx + rx + 19 * s, cy - 3 * s)], fill=ink, width=max(2, round(6 * s)))
        out[st] = im
    return out


def main():
    f = Path(sys.argv[1]).resolve()
    D = f.parent
    P = json.loads(f.read_text(encoding="utf-8"))
    deck_file = (D / P.get("deck", "../../deck/deck.json")).resolve()
    deck = json.loads(deck_file.read_text(encoding="utf-8"))
    slide = next(s for s in deck["slides"] if s["n"] == P["slide"])
    fig_dir = (D / P.get("figures_dir", "../../figures")).resolve() / P["figure"]
    W, H = P.get("size", [1920, round(1920 * deck["height"] / deck["width"] / 2) * 2])
    fps, n = P.get("fps", 24), P.get("frames", 162)
    src = Image.open(deck_file.parent / slide["clean"]).convert("RGB")
    eye, other = eye_on_slide(fig_dir, P.get("eye", 1))
    states = {k: v.resize((W, H), Image.LANCZOS) for k, v in wink_states(src, eye).items()}
    sc = W / src.size[0]
    ex, ey = eye[0] * sc, eye[1] * sc
    ox, oy = other[0] * sc, other[1] * sc
    dist = math.hypot(ox - ex, oy - ey)                          # face centre: half-way to the other eye, a bit lower
    face = (ex + 0.525 * (ox - ex), ey + 0.14 * dist)
    zmax = P.get("zoom", 2.3)
    h0, h1, h2, h3 = P.get("wink", [99, 101, 108, 110])
    i0, i1 = P.get("iris", [80, 98])
    t_at = P.get("title_at", 126)
    title = P.get("title") or [slide.get("title", ""), ""]
    from clip import font
    acc = P.get("subtitle_color") or [round(255 - (255 - v) * 0.5) for v in accent_from(fig_dir)]   # light accent
    tc = P.get("title_color", [250, 249, 244])
    fb, fr = font(True, round(76 * H / 1080)), font(False, round(48 * H / 1080))
    first = Image.open(D / P["from_image"]).convert("RGB").resize((W, H)) if P.get("from_image") else None
    clash = [n for n in ("stage.json", "scene_stage.json", "intro_stage.json") if (D / n).exists()]
    if clash:                       # <name>.mp4, stage.mp4, first/last.png, check.json would overwrite that clip's
        sys.exit(f"{D} holds another clip ({clash[0]}) - give the outro its own folder, e.g. clips/finale/outro.json")
    out = D / "frames_outro"        # not frames/: clip.py and scene.py keep their Synfig frames there
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    for k in range(n):
        if first is not None and k < 24:
            u = smooth(k / 24)
            s = 1 - 0.12 * u
            aa = first.resize((int(W * s), int(H * s)), Image.LANCZOS)
            base = Image.new("RGB", (W, H), (28, 26, 24))
            base.paste(aa, ((W - aa.size[0]) // 2, (H - aa.size[1]) // 2))
            im = Image.blend(base, states["open"], u)
        else:
            t0 = 24 if first is not None else 0
            kk = 0.25 * smooth((k - t0) / 56) + 0.75 * smooth((k - (i0 - 10)) / 28)
            z = 1 + (zmax - 1) * kk
            cw, ch = int(W / z), int(H / z)
            cx = int(W / 2 + (face[0] - W / 2) * kk)
            cy = int(H / 2 + (face[1] - H / 2) * kk)
            bx = min(max(0, cx - cw // 2), W - cw)
            by = min(max(0, cy - ch // 2), H - ch)
            st = states["half"] if k in (h0, h2) else states["closed"] if h1 <= k < h2 else states["open"]
            im = st.crop((bx, by, bx + cw, by + ch)).resize((W, H), Image.LANCZOS)
            fx, fy = (face[0] - bx) * W / cw, (face[1] - by) * H / ch
            if k >= i0:
                r = (1200 - 760 * smooth((k - i0) / (i1 - i0)) - 436 * smooth((k - h3 - 2) / 12)) * H / 1080
                m = Image.new("L", (W, H), 0)
                ImageDraw.Draw(m).ellipse((fx - r, fy - r, fx + r, fy + r), fill=255)
                im = Image.composite(im, Image.new("RGB", (W, H)), m.filter(ImageFilter.GaussianBlur(3)))
            if k >= t_at:
                u = smooth((k - t_at) / 10)
                im = Image.new("RGB", (W, H))
                d = ImageDraw.Draw(im)
                d.text((W / 2, H / 2 - 50 * H / 1080), title[0], font=fb, fill=tuple(int(v * u) for v in tc), anchor="mm")
                if len(title) > 1 and title[1]:
                    d.text((W / 2, H / 2 + 50 * H / 1080), title[1], font=fr, fill=tuple(int(v * u) for v in acc),
                           anchor="mm")
        im.save(out / f"f_{k:04d}.png")
    ff = config.need("ffmpeg")
    raw = D / "stage.mp4"
    subprocess.run([ff, "-y", "-v", "error", "-framerate", str(fps), "-i", str(out / "f_%04d.png")] + h264()
                   + ["-pix_fmt", "yuv420p", str(raw)], check=True)
    name = D / f"{D.name}.mp4"
    look = P.get("look", "none")
    if look != "none" and "--no-look" not in sys.argv:
        subprocess.run([sys.executable, str(_studio.skill_dir("film-finish") / "scripts" / "apply_look.py"), str(raw),
                        "-o", str(name), "--look", look], check=True)
    else:
        shutil.copy(raw, name)
    shutil.copy(out / "f_0000.png", D / "first.png")
    shutil.copy(out / f"f_{n - 1:04d}.png", D / "last.png")
    if P.get("sound", True):
        import sound
        m = sound.Mix(n, fps, D.parent.parent / "cache" / "sfx")
        m.sfx(h1, "mallet/glock", ["--pitch", "E6"], -20)
        m.sfx(h1 + 1, "hover_tick/ping", [], -27)
        m.write(D / "ton.wav", loudnorm=False)
        sound.mux(name, D / "ton.wav")
    check = {"frames": n, "seconds": round(n / fps, 2), "size": [W, H], "eye_slide_px": [round(v, 1) for v in eye],
             "face_px": [round(v, 1) for v in face], "wink": [h0, h1, h2, h3]}
    (D / "check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
    print(f"-> {name} {check}")


def accent_from(fig_dir):
    from clip import accent_color
    return accent_color({"dir": fig_dir})


if __name__ == "__main__":
    main()
