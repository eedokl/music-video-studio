# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Add a portal flight to an analysed song project: the engine in flight/, the song's data, one starter world per part.

  uv run new_flight.py PROJECT [--flight flight] [--no-install]

PROJECT is a song project whose song is analysed (project.json, song.wav, analysis/timing.json + hits.json - made
with lyric-music-video new_video.py --no-install and analyze_song.py). This script
  - copies assets/flight-template to PROJECT/flight/ (an existing flight is kept: only song.js is written again),
  - writes flight/src/song.js (beat grid, every line with its word times, the song cut into parts on bar lines)
    and copies the song to flight/public/,
  - runs `npm install` there (three.js + puppeteer-core) unless --no-install,
  - notes "flight" in project.json.
The flight then already runs through the whole song: every part gets one of three starter worlds (src/plan.js).
Watch it live: `node serve.mjs 5245` in flight/ and open http://localhost:5245/ (or flight.py PROJECT check).
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import flight_data  # noqa: E402
from song_project import Project  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "flight-template"


def npm_install(flight):
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("npm not found - install Node.js 20+ (https://nodejs.org), then run `npm install` in the flight folder")
    subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=flight, check=True)


def main():
    ap = argparse.ArgumentParser(description="Add a portal flight (three.js engine + starter worlds) to a song project.")
    ap.add_argument("project")
    ap.add_argument("--flight", default=None, help="folder inside the project (default: project.json 'flight' or flight)")
    ap.add_argument("--no-install", action="store_true", help="do not run npm install (no network)")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("portal-music-video")
    name = a.flight or P.get("flight", "flight")
    flight = P.dir / name
    if (flight / "src" / "engine.js").exists():
        print(f"{flight} exists - engine and worlds kept, song data written again")
    else:
        shutil.copytree(TEMPLATE, flight, ignore=shutil.ignore_patterns("node_modules", "out"), dirs_exist_ok=True)
    sections, bpm, offset, end = flight_data.write(P, flight)
    if P.get("flight") != name:
        p = json.loads(P.file.read_text(encoding="utf-8"))
        p["flight"] = name
        P.file.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    if not a.no_install and not (flight / "node_modules" / "three").exists():
        npm_install(flight)
    beat = 60.0 / bpm
    print(f"-> {flight}: song {end:.1f} s, {bpm:g} BPM, first bar line at {offset:.3f} s, {len(sections)} parts")
    t = 0.0
    for i, s in enumerate(sections, 1):
        print(f"   {i:2d}  {t:7.2f} s  {s['beats']:6.1f} beats  {len(s['lines']):2d} lines  {s['name']}")
        t += s["beats"] * beat
    print("   every part has a starter world (flight/src/plan.js) - replace them with worlds made for this song")


if __name__ == "__main__":
    main()
