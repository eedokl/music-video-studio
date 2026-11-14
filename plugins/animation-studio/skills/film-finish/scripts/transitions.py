"""Transitions computed frame by frame on the finished cut - no handles needed, every section stays on its song frame.

Each transition only uses frames that exist around the cut (the last frame of the outgoing section is held as a still
where needed), so the picture never shifts against the song. Kinds (project.json "transitions"):

  {"at": 11.6, "kind": "zoom_through", "center": [0.22, 0.30], "frames": 12}
      the outgoing last frame keeps zooming into a point (a window, a door, a screen) and dissolves; the new scene
      comes in slightly enlarged and settles
  {"at": 38.3, "kind": "glow", "center": [0.5, 0.5], "color": "#ffecbe"}
      a warm light burst from a point (8 frames around the cut) - a room becomes a stage
  {"at": 66.7, "kind": "screen_zoom", "center": [0.5, 0.39], "frames": 10}
      the camera zooms into a point before the cut (a big screen) and the close-up settles after it
  {"at": 113.0, "kind": "iris", "center": [0.51, 0.27], "close": 14, "open": 11}
      the picture closes in a circle onto a detail (a grin), black for one frame, the next scene opens from the middle;
      "shaders": true uses the Shaders IrisWipe masks (shaders_render.py, WebGPU) instead of the numpy circle;
      "hold_black": 10 closes the iris that many frames EARLY and holds black up to the cut (an iris-out ending)
  {"at": 178.7, "kind": "white"}   flash on a downbeat (1 frame up, 7 frames decay)
  {"at": 211.8, "kind": "black"}   short dip to black around the cut
centre: 0..1 from the top-left (or pixels when > 1). "align": "cut" (default - centred on the cut, as in "Prompts!")
or "after" (the whole transition runs over the first frames of the incoming shot, as in the ai_efficiency film). "at" in song seconds. Keep transitions 6-14 frames and leave
abrupt musical stops as hard cuts. Always applied to the untouched cut (cache/film_cut.mp4), so re-running never
stacks transitions.

    from transitions import apply
    apply(src_mp4, dst_mp4, specs, t_start, fps)          # picture only; audio is handled by build.py
"""
import subprocess

import numpy as np
from PIL import Image

import _studio  # noqa: E402
_studio.use()
from encoding import h264  # noqa: E402
from media import ffmpeg  # noqa: E402

FLASH = {-1: 0.3, 0: 0.9, 1: 0.7, 2: 0.5, 3: 0.33, 4: 0.2, 5: 0.1, 6: 0.04}
GLOW = {-3: 0.15, -2: 0.35, -1: 0.6, 0: 0.85, 1: 0.6, 2: 0.4, 3: 0.22, 4: 0.1}


def smooth(u):
    return u * u * (3 - 2 * u)


def rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


class Frame:
    def __init__(self, w, h):
        self.W, self.H = w, h
        self.YY, self.XX = np.mgrid[0:h, 0:w].astype(np.float32)

    def px(self, c):
        x, y = c
        return (x * self.W if x <= 1 else x, y * self.H if y <= 1 else y)

    def zoom(self, img, s, c=None):
        """enlarge around point c (s >= 1); c drifts to the centre the closer we get"""
        W, H = self.W, self.H
        c = c or (W / 2, H / 2)
        if s <= 1.0001:
            return img
        w, h = int(W * s), int(H * s)
        big = Image.fromarray(img).resize((w, h), Image.BICUBIC)
        u = min(1.0, (s - 1) / 0.8)
        cx, cy = c[0] + (W / 2 - c[0]) * (1 - u), c[1] + (H / 2 - c[1]) * (1 - u)
        x0 = int(min(max(cx * s - W / 2, 0), w - W))
        y0 = int(min(max(cy * s - H / 2, 0), h - H))
        return np.asarray(big.crop((x0, y0, x0 + W, y0 + H)))

    def radial(self, c, r, soft=40.0):
        d = np.sqrt((self.XX - c[0]) ** 2 + (self.YY - c[1]) ** 2)
        return np.clip((r - d) / soft + 0.5, 0, 1)[..., None]


def plan(specs, t_start, fps):
    """-> list of (kind, cut_frame, spec) on film frames"""
    out = []
    for s in specs:
        kind = s.get("kind", "white")
        f0 = round((float(s["at"]) - t_start) * fps)
        if s.get("align") == "after":                 # run the whole transition over the incoming shot
            f0 += {"glow": 3, "screen_zoom": int(s.get("frames", 10)), "iris": int(s.get("close", 14)),
                   "white": 1, "black": 6}.get(kind, 0)
        out.append((kind, f0, s))
    return out


def touches(items, n):
    for kind, f0, s in items:
        lo = {"zoom_through": 0, "glow": -3, "screen_zoom": -int(s.get("frames", 10)),
              "iris": -int(s.get("close", 14)) - int(s.get("hold_black", 0)),
              "white": -1, "black": -6}.get(kind, -14)
        hi = {"zoom_through": int(s.get("frames", 12)), "glow": 4, "screen_zoom": int(s.get("settle", 6)),
              "iris": int(s.get("open", 11)), "white": 6, "black": 6}.get(kind, 14)
        if f0 + lo - 1 <= n <= f0 + hi:
            return True
    return False


def apply(src, dst, specs, t_start, fps=24, iris_masks=None):
    """Read the cut as a frame stream, replace the frames of every transition, write dst (picture only)."""
    items = plan(specs, t_start, fps)
    probe = subprocess.run([ffmpeg(), "-i", str(src)], capture_output=True, text=True, errors="replace").stderr
    import re
    m = re.search(r"(\d{3,5})x(\d{3,5})", probe)
    W, H = int(m.group(1)), int(m.group(2))
    G = Frame(W, H)
    dec = subprocess.Popen([ffmpeg(), "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-an", *h264(), "-pix_fmt", "yuv420p", str(dst)],
                           stdin=subprocess.PIPE)
    held = {}                                         # last outgoing frame per zoom_through
    n, changed = 0, 0
    while True:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        if not touches(items, n):
            enc.stdin.write(buf)
            n += 1
            continue
        for kind, f0, s in items:
            k = n - f0
            c = G.px(s.get("center", (0.5, 0.5)))
            if kind == "zoom_through":
                L = int(s.get("frames", 12))
                if k == -1:
                    held[f0] = img.copy()
                if 0 <= k < L and f0 in held:
                    u = smooth((k + 1) / L)
                    a = G.zoom(held[f0], 1 + 0.7 * u ** 1.5, c).astype(np.float32)
                    b = G.zoom(img, 1.25 - 0.25 * u).astype(np.float32)
                    img = (a * (1 - u) + b * u).clip(0, 255).astype(np.uint8)
                    changed += 1
            elif kind == "glow" and k in GLOW:
                r = (200 + 900 * (k + 3) / 8) * W / 1280
                g = G.radial(c, r, 260 * W / 1280) * GLOW[k]
                img = (img.astype(np.float32) * (1 - g) + rgb(s.get("color", "#ffecbe")) * g).clip(0, 255).astype(np.uint8)
                changed += 1
            elif kind == "screen_zoom":
                L, Lo = int(s.get("frames", 10)), int(s.get("settle", 6))
                if -L <= k < 0:
                    img = G.zoom(img, 1 + float(s.get("amount", 0.9)) * smooth((k + L + 1) / L), c)
                    changed += 1
                elif 0 <= k < Lo:
                    img = G.zoom(img, 1.18 - 0.18 * smooth((k + 1) / Lo))
                    changed += 1
            elif kind == "iris":
                Lc, Lo, hb = int(s.get("close", 14)), int(s.get("open", 11)), int(s.get("hold_black", 0))
                if hb and -hb <= k < 0:                         # closed early: black up to the cut
                    img = np.zeros_like(img)
                    changed += 1
                elif -Lc - hb <= k < -hb:
                    k2 = k + hb
                    u = smooth((k2 + Lc + 1) / Lc)
                    if iris_masks and s.get("shaders"):         # opt-in: Shaders IrisWipe masks
                        mk = iris_masks(c, Lc, (W, H))[k2 + Lc][..., None]
                    else:
                        mk = G.radial(c, (1400 * (1 - u) ** 1.8 + 70) * W / 1280, 6)   # lingers on the detail
                    if k2 == -1:
                        mk = mk * 0
                    img = (img.astype(np.float32) * mk).astype(np.uint8)
                    changed += 1
                elif 0 <= k < Lo:
                    u = smooth((k + 1) / Lo)
                    img = (img.astype(np.float32) * G.radial((W / 2, H / 2), (30 + 780 * u ** 2) * W / 1280, 6)).astype(np.uint8)
                    changed += 1
            elif kind == "white" and k in FLASH:
                img = (img.astype(np.float32) * (1 - FLASH[k]) + 255 * FLASH[k]).clip(0, 255).astype(np.uint8)
                changed += 1
            elif kind == "black" and -6 <= k <= 6:
                a = 1 - abs(k) / 7
                img = (img.astype(np.float32) * (1 - a)).astype(np.uint8)
                changed += 1
        enc.stdin.write(np.ascontiguousarray(img).tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    return n, changed
