# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Render every shot to scenes/<shot>/f.%04d.png (project.json "size", default 1280x720; 24 fps) for film-finish, with the photographic finish.

Material per shot, best first:
  1. the selected clip (selection.json "clip"): placed on the song with clips.frame_index - LTX lead-in skipped,
     LTX lip-sync 1 frame later (delay_frames), plus the measured lag (dt = +lag/24 s); S2V 16 fps by frame repeat
  2. the picked still (start image / B-roll) with a slow camera move and depth parallax (ai/depth/*_depth.png)
  3. a placeholder card (shot, technique, line, idea) - visible gaps, never silent failures
  + "typo" (typo.py): NEWSFLASH, stamps on the sung words, departure board, title - drawn on its own ground or over
    the material above (technique "typo" has no material)
Finish (project.json "finish"): film grain sigma 2.5 (5.5 until 0.25.0 read as noise in the small mp4), vignette 0.38,
darker band under the lyrics, fade in 0.5 s at the song start and out 2.5 s at its end (at most 40 % of the last shot); "ai_label" (text) is shown
in the last 3 s of the last shot (LTX licence + plugin rule: AI content is labelled).
Usage: uv run render_shots.py [<project>]
         [--only s02,s05] [--labels]   (--labels: shot/technique/material in the corner, for the animatic)
"""
import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video")
import claudia  # noqa: E402
import clips  # noqa: E402
import creative  # noqa: E402
import typo  # noqa: E402
from cvio import imread, video_capture  # noqa: E402
from media import duration  # noqa: E402
from song_project import Project  # noqa: E402

W, H = 1280, 720                       # set from project.json "size" in main() (P.size), also for typo.py
MOVES = [dict(zoom=(1.0, 1.10), pan=(0, 0.02, 0, -0.02), par=26), dict(zoom=(1.10, 1.0), pan=(0.03, 0, -0.03, 0), par=30),
         dict(zoom=(1.04, 1.10), pan=(-0.04, 0, 0.04, 0), par=34), dict(zoom=(1.08, 1.02), pan=(0, -0.03, 0, 0.02), par=24)]


def font(size):
    for f in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def cover(img):
    h, w = img.shape[:2]
    s = max(W / w, H / h)
    img = cv2.resize(img, (max(W, round(w * s)), max(H, round(h * s))),
                     interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LANCZOS4)
    y0, x0 = (img.shape[0] - H) // 2, (img.shape[1] - W) // 2
    return img[y0:y0 + H, x0:x0 + W]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


class ClipSource:
    def __init__(self, path, lag=0):
        self.meta = clips.read_meta(path)
        self.lag = lag
        cap = video_capture(path)
        self.fr = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            self.fr.append(cover(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
        if not self.fr:
            raise RuntimeError(f"{path} has no frames")

    def frame(self, u, t):
        return self.fr[clips.frame_index(t, self.meta, self.lag, len(self.fr))].astype(np.float32)


class StillSource:
    """Still with a slow camera move; near parts (depth map) move more than far ones."""
    def __init__(self, path, depth, mv):
        bgr = imread(path)
        if bgr is None:
            raise RuntimeError(f"cannot read {path}")
        self.img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
        dep = imread(depth, cv2.IMREAD_GRAYSCALE) if depth and Path(depth).exists() else None
        if dep is None:
            dep = np.full(self.img.shape[:2], 128, np.uint8)
        self.dep = cv2.resize(dep, (self.img.shape[1], self.img.shape[0])).astype(np.float32) / 255.0
        self.mv, (self.h, self.w) = mv, self.img.shape[:2]
        self.base = max(W / self.w, H / self.h)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.xx, self.yy = xx - W / 2, yy - H / 2

    def frame(self, u, t=None):
        mv, e = self.mv, ease(u)
        z = mv["zoom"][0] + (mv["zoom"][1] - mv["zoom"][0]) * e
        px = (mv["pan"][0] + (mv["pan"][2] - mv["pan"][0]) * e) * W
        py = (mv["pan"][1] + (mv["pan"][3] - mv["pan"][1]) * e) * H
        s = self.base * z
        mx = self.w / 2 + (self.xx - px) / s
        my = self.h / 2 + (self.yy - py) / s
        dep = cv2.remap(self.dep, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        par = mv["par"] * (e - 0.5)
        dz = mv["zoom"][1] - mv["zoom"][0]
        mx2 = mx - (par * np.sign(mv["pan"][2] - mv["pan"][0] or 1) + self.xx / W * dz * 60) * (dep - 0.5) / s
        my2 = my - (self.yy / H * dz * 60) * (dep - 0.5) / s
        return cv2.remap(self.img, mx2.astype(np.float32), my2.astype(np.float32), cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REFLECT)


def card(s):
    img = Image.new("RGB", (W, H), (32, 34, 40))
    d = ImageDraw.Draw(img)
    d.text((60, 60), f"{s['name']}  {s['technique']}  (no material yet)", font=font(34), fill=(217, 119, 87))
    y = 140
    for txt in (s.get("line", ""), s.get("idea", ""), s.get("subject", "") or s.get("action", "")):
        if txt:
            d.text((60, y), txt[:90], font=font(26), fill=(230, 226, 218))
            y += 50
    return np.asarray(img, np.float32)


def source(P, s, sel):
    """-> (object with .frame(u, t) or None, description)"""
    name = s["name"]
    c = (sel.get("clip") or {}).get(name)
    if c and not c.get("still") and c.get("file") and P.path(c["file"]).exists():   # "still": the still by choice
        return ClipSource(P.path(c["file"]), c.get("lag", 0)), f"clip {c['file']} lag {c.get('lag', 0):+d}"
    grp = "broll" if s["technique"] == "broll" else "start"
    img = (sel.get(grp) or {}).get(name)
    if img and P.path(img).exists():
        dep = P.dir / "ai" / "depth" / f"{name}_{grp}_depth.png"
        mv = MOVES[creative.rng(P, f"move:{name}").randrange(len(MOVES))]
        if grp == "start":
            mv = dict(mv, zoom=(1.0, 1.06))
        return StillSource(P.path(img), dep, mv), f"still {img}"
    return None, "card"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--only", default="")
    ap.add_argument("--labels", action="store_true")
    a = ap.parse_args()
    global W, H
    P = Project(a.project)
    P.check("claudia-music-video")                 # project.json validated before any long step
    W, H = typo.W, typo.H = P.size   # frame size of the film (project.json "size")
    words = (P.sheet().get("words", []) if (P.analysis / "song_sheet.json").exists() else [])
    sel = json.loads((P.dir / "selection.json").read_text(encoding="utf-8")) if (P.dir / "selection.json").exists() else {}
    fin = claudia.pin_finish(P)
    song_len = duration(P.song)
    secs = P.sections()
    last = secs[-1]["name"] if secs else None
    if secs and "fade_out" not in (P.get("finish") or {}):
        # claudia3: 2.5 s darkened almost the whole 3 s last shot - at most 40 % of the last shot (>= 0.8 s)
        fin["fade_out"] = min(fin["fade_out"], max(0.8, 0.4 * (song_len - secs[-1]["from"])))
    print(claudia.finish_line(fin), flush=True)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vign = (1 - fin["vignette"] * np.clip((rr - 0.55) / 0.85, 0, 1) ** 1.6)[..., None]
    band = (1 - fin["text_band"] * np.clip((yy - H * 0.68) / (H * 0.22), 0, 1) ** 1.2)[..., None]
    only = [x for x in a.only.split(",") if x]
    rep = []
    for s in secs:
        if only and s["name"] not in only:
            continue
        rng = np.random.default_rng(creative.rng(P, f"grain:{s['name']}").randrange(1 << 30))
        try:
            src, desc = source(P, s, sel)
        except Exception as ex:                      # broken clip -> card, logged
            src, desc = None, f"card (error: {ex})"
        f0 = round(s["from"] * P.fps)                # absolute rounding: the pieces add up to the song (no drift)
        n = round(s["to"] * P.fps) - f0
        out = P.dir / "scenes" / s["name"]
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        typo_only = s.get("typo") and src is None
        if typo_only:
            desc = f"typo {s['typo'].get('kind')}"
        base_card = card(s) if src is None and not typo_only else None
        for fi in range(n):
            t = (f0 + fi) / P.fps
            u = fi / max(n - 1, 1)
            img = src.frame(u, t) if src is not None else (None if typo_only else base_card.copy())
            if s.get("typo"):
                img = typo.draw(s, img, u, t, words)
            img = img * (vign * band if s.get("lyrics") else vign)
            if fin["grain"]:
                img += rng.normal(0, fin["grain"], (H // 2, W // 2, 1)).astype(np.float32).repeat(2, 0).repeat(2, 1)
            k = 1.0
            if fin["fade_in"] and t < fin["fade_in"]:
                k = min(k, t / fin["fade_in"])
            if fin["fade_out"] and song_len - t < fin["fade_out"]:
                k = min(k, max(0.0, (song_len - t) / fin["fade_out"]))
            fr = Image.fromarray(np.clip(img * k, 0, 255).astype(np.uint8))
            if P.get("ai_label") and s["name"] == last and s["to"] - t <= 3.0 and not (s.get("typo") or {}).get("note"):
                d = ImageDraw.Draw(fr)
                txt = P["ai_label"]
                f = font(20)
                d.rectangle([(16, 16), (32 + d.textlength(txt, font=f), 50)], fill=(10, 12, 16))
                d.text((24, 21), txt, font=f, fill=(235, 230, 220))
            if a.labels:
                d = ImageDraw.Draw(fr)
                lab = f"{s['name']} {s['technique']} · {desc.split()[0]}"
                d.rectangle([(10, 660), (24 + d.textlength(lab, font=font(20)), 692)], fill=(0, 0, 0))
                d.text((16, 664), lab, font=font(20), fill=(217, 119, 87) if src is None else (240, 236, 228))
            fr.save(out / f"f.{fi:04d}.png", compress_level=1)
        rep.append(f"{s['name']} {s['from']:7.2f}-{s['to']:7.2f} {s['technique']:14s} {desc}")
        print(rep[-1], flush=True)
    if only and (P.dir / "render.log").exists():   # --only: keep the lines of the other shots (takes.py reads them)
        new = {ln.split()[0]: ln for ln in rep}
        old = [ln for ln in (P.dir / "render.log").read_text(encoding="utf-8").splitlines() if ln.strip()]
        have = {ln.split()[0] for ln in old}
        rep = [new.get(ln.split()[0], ln) for ln in old] + [ln for ln in rep if ln.split()[0] not in have]
        order = {s["name"]: i for i, s in enumerate(secs)}
        rep.sort(key=lambda ln: order.get(ln.split()[0], 1 << 20))
    with open(P.dir / "render.log", "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")


if __name__ == "__main__":
    main()
