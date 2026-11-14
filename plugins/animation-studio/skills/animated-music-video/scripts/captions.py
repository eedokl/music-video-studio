# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Comic caption box: the sung line types itself word by word into a yellow box, in time with the singing.

For comic sections (section "kind": "panels" and comic flights rendered by toon-2d render_multiplane.py into
scenes/<section>/): the box sits fixed on the screen (never inside a panel - the camera would crop it), pops up empty
at the line start, each word appears when it is sung (word times from analysis/song_sheet.json, spread over the
caption's words; everything stands 0.8 s before the box fades) and fades before the next line / cut.
project.json, per section: "caption": true | {"place": "top_left" | "top" | "top_right" | "bottom_left" | "bottom_right",
  "width": 520, "size": 30, "box": "#fff3b0", "ink": "#2b1d14",
  "group": "panel" | "couplet" | "line", "places": {"p5": "bottom_right"}, "comic": "comic/comic.json", "lead": 1.5,
  "ghost": 0.3}   ghost = opacity of the words not yet sung (0 = they pop in only when sung)
Grouping (like a comic narrator box, one box per panel): "panel" puts all lines sung while the camera reads one panel
into ONE box (panel windows from the comic page's camera keys - "comic", or found via the section's renderer json);
"couplet" pairs consecutive lines; "line" = one box per line. Default: "panel" when a comic page is found, "line" for
"kind": "panels" (a hard cut per line anyway), else "couplet". A box stays until the next one starts (short
cross-fade, no empty gap - the lyric never vanishes while e.g. a figure breaks out of the page).
The rendered frames are kept in scenes/<section>_raw/ (first run moves them there), so re-running never stacks boxes.
scenes/<section>_raw/composited.json records a CONTENT hash of every composite written to scenes/<section>/; each
composite is saved under a temp name, logged in composited.partial, and only then renamed to f.NNNN.png - so every
frame visible under its final name is known, even after a pass killed at any moment.
Only a frame in scenes/<section>/ whose content this pass never wrote means the external renderer made a new take -
then the new frames replace the stale raw copy. Copying, zipping or checking out the project (new mtimes) changes
nothing; an interrupted pass is simply composited again from the raw originals.
Narrator inset over externally rendered sections (section "kind": "external" + "inset", e.g. a multiplane intro or a
comic flight): scene.py renders only the round inset as a transparent Synfig track into scenes/<section>_inset/ and
this pass lays it over the raw frames (under nothing, over the caption box) - so any renderer's frames get the inset.
Usage: uv run captions.py <section> [--project .]
       (scene.py --render calls it for sections with "caption")
"""
import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import _studio  # noqa: E402
_studio.use("song-analysis")
import derived  # noqa: E402
from song_project import Project  # noqa: E402

FONTS = ["C:/Windows/Fonts/segoeprb.ttf", "C:/Windows/Fonts/comicbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def frame_size(P):
    """FRAME SIZE - the caption layer's canvas = the project's frame size (project.json "size", default 1280x720)."""
    return tuple(P.size)


def px(P, v):
    """A pixel value designed for 720p, scaled to the project's frame height (identical at the default size)."""
    return int(round(v * P.scale))


def font(size):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def comic_windows(P, A, spec):
    """[(t0, t1, panel_id)] from the comic page's camera keys (song seconds), or [] if no comic page is found."""
    import json
    import re
    cands = []
    if spec.get("comic"):
        cands.append(P.dir / spec["comic"])
    m = re.search(r"([\w./-]+\.json)", str(A.get("renderer", "")))
    if m:
        cands.append(P.dir / m.group(1))
    for c in cands:
        if not c.exists():
            continue
        d = json.loads(c.read_text(encoding="utf-8"))
        if "camera" not in d and d.get("comic"):          # breakout.json -> its comic page
            c = c.parent / d["comic"]
            if not c.exists():
                continue
            d = json.loads(c.read_text(encoding="utf-8"))
        cam = d.get("camera") or []
        fps = float(d.get("fps", P.fps))
        S = float(A["from"])
        starts = []                                      # first key of each panel view, in order
        for k in cam:
            v = k.get("view", "")
            if v != "page" and (not starts or starts[-1][1] != v):
                starts.append((S + k["frame"] / fps, v))
        if starts:
            return [(t, starts[i + 1][0] if i + 1 < len(starts) else float(A["to"]), v)
                    for i, (t, v) in enumerate(starts)]
    return []


def caption_events(P, A):
    """[(f0, f1, rows, word_frames, place)] per caption box of the section (frames relative to the section start)."""
    S, E, fps = float(A["from"]), float(A["to"]), P.fps
    spec = A.get("caption") if isinstance(A.get("caption"), dict) else {}
    sheet = P.sheet()
    lines, words = sheet["lines"], sheet["words"]
    fnt = font(px(P, int(spec.get("size", 30))))         # caption sizes are given for 720p
    maxw = px(P, int(spec.get("width", 520)))
    wins = comic_windows(P, A, spec)
    group = spec.get("group") or ("panel" if wins else "line" if A.get("kind") == "panels" else "couplet")
    sec = [l for l in lines if S - 0.5 <= l["t"] < E - 0.3]
    groups = []                                          # [{"t", "end", "text", "panel"}]
    for l in sec:
        pid = None
        if group == "panel" and wins:
            lead = float(spec.get("lead", 1.5))         # the camera reaches a panel up to ~1.5 s after its line starts
            pid = ([w[2] for w in wins if w[0] <= l["t"] + lead] or [wins[0][2]])[-1]
        g = groups[-1] if groups else None
        join = g is not None and (
            l["t"] - g["t"] <= 0.3                       # lines closer than 0.3 s always share one box
            or (group == "panel" and pid == g["panel"])
            or (group == "couplet" and g["n"] < 2 and l["t"] - g["end"] < 2.5))
        if join:
            sep = " " if l["t"] - g["end"] <= 0.3 or g["text"].rstrip()[-1:] in ".,!?…:;–-" else spec.get("join", " – ")
            g.update(text=g["text"] + sep + l["text"], end=l["end"], n=g["n"] + 1)
        else:
            groups.append({"t": l["t"], "end": l["end"], "text": l["text"], "panel": pid, "n": 1})
    out = []
    for i, g in enumerate(groups):
        t0 = g["t"]
        t1 = groups[i + 1]["t"] if i + 1 < len(groups) else min(E, g["end"] + 1.0)
        text = " ".join(w for w in g["text"].replace("(", " (").split() if not w.startswith("(") and not w.endswith(")"))
        cap = text.split()
        if not cap:
            continue
        rows, cur = [], ""
        for w in cap:                                    # wrap to the box width
            trial = (cur + " " + w).strip()
            if cur and fnt.getlength(trial) > maxw:
                rows.append(cur)
                cur = w
            else:
                cur = trial
        rows.append(cur)
        st = [w["t"] for w in words if t0 - 0.2 <= w["t"] < t1 and not w["word"].startswith("(")]
        n = len(cap)
        wt = [st[round(j * (len(st) - 1) / max(n - 1, 1))] for j in range(n)] if len(st) >= 2 else             [t0 + (t1 - t0) * 0.8 * j / max(n - 1, 1) for j in range(n)]
        lim = t1 - 0.8                                   # all words stand 0.8 s before the box fades
        if wt[-1] > lim and lim > wt[0]:
            a0 = wt[0]
            wt = [a0 + (x - a0) * (lim - a0) / (wt[-1] - a0) for x in wt]
        place = (spec.get("places") or {}).get(g["panel"] or "", spec.get("place", "top_left"))
        out.append((round((t0 - S) * fps), round((t1 - S) * fps), rows, [round((x - S) * fps) for x in wt], place))
    return out, fnt, spec


LEDGER = "composited"            # scenes/<section>_raw/composited.json (+ .partial) - same files as before derived.py


def _ledger(raw):
    return derived.Ledger(raw, LEDGER)


def _fresh_render(frames, raw):
    """True when scenes/<name>/ holds a frame this script never wrote (a re-render by the external renderer) -
    then the raw copy is stale. Frames of an interrupted pass are in composited.partial and do not count."""
    now = sorted(frames.glob("f.*.png"))
    if not now:
        return False
    foreign = _ledger(raw).foreign(now)
    if foreign is None:                                 # no hash record (older run): only a frame-count change shows
        return len(now) != len(list(raw.glob("f.*.png")))
    return bool(foreign)


def apply(P, name):
    """Post pass over scenes/<name>/: caption box (section "caption") and/or the narrator inset track
    (scenes/<name>_inset/, written by scene.py for "kind": "external" sections with "inset")."""
    A = P.section(name)
    W, H = frame_size(P)
    frames = P.dir / "scenes" / name
    raw = P.dir / "scenes" / f"{name}_raw"
    inset_dir = P.dir / "scenes" / f"{name}_inset"
    use_inset = bool(A.get("inset")) and A.get("kind") == "external" and any(inset_dir.glob("f.*.png"))
    if raw.exists() and _fresh_render(frames, raw):
        print(f"   scenes/{name}/ was re-rendered - replacing the stale scenes/{name}_raw/")
        shutil.rmtree(raw)
    if not raw.exists():
        if not any(frames.glob("f.*.png")):
            raise SystemExit(f"scenes/{name}/ has no frames - render the scene first")
        shutil.move(str(frames), str(raw))              # one rename: the originals are never copied over
    frames.mkdir(exist_ok=True)                         # (also after a kill between the move and the mkdir)
    if A.get("caption"):
        events, fnt, spec = caption_events(P, A)
    else:
        events, fnt, spec = [], font(px(P, 30)), {}
    ink = spec.get("ink", "#2b1d14")
    ghost = float(spec.get("ghost", 0.3))
    boxc = spec.get("box", "#fff3b0")
    rh = int(fnt.size * 1.4)
    n = 0
    derived.Ledger.clean(frames, "f.*.png")             # half-written composites of an interrupted pass
    # a frame only ever appears under its final name AFTER its hash is logged (Ledger.save: temp name that "f.*.png"
    # does not match -> hash logged + fsynced -> rename): a kill at any point leaves no unlogged f.NNNN.png
    with _ledger(raw).session() as led:
        for src in sorted(raw.glob("f.*.png")):
            f = int(src.stem.split(".")[1])
            img = Image.open(src).convert("RGBA")
            for f0, f1, rows, wf, place in events:
                a0, a1 = f0, f1                              # held until the next box: 3-frame cross-fade, no gap
                if not (a0 <= f < a1):
                    continue
                alpha = min(1.0, (f - a0 + 1) / 3, (a1 - f) / 3)
                bw = int(max(fnt.getlength(r) for r in rows)) + px(P, 44)
                bh = rh * len(rows) + px(P, 22)
                m = px(P, 30)
                bx = {"top_left": m, "bottom_left": m, "top": (W - bw) // 2, "top_right": W - bw - m,
                      "bottom_right": W - bw - m}.get(place, m)
                by = H - bh - px(P, 120) if place.startswith("bottom") else px(P, 28)
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                d.rounded_rectangle((bx, by, bx + bw, by + bh), px(P, 6), fill=boxc + "e6", outline=ink,
                                    width=max(1, px(P, 3)))
                gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # ghost words on their own layer (ImageDraw doesn't blend)
                gd = ImageDraw.Draw(gl)
                k = 0
                for ri, row in enumerate(rows):
                    x = bx + px(P, 22)
                    for w in row.split():
                        if wf[k] - 1 <= f:
                            d.text((x, by + px(P, 8) + ri * rh), w, font=fnt, fill=ink)
                        elif ghost > 0:                      # words still to come stand faintly, so the box is never empty
                            gd.text((x, by + px(P, 8) + ri * rh), w, font=fnt, fill=ink + "%02x" % int(255 * ghost))
                        x += fnt.getlength(w + " ")
                        k += 1
                layer.alpha_composite(gl)
                if alpha < 1:
                    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * max(alpha, 0))))
                img.alpha_composite(layer)
            ins = inset_dir / src.name
            if use_inset and ins.exists():
                img.alpha_composite(Image.open(ins).convert("RGBA"))
            out = img.convert("RGB")
            led.save(frames / src.name, lambda tmp: out.save(tmp, format="PNG"))
            n += 1
    print(f"-> scenes/{name}/: {n} frames with {len(events)} caption boxes" + (", narrator inset" if use_inset else "")
          + f" (originals in scenes/{name}_raw/)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("section")
    ap.add_argument("--project", default=".")
    a = ap.parse_args()
    apply(Project(a.project), a.section)


if __name__ == "__main__":
    main()
