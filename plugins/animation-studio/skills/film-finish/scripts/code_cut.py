# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Code cut: a film whose cut is data and whose text and graphics are drawn in code, frame by frame, in headless
Edge/Chrome (the page in code_cut/). Footage (takes as numbered frames, stills) stays untouched underneath.

A work folder holds:
  edit.json    fps, frames, size, worlds, chrome, accents, overlays, shots[] -> parts[] (see references/code-cut.md)
  song.json    t0, fps, frames, beats_k, kick, lines[] with words[] (frames from the film start)
  clips.json   per take: fps, frames, song_start, delay_frames, faces[] (face box per frame, 0..1, or null)
  frames/<take>/0001.jpg ...   stills/...   optional ticker file named in edit.json "ticker"

Usage (uv run code_cut.py ...):
  code_cut.py check  <work>                         validation only (exit code 2 on errors)
  code_cut.py render <work> --song song.wav --out film.mp4 [--from K --to K] [--plate] [--keep-png]
  code_cut.py frames <work> --from K --to K         frames into <work>/png only (preview, no validation)
  code_cut.py sheet  <work> out.jpg K K K ...       contact sheet of rendered frames [--grid: thirds/quarters + frame number]

Masks so that dust and "behind" overlays pass behind people come from ai-video near_masks.py (gpu_python).

Rules checked: shots tile the film; parts tile their shot; every cut sits on a measured beat or a word onset
(edit.json "free_cuts": [k, ...] lists the exceptions); a take covers the song time of its part; every part has a
`why`; files exist; overlay types are known. Notes (no error): text that stands too short to read, "behind" overlays
and dust on takes without masks. `render` never overwrites an existing film and writes <work>/last_render.json (which
file is the current film). A frame range re-renders only those frames and rebuilds the film from all frames on disk.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("toon-2d")
import config  # noqa: E402
from media import ffmpeg  # noqa: E402

HERE = Path(__file__).resolve().parent
PAGE = HERE / "code_cut"
SERVER = _studio.skill_dir("toon-2d") / "scripts" / "multiplane" / "server.mjs"


OVERLAYS = {"title", "shout", "flash", "list", "counter", "board", "typer", "lower", "credits",
            "stamp", "check", "sight", "rings", "cards", "flip", "quote"}
READ_S = {"stamp": 2.0, "quote": 5.0, "title": 1.5, "lower": 2.0}     # shortest time such a text can be read in


def notes(work):
    """-> list of hints that are no errors: unreadably short text, 'behind' pieces without masks."""
    edit, _, clips = load(work)
    fps, out = edit["fps"], []
    for o in edit.get("overlays", []):
        need = READ_S.get(o.get("type"))
        if need and (o["k1"] - o["k0"]) / fps < need:
            out.append(f"{o['type']} at {o['k0']} stands {(o['k1'] - o['k0']) / fps:.1f} s - under {need:g} s nobody reads it "
                       f"(hold it over the cut if the shot is short)")
    behind = [o for o in edit.get("overlays", []) if o.get("behind")]
    for s in edit["shots"]:
        dust = (edit.get("worlds", {}).get(s.get("world"), {}) or {}).get("dust", edit.get("dust"))
        for p in s["parts"]:
            if p["kind"] != "take" or clips.get(p["src"], {}).get("masks"):
                continue
            hit = [o for o in behind if o["k0"] < p["k1"] and o["k1"] > p["k0"]]
            if hit or dust:
                what = " and ".join(x for x in ("dust (left out)" if dust else "",
                                                 f"{len(hit)} 'behind' overlay(s) (drawn in front)" if hit else "") if x)
                out.append(f"{s['id']}: take {p['src']} has no masks - {what}; run ai-video near_masks.py")
    seen = set()
    return [n for n in out if not (n in seen or seen.add(n))]


def load(work):
    work = Path(work)
    edit = json.loads((work / "edit.json").read_text(encoding="utf-8"))
    song = json.loads((work / "song.json").read_text(encoding="utf-8"))
    clips = json.loads((work / "clips.json").read_text(encoding="utf-8")) if (work / "clips.json").exists() else {}
    return edit, song, clips


def validate(work):
    """-> list of error strings (empty = fine)."""
    work = Path(work)
    edit, song, clips = load(work)
    ok = (set(song["beats_k"]) | {w["k0"] for ln in song["lines"] for w in ln["words"]} | {0, edit["frames"]}
          | set(edit.get("free_cuts", [])))
    errs, k = [], 0
    for s in edit["shots"]:
        if s["k0"] != k:
            errs.append(f"{s['id']}: starts at {s['k0']}, expected {k} (gap or overlap)")
        pk = s["k0"]
        for p in s["parts"]:
            if p["k0"] != pk:
                errs.append(f"{s['id']}: part starts at {p['k0']}, expected {pk}")
            if p["k0"] not in ok:
                errs.append(f"{s['id']}: cut at {p['k0']} is neither a beat nor a word onset")
            if p["k1"] <= p["k0"]:
                errs.append(f"{s['id']}: empty part at {p['k0']}")
            if not p.get("why"):
                errs.append(f"{s['id']}: part at {p['k0']} has no why")
            if p["kind"] == "take":
                c = clips.get(p["src"])
                if not c:
                    errs.append(f"{s['id']}: take {p['src']} is not in clips.json")
                else:
                    a = song.get("t0", 0) + p["k0"] / edit["fps"]
                    b = song.get("t0", 0) + p["k1"] / edit["fps"]
                    end = c["song_start"] + c["frames"] / c["fps"]
                    if a < c["song_start"] - 0.2 or (b > end + 0.12 and not p.get("hold")):     # "hold": last frame held on purpose
                        errs.append(f"{s['id']}: {p['src']} does not cover {a:.2f}-{b:.2f} s (has "
                                    f"{c['song_start']:.2f}-{end:.2f})")
                    if not (work / "frames" / p["src"]).is_dir():
                        errs.append(f"{s['id']}: frames/{p['src']} missing")
            elif not (work / p["src"]).exists():
                errs.append(f"{s['id']}: missing {p['src']}")
            pk = p["k1"]
        if pk != s["k1"]:
            errs.append(f"{s['id']}: parts end at {pk}, shot at {s['k1']}")
        k = s["k1"]
    if k != edit["frames"]:
        errs.append(f"shots end at {k}, film has {edit['frames']} frames")
    for o in edit.get("overlays", []):
        if o.get("type") not in OVERLAYS:
            errs.append(f"overlay at {o.get('k0')}: unknown type {o.get('type')!r} (known: {', '.join(sorted(OVERLAYS))})")
    ir = edit.get("iris")
    if ir and not (0 <= ir["k0"] < ir["k1"] <= edit["frames"]):
        errs.append(f"iris {ir['k0']}-{ir['k1']} lies outside the film")
    if edit.get("ticker") and not (work / edit["ticker"]).exists():
        errs.append(f"ticker file {edit['ticker']} missing")
    w, h = edit.get("size", [1280, 720])
    if abs(w / h - 16 / 9) > 0.01:
        errs.append(f"size {w}x{h} is not 16:9 (the layout is designed for 1280x720 and scaled)")
    return errs


def report(work):
    errs = validate(work)
    edit, _, _ = load(work)
    parts = [p for s in edit["shots"] for p in s["parts"]]
    lens = sorted(p["k1"] - p["k0"] for p in parts)
    for e in errs:
        print("EDIT ERROR:", e)
    for n in notes(work):
        print("NOTE:", n)
    print(f"edit.json: {len(edit['shots'])} shots, {len(parts)} parts, median part "
          f"{lens[len(lens) // 2] / edit['fps']:.2f} s, {'OK' if not errs else str(len(errs)) + ' errors'}")
    return not errs


def render_frames(work, k0, k1, plate=False, timeout=3600):
    """Frames k0..k1-1 -> <work>/png/f_00000.png (p_ with plate). True when the page finished without an error."""
    from render_multiplane import find_browser, free_port, kill_tree
    work = Path(work)
    edit, _, _ = load(work)
    out = work / "png"
    out.mkdir(exist_ok=True)
    page = work / "_page"                       # the server serves the work folder: the page is copied next to the data
    shutil.rmtree(page, ignore_errors=True)
    shutil.copytree(PAGE, page)
    node = config.get("node") or shutil.which("node")
    if not node:
        raise SystemExit("node not found - install Node.js or set the config key 'node' (check_tools.py --set node=PATH)")
    port = free_port()
    srv = subprocess.Popen([node, str(SERVER), str(work), str(out), str(port)], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, errors="replace")
    time.sleep(0.8)
    prof = tempfile.mkdtemp(prefix="code_cut_browser_")
    w, h = edit.get("size", [1280, 720])
    url = f"http://127.0.0.1:{port}/_page/index.html?from={k0}&to={k1}" + ("&plate=1" if plate else "")
    br = subprocess.Popen([find_browser(), "--headless=new", f"--user-data-dir={prof}", "--no-first-run",
                           "--disable-extensions", "--force-device-scale-factor=1", f"--window-size={w},{h}", url],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    try:
        log, _ = srv.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        srv.kill()
        log, _ = srv.communicate()
        log = (log or "") + f"\nERROR: timeout after {timeout} s"
    finally:
        kill_tree(br, prof)
        time.sleep(0.5)
        shutil.rmtree(prof, ignore_errors=True)
        shutil.rmtree(page, ignore_errors=True)
    bad = [ln for ln in log.splitlines() if "ERROR" in ln]
    for ln in bad[:10]:
        print(ln)
    print(f"frames {k0}-{k1} in {time.time() - t0:.1f} s")
    return not bad


def build(work, song_wav, out, plate=False):
    work, out = Path(work), Path(out)
    edit, song, _ = load(work)
    if out.exists():
        raise SystemExit(f"{out.name} exists - never overwrite a render, pick the next version name")
    pre = "p_" if plate else "f_"
    n = len(list((work / "png").glob(pre + "*.png")))
    if n != edit["frames"]:
        raise SystemExit(f"{n} frames on disk, the film has {edit['frames']} - render the whole film once first")
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = edit["frames"] / edit["fps"]
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-framerate", str(edit["fps"]), "-i", str(work / "png" / (pre + "%05d.png")),
                    "-ss", f"{song.get('t0', 0):.3f}", "-t", f"{dur:.3f}", "-i", str(song_wav),
                    "-af", f"afade=t=out:st={dur - 0.4:.2f}:d=0.4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                    "-c:a", "aac", "-b:a", "256k", "-shortest", str(out)], check=True)
    # which file is the current film of this work folder - later steps (overlays, versions) read it instead of guessing
    (work / "last_render.json").write_text(json.dumps({"film": str(out.resolve()), "frames": edit["frames"], "plate": plate,
                                                       "at": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1), encoding="utf-8")
    print("->", out)


def sheet(work, out, ks, cols=3, tw=640, grid=False):
    """Contact sheet of rendered frames. grid: quarter / third lines and the frame number on every picture - for
    reading off where an overlay has room (x = column / 4 * 1280, y = row / 3 * 720)."""
    from PIL import Image, ImageDraw
    work = Path(work)
    ims = [Image.open(work / "png" / f"f_{k:05d}.png") for k in ks]
    th = round(tw * ims[0].height / ims[0].width)
    img = Image.new("RGB", (cols * tw, ((len(ims) + cols - 1) // cols) * th))
    for i, im in enumerate(ims):
        im = im.convert("RGB").resize((tw, th))
        if grid:
            d = ImageDraw.Draw(im)
            for x in range(1, 4):
                d.line([x * tw / 4, 0, x * tw / 4, th], fill=(120, 120, 120))
            for y in range(1, 3):
                d.line([0, y * th / 3, tw, y * th / 3], fill=(120, 120, 120))
            d.rectangle([0, 0, 92, 20], fill=(0, 0, 0))
            d.text((5, 4), f"F {ks[i]:05d}", fill=(255, 255, 0))
        img.paste(im, ((i % cols) * tw, (i // cols) * th))
    img.save(out, quality=88)
    print("->", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", choices=["check", "render", "frames", "sheet"])
    ap.add_argument("work")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--song")
    ap.add_argument("--out")
    ap.add_argument("--from", dest="k0", type=int)
    ap.add_argument("--to", dest="k1", type=int)
    ap.add_argument("--plate", action="store_true", help="footage only, no code layer")
    ap.add_argument("--grid", action="store_true", help="sheet: quarter/third lines and frame numbers (placing overlays)")
    ap.add_argument("--keep-png", action="store_true", help=argparse.SUPPRESS)      # frames are always kept (range re-render)
    a = ap.parse_args()
    if a.job == "sheet":
        return sheet(a.work, a.rest[0], [int(k) for k in a.rest[1:]], grid=a.grid)
    if a.job == "frames":
        sys.exit(0 if render_frames(a.work, a.k0 or 0, a.k1 or (a.k0 or 0) + 1) else 1)
    ok = report(a.work)
    if a.job == "check" or not ok:
        sys.exit(0 if ok else 2)
    if not a.song or not a.out:
        raise SystemExit("render needs --song and --out")
    if Path(a.out).exists():
        raise SystemExit(f"{Path(a.out).name} exists - never overwrite a render, pick the next version name")
    edit, _, _ = load(a.work)
    if not render_frames(a.work, a.k0 or 0, a.k1 or edit["frames"], a.plate):
        sys.exit(1)
    build(a.work, a.song, a.out, a.plate)


if __name__ == "__main__":
    main()
