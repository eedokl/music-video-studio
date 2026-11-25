# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Cut the film with film-finish: lyrics overlay per shot (overlays.py), the whole film on the song (build.py film:
film.mp4, film_small.mp4 < 30 MB, film_mail.mp4, 0 decode errors), then review sheets:
  film_sheet.png        3x3 frames over the film (media.contact_sheet)
  film_shots.jpg        one row per shot at 20/50/80 % (ai-video sheets.shot_sheet) - for the canon check by eye
  review.json           shot list with technique, material, lip numbers - hand it to the video-review skill
  --version [N]         also keep this cut as film_vN.mp4 / _small / _mail, film_vN_sheet.png, selection_vN.json
                        (no N = the next free number) - film.mp4 is always the latest cut and is overwritten
Usage: uv run make_film.py [<project>]
         [--no-lyrics] [--version [N]]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video", "film-finish")
import claudia  # noqa: E402
import media  # noqa: E402
import sheets  # noqa: E402
from song_project import Project  # noqa: E402

FF = _studio.skill_dir("film-finish") / "scripts"


def next_version(d):
    nums = [int(m.group(1)) for f in d.glob("film_v*.mp4") if (m := re.fullmatch(r"film_v(\d+)\.mp4", f.name))]
    return max(nums, default=0) + 1


def keep_version(P, v):
    """film.mp4 & co. -> film_v<v>.* (maschine_dance / Hymne, 2026-11-25: every version was copied by hand)."""
    d, out = P.dir, []
    pairs = [("film.mp4", f"film_v{v}.mp4"), ("film_small.mp4", f"film_v{v}_small.mp4"),
             ("film_mail.mp4", f"film_v{v}_mail.mp4"), ("film_sheet.png", f"film_v{v}_sheet.png"),
             ("film_shots.jpg", f"film_v{v}_shots.jpg"), ("selection.json", f"selection_v{v}.json")]
    for src, dst in pairs:
        if (d / src).exists():
            shutil.copy2(d / src, d / dst)
            out.append(dst)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--no-lyrics", action="store_true")
    ap.add_argument("--version", nargs="?", const="next", help="keep this cut as film_v<N>.* (no N: the next number)")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("claudia-music-video")                 # project.json validated before any long step
    version = None
    if a.version:
        if a.version != "next" and not a.version.isdigit():
            raise SystemExit(f"--version: a number or nothing, not {a.version!r}")
        version = next_version(P.dir) if a.version == "next" else int(a.version)
        if (P.dir / f"film_v{version}.mp4").exists() and a.version != "next":
            raise SystemExit(f"film_v{version}.mp4 exists - another number, or --version alone for the next free one")
    if "lyrics_style" not in P.p:                         # Claudia look: caps with the clay highlight #D97757
        P.p["lyrics_style"] = "caps"
        P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in P.sections():
        ov = P.dir / "overlays" / f"{s['name']}.mov"
        if s.get("lyrics") and not a.no_lyrics:
            subprocess.run([sys.executable, str(FF / "overlays.py"), s["name"], "--project", str(P.dir)], check=True)
        elif ov.exists():
            ov.unlink()
    subprocess.run([sys.executable, str(FF / "build.py"), "film", "--project", str(P.dir)], check=True)
    film = P.dir / "film.mp4"
    media.contact_sheet(film, P.dir / "film_sheet.png")
    t0 = min(s["from"] for s in P.sections())
    sheets.shot_sheet(film, [(s["from"], s["to"], f"{s['name']} {s['technique']}") for s in P.sections()],
                      P.dir / "film_shots.jpg", offset=t0)
    sel = json.loads((P.dir / "selection.json").read_text(encoding="utf-8")) if (P.dir / "selection.json").exists() else {}
    review = {"film": "film.mp4", "shots": [dict(name=s["name"], start=s["from"], end=s["to"], technique=s["technique"],
                                                 line=s.get("line"), material=(sel.get("clip") or {}).get(s["name"]))
                                            for s in P.sections()]}
    (P.dir / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    fin = dict(claudia.FINISH, **(P.get("finish") or {}))
    print(claudia.finish_line(fin) + "  (applied to the frames by render_shots.py; the film-finish \"look\" stays none)")
    print("-> film.mp4, film_sheet.png, film_shots.jpg, review.json")
    if version is not None:
        print(f"-> version {version}: " + ", ".join(keep_version(P, version)))


if __name__ == "__main__":
    main()
