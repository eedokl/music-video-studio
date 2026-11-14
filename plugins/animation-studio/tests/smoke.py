"""Smoke test of the animation-studio plugin - cheap, no renders, no GPU, no network.

    python tests/smoke.py              # static checks + `--help` of every CLI that imports with this interpreter
    uv run --no-project --with numpy --with pillow --with svgelements python tests/smoke.py   # more CLIs import

Checks:
  1. every script compiles
  2. all skills/*/scripts/_studio.py are byte-identical (change studio-core's copy, then copy it everywhere)
  3. module names that exist in more than one skill are only the known ones (KNOWN_DUPLICATES); a new duplicate
     fails - rename it (the skill's own folder wins on sys.path, but a sibling's module of the same name is shadowed)
  4. no absolute machine paths (drive letters, user folders) in shipped text files
  5. ${CLAUDE_PLUGIN_ROOT} only in SKILL.md files (Claude Code substitutes it nowhere else)
  6. every `--flag` that a SKILL.md shows right after a script name exists in that script
  7. `python <script> --help` exits 0 for every CLI with argparse; a missing third-party module is reported as
     "skipped", not as a failure
Exit code 1 when a check fails.
"""
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
# files where ${CLAUDE_PLUGIN_ROOT} is a placeholder that a script expands itself (not Claude Code)
PLUGIN_ROOT_OK = {"skills/ai-video/references/night-run.md"}   # jobs.json hooks, expanded by night_run.py
KNOWN_DUPLICATES = {"mouth", "scene", "figures", "blender_run", "sets", "plan", "render"}
TEXT = {".py", ".md", ".json", ".ts", ".mjs", ".js", ".html", ".css", ".txt", ".toml", ".yaml", ".yml"}
fails, notes = [], []


def fail(msg):
    fails.append(msg)


scripts = sorted(p for p in SKILLS.rglob("*.py") if "node_modules" not in p.parts)

# 1 compile
import tempfile
_pyc = Path(tempfile.gettempdir()) / "animation_studio_smoke.pyc"
for p in scripts:
    try:
        py_compile.compile(str(p), doraise=True, cfile=str(_pyc))
    except py_compile.PyCompileError as e:
        fail(f"compile: {p.relative_to(ROOT)}: {e.msg.strip()[:200]}")
_pyc.unlink(missing_ok=True)

# 2 identical _studio.py
copies = {p: p.read_bytes() for p in SKILLS.glob("*/scripts/_studio.py")}
ref = (SKILLS / "studio-core" / "scripts" / "_studio.py").read_bytes()
for p, b in copies.items():
    if b.replace(b"\r\n", b"\n") != ref.replace(b"\r\n", b"\n"):
        fail(f"_studio.py differs from studio-core's copy: {p.relative_to(ROOT)}")

# 3 module name collisions
owners = {}
for p in SKILLS.glob("*/scripts/*.py"):
    if p.name != "_studio.py":
        owners.setdefault(p.stem, []).append(p.parent.parent.name)
for m, sk in owners.items():
    if len(sk) > 1 and m not in KNOWN_DUPLICATES:
        fail(f"module name '{m}.py' exists in several skills: {sk} - rename one")

# 4 absolute paths  /  5 ${CLAUDE_PLUGIN_ROOT} outside SKILL.md
# a real machine's path: a named user folder or this studio's project drive layout - placeholders in docs such as
# "D:/tools/ldraw", "C:\path\to\chrome.exe" or "C:/Users/<you>" are fine
abs_re = re.compile(r"\b[A-Za-z]:[\\/](?:Users[\\/](?!<|you\b|name\b)\w|animation[\\/]|Blender Foundation|Programs[\\/])", re.I)
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in TEXT or "node_modules" in p.parts or p.name == "smoke.py":
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    for m in abs_re.finditer(t):
        line = t[:m.start()].count("\n") + 1
        fail(f"absolute path in {p.relative_to(ROOT)}:{line}: {t[m.start():m.start() + 40].splitlines()[0]}")
        break
    if "${CLAUDE_PLUGIN_ROOT}" in t and p.name not in ("SKILL.md", "CONVENTIONS.md") and p.suffix == ".md" \
            and p.relative_to(ROOT).as_posix() not in PLUGIN_ROOT_OK:
        fail(f"${{CLAUDE_PLUGIN_ROOT}} is not substituted outside SKILL.md: {p.relative_to(ROOT)}")

# 6 SKILL.md flags vs. argparse
by_name = {}
for p in scripts:
    by_name.setdefault(p.name, []).append(p)
for md in SKILLS.glob("*/SKILL.md"):
    for line in md.read_text(encoding="utf-8").splitlines():
        for m in re.finditer(r"([\w-]+\.py)\b([^`|]*)", line):
            name, rest = m.group(1), m.group(2)
            cands = [p for p in by_name.get(name, []) if md.parent.name in p.parts] or by_name.get(name, [])
            if not cands:
                continue
            src = "\n".join(c.read_text(encoding="utf-8", errors="replace") for c in cands)
            rest = re.split(r"[\w-]+\.py", rest)[0]
            for flag in re.findall(r"(?<![\w-])(--[a-z][\w-]*)", rest):
                if flag in ("--with", "--no-project", "--help"):
                    continue
                if f'"{flag}"' not in src and f"'{flag}'" not in src and flag not in src:
                    fail(f"{md.parent.name}/SKILL.md shows `{name} {flag}` but {name} has no {flag}")

# 7 --help
skipped = 0
for p in scripts:
    t = p.read_text(encoding="utf-8", errors="replace")
    if "argparse" not in t or "__main__" not in t or p.parent.name in ("assets", "templates", "recipes"):
        continue
    try:
        r = subprocess.run([sys.executable, str(p), "--help"], capture_output=True, text=True, timeout=60,
                           cwd=str(p.parent), errors="replace")
    except subprocess.TimeoutExpired:
        fail(f"--help timed out: {p.relative_to(ROOT)}")
        continue
    if r.returncode != 0:
        err = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
        if "ModuleNotFoundError" in (r.stderr or "") and not re.search(r"No module named '(_studio|config|media)'", r.stderr):
            skipped += 1
            notes.append(f"skipped (missing package): {p.relative_to(ROOT)}: {err[0][:120]}")
        else:
            fail(f"--help failed: {p.relative_to(ROOT)}: {err[0][:200]}")

for n in notes:
    print("  " + n)
print(f"{len(scripts)} scripts, {len(copies)} _studio.py copies, {skipped} CLIs skipped for missing packages")
if fails:
    print(f"\n{len(fails)} problem(s):")
    for f in fails:
        print("  FAIL " + f)
    sys.exit(1)
print("OK")
