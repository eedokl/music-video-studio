"""A short classical 2D scene as a small project: brief + creative seed + ideas, scene folder, finished film.

Usage (uv run --no-project --with numpy --with pillow python short.py ...):
  short.py new <folder> --title "Pip and the Flower" [--template blank|example|figure] [--seed 4711]
           [--principles "anticipation,take"] [--figure fips]
      -> <folder>/short.json, _toon.py, make_scene.py (from the toon-2d template), prints the seed
  short.py idea <folder> "Pip hides behind the flower stem" [--by user|ai] [--where beat2]
  short.py variant <folder> <salt> option1 option2 ...      -> picks one option with the creative seed (and logs it)
  short.py finish <folder> [--sif scene.sif] [--cues sfx_cues.json] [--contact 0,24,48] [--jobs 8] [--no-look]
      -> renders the .sif (toon-2d render.py), adds the sound-effect track (sfx_track.py) if cues exist,
         applies the standard look once (film-finish apply_look.py) and writes
         <folder>/final/<name>.mp4, <name>.gif, contact.png (labelled key frames)
short.json: {"title", "seed", "ideas": [...], "principles": [...], "beats": [[f0, f1, "what"], ...], "figure"}
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("toon-2d", "film-finish")
import creative  # noqa: E402

HERE = Path(__file__).resolve().parent
TOON = _studio.skill_dir("toon-2d") / "scripts"
FINISH = _studio.skill_dir("film-finish") / "scripts"


class Short:
    def __init__(self, folder):
        self.dir = Path(folder).resolve()
        self.file = self.dir / "short.json"
        self.p = json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else {}

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self.p, ensure_ascii=False, indent=1), encoding="utf-8")


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd[1:3]), "...", flush=True)
    r = subprocess.run([str(c) for c in cmd], **kw)
    if r.returncode != 0:
        sys.exit(f"step failed: {Path(str(cmd[1])).name}")


def cmd_new(a):
    S = Short(a.folder)
    S.p.setdefault("title", a.title or S.dir.name)
    if a.seed is not None:
        S.p["seed"] = a.seed
    S.p.setdefault("ideas", [])
    if a.principles:
        S.p["principles"] = [x.strip() for x in a.principles.split(",") if x.strip()]
    if a.figure:
        S.p["figure"] = a.figure
    S.save()
    creative.seed(S)
    subprocess.run([sys.executable, str(TOON / "new_scene.py"), str(S.dir), "--from", a.template], check=True)
    print(f"short '{S.p['title']}' seed {S.p['seed']} -> {S.file}")


def cmd_idea(a):
    S = Short(a.folder)
    creative.add_idea(S, a.by, a.text, a.where)
    print(f"{len(S.p['ideas'])} ideas")


def cmd_variant(a):
    S = Short(a.folder)
    choice = creative.pick(S, a.salt, a.options)
    creative.add_idea(S, "ai", f"{a.salt}: {choice} (seed pick from {', '.join(a.options)})", a.salt, "done")
    print(choice)


def cmd_finish(a):
    S = Short(a.folder)
    sif = Path(a.sif) if a.sif else next(iter(sorted(S.dir.glob("*.sif"))), None)
    if sif is None:
        sys.exit("no .sif in the folder - run make_scene.py first")
    sif = (S.dir / sif).resolve() if not sif.is_absolute() else sif
    contact = a.contact or "auto"
    sheet = sif.parent / "contact.png"
    sheet.unlink(missing_ok=True)                    # never ship a contact sheet of an earlier render
    run([sys.executable, TOON / "render.py", sif, "--contact", contact, "--jobs", str(a.jobs)])
    video = sif.with_suffix(".mp4")
    cues = Path(a.cues) if a.cues else (S.dir / "sfx_cues.json")
    if cues.exists():
        run([sys.executable, HERE / "sfx_track.py", cues, "--video", video, "--out", S.dir / "sfx.wav"])
        video = video.with_name(video.stem + "_sfx.mp4")
    final = S.dir / "final"
    final.mkdir(exist_ok=True)
    name = sif.stem
    out = final / f"{name}.mp4"
    if a.no_look:
        shutil.copy(video, out)
    else:
        run([sys.executable, FINISH / "apply_look.py", video, "-o", out])
    ff = __import__("config").need("ffmpeg")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(out), "-vf",
                    "fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse",
                    str(final / f"{name}.gif")], check=True)
    if sheet.exists():
        shutil.copy(sheet, final / "contact.png")
    else:
        (final / "contact.png").unlink(missing_ok=True)
    S.p["final"] = str(out.relative_to(S.dir))
    S.save()
    print("final:", out, "| gif:", final / f"{name}.gif",
          "| contact:", final / "contact.png" if sheet.exists() else f"none (--contact {contact})")


def main():
    ap = argparse.ArgumentParser(description="Short 2D scene project: brief, seed, ideas, finish.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("folder")
    n.add_argument("--title")
    n.add_argument("--template", default="blank", choices=["blank", "example", "figure", "none"])
    n.add_argument("--seed", type=int)
    n.add_argument("--principles")
    n.add_argument("--figure")
    i = sub.add_parser("idea")
    i.add_argument("folder")
    i.add_argument("text")
    i.add_argument("--by", default="ai", choices=["ai", "user"])
    i.add_argument("--where", default="")
    v = sub.add_parser("variant")
    v.add_argument("folder")
    v.add_argument("salt")
    v.add_argument("options", nargs="+")
    f = sub.add_parser("finish")
    f.add_argument("folder")
    f.add_argument("--sif")
    f.add_argument("--cues")
    f.add_argument("--contact")
    f.add_argument("--jobs", type=int, default=1)
    f.add_argument("--no-look", action="store_true")
    a = ap.parse_args()
    {"new": cmd_new, "idea": cmd_idea, "variant": cmd_variant, "finish": cmd_finish}[a.cmd](a)


if __name__ == "__main__":
    main()
