"""Run a Blender script of this skill headless, with the shared GPU lock (EEVEE/Cycles use the graphics card).

  python blender_run.py brickfilm.py -- <plan.json> --render
  python blender_run.py --check            Blender + LDraw library found? (prints versions and paths)
Blender comes from the config key `blender`, the LDraw library from `ldraw_dir` (see references/ldraw-setup.md).
The lock is taken as job "bricks_blender" (model "blender") and released when Blender ends; other jobs wait.
"""
import os
import subprocess
import sys
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

HERE = Path(__file__).resolve().parent


def check():
    b = config.need("blender")
    lib = config.get("ldraw_dir")
    ok = bool(lib) and (Path(lib) / "LDConfig.ldr").exists() and (Path(lib) / "parts").is_dir()
    v = subprocess.run([b, "-b", "--version"], capture_output=True, text=True, errors="replace").stdout.splitlines()
    print(f"blender    {b}  ({v[0] if v else '?'})")
    print(f"ldraw_dir  {lib or '-'}  {'ok' if ok else 'MISSING - see bricks-3d/references/ldraw-setup.md'}")
    return ok


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--check":
        return 0 if check() else 1
    script = Path(argv[0])
    if not script.is_absolute():
        script = HERE / script
    rest = argv[1:]
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not config.get("ldraw_dir"):
        raise SystemExit("config key ldraw_dir is not set (folder of the LDraw parts library) - "
                         "see bricks-3d/references/ldraw-setup.md")
    from gpu_lock import acquire
    acquire("bricks_blender", model="blender")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    r = subprocess.run([config.need("blender"), "-b", "--factory-startup", "--python-exit-code", "1",
                        "--python", str(script), "--", *rest], env=env)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
