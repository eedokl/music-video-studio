# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run a Python script inside Blender, headless (Blender from the machine config key "blender").

Usage: uv run blender_run.py <script.py> [-- script args]
Same as: blender -b --factory-startup --python <script.py> -- [args]
Example: blender_run.py <toon-2d>/assets/blender_gp_example.py -- --layers layers --out gp --still 40
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    script = str(Path(sys.argv[1]).resolve())
    rest = sys.argv[2:]
    if rest and rest[0] != "--":
        rest = ["--"] + rest
    r = subprocess.run([config.need("blender"), "-b", "--factory-startup", "--python", script] + rest)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
