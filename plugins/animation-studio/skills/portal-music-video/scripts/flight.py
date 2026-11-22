# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Check and render a portal flight (PROJECT/flight, made by new_flight.py).

  uv run flight.py PROJECT data                      song.js again after the timing or the lyrics changed
  uv run flight.py PROJECT check [--cpu]             every portal crossing measured, slow frames counted, page errors,
                                                     one picture per world -> flight/out/check/ + out/flight_check.jpg
  uv run flight.py PROJECT clip --from 60 --to 70    a piece as MP4 -> out/clip_60-70.mp4
  uv run flight.py PROJECT final --title "Song"      the whole film -> out/<title>.mp4 + _small (< 29 MB) + _mail (~12 MB)
  options for clip / final: --cpu  --fps 30  --size 1920x1080  --crf 18  --workers 4  --replace

--cpu draws with the browser's software renderer and encodes with x264: nothing touches the graphics card (for when it
is busy with an AI job). Reference: 4:32 min at 1080p30 took 31 min on 20 cores with 5 browsers; with the card it is
several times faster. The render is cut into segments that survive an interruption; they are thrown away by
themselves when a source file of the flight changed (content hash, not file dates).
A finished film is never replaced: when out/<title>.mp4 exists the new one is "<title> v2" (--replace overwrites).
The browser: config "chrome" or "browser" (check_tools.py --setup / --set chrome=PATH), env ANIMATION_STUDIO_CHROME.
Exit codes: 0 ok, 1 the check found a seam or a page error / the render failed, 2 project.json wrong, 3 the page did
not load (the message names the error - usually a typo in a world).
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "film-finish")
import config  # noqa: E402
import derived  # noqa: E402
import flight_data  # noqa: E402
from media import check_video, duration, ffmpeg, has_audio  # noqa: E402
from song_project import Project  # noqa: E402

ENCODE = _studio.skill_dir("film-finish") / "scripts" / "encode.py"


def tool(name):
    return config.get(name) or shutil.which(name) or shutil.which(name + ".cmd") or name


def flight_dir(P):
    d = P.dir / P.get("flight", "flight")
    if not (d / "src" / "engine.js").exists():
        raise SystemExit(f"{d} has no flight - run new_flight.py PROJECT first")
    if not (d / "node_modules" / "three").exists():
        print("node_modules missing - npm install")
        subprocess.run([shutil.which("npm") or shutil.which("npm.cmd") or "npm", "install", "--no-audit", "--no-fund"], cwd=d, check=True)
    return d


def node(d, script, *args, capture=False):
    browser = config.get("chrome") or config.get("browser")
    cmd = [tool("node"), script, *map(str, args), "--ffmpeg", ffmpeg()]
    if browser:
        cmd += ["--browser", browser]
    return subprocess.run(cmd, cwd=d, capture_output=capture, text=True, encoding="utf-8", errors="replace")


def sources(d):
    return [d / "src", d / "index.html", d / "public" / "song.wav"]


def check(P, a):
    d = flight_dir(P)
    r = node(d, "check.mjs", *(["--cpu"] if a.cpu else []), capture=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(r.returncode or 1)
    rep = json.loads(r.stdout.strip().splitlines()[-1])
    print(f"renderer: {rep['renderer']}   film {rep['total']:.2f} s, {len(rep['worlds'])} worlds")
    print("   world                 start    length   picture change before | across | after the portal")
    seams = []
    for w in rep["worlds"]:
        mark = "  (the film ends here)" if w["last"] else "  <- SEAM: the crossing stands out" if w["seam"] else ""
        print(f"   {w['id']:20s} {w['start']:7.2f} s {w['seconds']:6.2f} s   {w['before']:5.1f} | {w['across']:5.1f} | {w['after']:5.1f}{mark}")
        if w["seam"]:
            seams.append(w["id"])
    f = rep["frames"]
    if f is None:
        print("   frames: not timed on the software renderer (run check without --cpu when the graphics card is free)")
    else:
        slow = f["slow"]
        print(f"   frames: {f['count']} drawn, mean {f['meanMs']} ms, slowest {f['maxMs']} ms, {len(slow)} over 14 ms"
              + (f" (first: {', '.join(f'{t} s {w} {ms} ms' for t, w, ms in slow[:6])})" if slow else ""))
    for e in rep["pageErrors"]:
        print(f"   PAGE ERROR: {e}")
    # one sheet of the pictures (a row per four worlds)
    pics = [d / "out" / "check" / w["picture"] for w in rep["worlds"]]
    cols = min(4, len(pics))
    rows = -(-len(pics) // cols)
    out = P.dir / "out" / "flight_check.jpg"
    out.parent.mkdir(exist_ok=True)
    ins = [x for p in pics for x in ("-i", str(p))]
    scaled = "".join(f"[{i}:v]scale=480:270[s{i}];" for i in range(len(pics)))
    tiles = "".join(f"[s{i}]" for i in range(len(pics)))
    layout = "|".join(f"{(i % cols) * 480}_{(i // cols) * 270}" for i in range(len(pics)))
    graph = f"{scaled}{tiles}xstack=inputs={len(pics)}:layout={layout}:fill=black[o]" if len(pics) > 1 else "[0:v]scale=480:270[o]"
    subprocess.run([ffmpeg(), "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[o]", "-frames:v", "1", str(out)], check=True)
    print(f"   one picture per world, in order ({cols} x {rows}): {out}")
    if seams or rep["pageErrors"]:
        raise SystemExit(1)


def render(P, a, out_name, piece=None):
    d = flight_dir(P)
    w, h = (int(x) for x in a.size.lower().split("x"))
    seg = d / "out" / "segments" / f"{w}x{h}_{a.fps:g}"
    marker = seg / "source.ok"
    spec = {"size": [w, h], "fps": a.fps, "crf": a.crf}
    fresh = marker.exists() and derived.fresh(marker, inputs=sources(d), spec=spec)
    args = ["--width", w, "--height", h, "--fps", f"{a.fps:g}", "--crf", a.crf, "--workers", a.workers, "--out", out_name]
    if piece:
        args += ["--from", piece[0], "--to", piece[1]]
    if a.cpu:
        args.append("--cpu")
    if not fresh:
        args.append("--fresh")
    r = node(d, "render.mjs", *args)
    if r.returncode not in (0, 4):
        raise SystemExit(r.returncode or 1)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("segments rendered from these sources\n", encoding="utf-8")
    derived.record(marker, inputs=sources(d), spec=spec)
    return d / "out" / out_name, r.returncode == 4


def checked(f, want):
    err = check_video(f)
    dur = duration(f)
    ok = not err and has_audio(f) and abs(dur - want) < 0.5
    print(f"   {f.name}: {f.stat().st_size / 1e6:.1f} MB, {dur:.2f} s" + ("" if ok else f"  <- CHECK: decode errors {err[:120]!r}, audio {has_audio(f)}, expected {want:.2f} s"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="Check and render a portal flight.")
    ap.add_argument("project")
    ap.add_argument("what", choices=["data", "check", "clip", "final"])
    ap.add_argument("--cpu", action="store_true", help="software renderer + x264: the graphics card stays free")
    ap.add_argument("--from", dest="t0", type=float)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--workers", type=int, default=4, help="browsers rendering side by side")
    ap.add_argument("--title", help="file name of the film (final)")
    ap.add_argument("--replace", action="store_true", help="overwrite a finished film of the same title")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("portal-music-video")
    out = P.dir / "out"
    if a.what == "data":
        sections, bpm, offset, end = flight_data.write(P, flight_dir(P))
        print(f"song.js written: {end:.1f} s, {bpm:g} BPM, {len(sections)} parts - check that src/plan.js still fits "
              f"(the starter plan follows SECTIONS by itself)")
    elif a.what == "check":
        check(P, a)
    elif a.what == "clip":
        if a.t0 is None or a.t1 is None:
            raise SystemExit("clip needs --from and --to (song seconds)")
        name = f"clip_{a.t0:g}-{a.t1:g}.mp4"
        f, page_errors = render(P, a, name, (a.t0, a.t1))
        out.mkdir(exist_ok=True)
        shutil.copyfile(f, out / name)
        ok = checked(out / name, a.t1 - a.t0)
        raise SystemExit(0 if ok and not page_errors else 1)
    else:
        title = a.title or P.get("name") or "flight"
        out.mkdir(exist_ok=True)
        final = out / f"{title}.mp4"
        n = 2
        while final.exists() and not a.replace:
            final = out / f"{title} v{n}.mp4"
            n += 1
        if final.name != f"{title}.mp4":
            print(f"out/{title}.mp4 exists - the new film is {final.name} (--replace overwrites)")
        f, page_errors = render(P, a, "flight.mp4")
        shutil.copyfile(f, final)
        want = duration(P.song)
        ok = checked(final, want)
        subprocess.run([*config.script_cmd(ENCODE), str(final)], check=True)
        for suffix in ("_small", "_mail"):
            v = final.with_name(final.stem + suffix + ".mp4")
            ok = (v.exists() and checked(v, want)) and ok
        raise SystemExit(0 if ok and not page_errors else 1)


if __name__ == "__main__":
    main()
