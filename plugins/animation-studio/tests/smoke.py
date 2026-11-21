"""Smoke test of the animation-studio plugin - cheap, no renders, no GPU, no network.

    python tests/smoke.py              # static checks + `--help` of every CLI that imports with this interpreter

Checks:
  1. every script compiles
  2. all skills/*/scripts/_studio.py are byte-identical (change studio-core's copy, then copy it everywhere)
  3. module names that exist in more than one skill are only the known ones (KNOWN_DUPLICATES); a new duplicate
     fails - rename it (the skill's own folder wins on sys.path, but a sibling's module of the same name is shadowed)
  4. no absolute machine paths (drive letters, user folders) in shipped text files
  5. ${CLAUDE_PLUGIN_ROOT} only in SKILL.md files (Claude Code substitutes it nowhere else); no "<plugin>/"
     commands in SKILL.md bodies
  6. every `--flag` that a SKILL.md shows right after a script name exists in that script
  7. `python <script> --help` exits 0 for every CLI with argparse; a missing third-party module is reported as
     "skipped", not as a failure
  8. every script that a doc runs with `uv run` (and every script that has one) carries a PEP 723 block with exact
     `==` pins, and its declared dependencies cover every third-party top-level import of the script and of the
     plugin modules it imports (`_studio.use(...)` siblings, transitively); imports inside try/except ImportError
     and the host modules of Blender / Krita are not counted
Exit code 1 when a check fails.
"""
import ast
import py_compile
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
# files where ${CLAUDE_PLUGIN_ROOT} is a placeholder that a script expands itself (not Claude Code)
PLUGIN_ROOT_OK = {"skills/ai-video/references/night-run.md"}   # jobs.json hooks, expanded by night_run.py
# plugin modules imported only to call a launcher that starts their own interpreter (gpu_python / uv) - their
# third-party imports never run in the importing process, so they are not followed for the PEP 723 check
SUBPROCESS_ONLY = {"estimate_depth", "near_masks"}  # night_run.py / code_film.py -> their run() starts gpu_python
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
    cc = re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", t)   # e.g. a backspace where "\b" was meant (an escaped heredoc)
    if cc:
        fail(f"control character {hex(ord(cc.group()))} in {p.relative_to(ROOT)}:{t[:cc.start()].count(chr(10)) + 1}")
    for m in abs_re.finditer(t):
        line = t[:m.start()].count("\n") + 1
        fail(f"absolute path in {p.relative_to(ROOT)}:{line}: {t[m.start():m.start() + 40].splitlines()[0]}")
        break
    if "${CLAUDE_PLUGIN_ROOT}" in t and p.name not in ("SKILL.md", "CONVENTIONS.md") and p.suffix == ".md" \
            and p.relative_to(ROOT).as_posix() not in PLUGIN_ROOT_OK:
        fail(f"${{CLAUDE_PLUGIN_ROOT}} is not substituted outside SKILL.md: {p.relative_to(ROOT)}")
    if p.name == "SKILL.md" and '"<plugin>/' in t:     # the <plugin> legend is for BLOCK.md / references only
        line = t[:t.index('"<plugin>/')].count("\n") + 1
        fail(f"{p.relative_to(ROOT)}:{line}: a command with <plugin>/ in a SKILL.md - write ${{CLAUDE_PLUGIN_ROOT}}/ "
             "(Claude Code substitutes it there)")

# 6 SKILL.md flags vs. argparse
by_name = {}
for p in scripts:
    by_name.setdefault(p.name, []).append(p)
for md in sorted(SKILLS.glob("*/SKILL.md")) + sorted(SKILLS.glob("*/BLOCK.md")):
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
                    fail(f"{md.parent.name}/{md.name} shows `{name} {flag}` but {name} has no {flag}")

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

# 8 PEP 723 headers of the scripts run with `uv run`
STDLIB = set(sys.stdlib_module_names) | {"__future__"}
HOST_MODULES = {"bpy", "bmesh", "mathutils", "krita"}           # Blender / Krita provide these
DIST = {"PIL": "pillow", "cv2": "opencv-python-headless", "skimage": "scikit-image", "fitz": "pymupdf",
        "pptx": "python-pptx", "faster_whisper": "faster-whisper", "ctranslate2": "faster-whisper"}
PEP723 = re.compile(r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$")


def norm_dist(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def pep723(text):
    """dependencies of the `script` block, or None without one"""
    for m in PEP723.finditer(text):
        if m.group("type") == "script":
            body = "".join(line[2:] if line.startswith("# ") else line[1:]
                           for line in m.group("content").splitlines(keepends=True))
            return tomllib.loads(body)
    return None


def import_scan(p):
    """(top-level third-party candidates, every imported module name, _studio.use skills) of one file"""
    tree = ast.parse(p.read_text(encoding="utf-8"), str(p))
    top, every, uses = set(), set(), []

    def names(node):
        if isinstance(node, ast.Import):
            return [a.name.split(".")[0] for a in node.names]
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            return [node.module.split(".")[0]]
        return []

    def walk(nodes, optional):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                walk(node.body, optional)                 # lazy imports inside functions count too
                continue
            if isinstance(node, ast.Try):
                guarded = any(h.type is None or re.search(r"ImportError|ModuleNotFoundError|Exception",
                                                           ast.unparse(h.type)) for h in node.handlers)
                walk(node.body, optional or guarded)
                for h in node.handlers:
                    walk(h.body, optional)
                walk(node.orelse + node.finalbody, optional)
                continue
            if not optional:
                top.update(names(node))
            for field in ("body", "orelse"):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.With)) and hasattr(node, field):
                    walk(getattr(node, field), optional)

    walk(tree.body, False)
    for node in ast.walk(tree):
        every.update(names(node))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "use" \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "_studio":
            uses += [a.value for a in node.args if isinstance(a, ast.Constant)]
    if "_toon" in every:                                  # scene folders: the shim adds toon-2d + characters
        uses += ["toon-2d", "characters"]
    return top, every, uses


def plugin_module(name, own, uses):
    """the plugin file a module name resolves to (own scripts/ first, then studio-core and the use()d skills)"""
    for d in [own] + [SKILLS / s / "scripts" for s in ("studio-core", *uses)]:
        if (d / f"{name}.py").exists():
            return d / f"{name}.py"
    return next(iter(sorted(SKILLS.glob(f"*/scripts/{name}.py"))), None)


def needed(p):
    """third-party top-level imports of a script and of every plugin module it reaches -> {dist: first file}"""
    own = p.parent
    if own.name == "recipes":
        own = own.parent / "scripts"
    elif own.name in ("assets", "templates"):
        own = SKILLS / "toon-2d" / "scripts"
    out, seen, todo = {}, set(), [(p, own, ())]
    while todo:
        f, d, ctx = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        top, every, uses = import_scan(f)
        uses = list(ctx) + uses
        for m in every - STDLIB - HOST_MODULES - {"_studio", "_toon"}:
            hit = plugin_module(m, d, uses)
            if hit is not None:
                if hit.stem not in SUBPROCESS_ONLY:       # its imports never run in this process
                    todo.append((hit, hit.parent, tuple(uses)))
            elif m in top:
                out.setdefault(norm_dist(DIST.get(m, m)), f.relative_to(ROOT).as_posix())
    return out


uv_docs = set()
for md in ROOT.rglob("*.md"):
    skill = md.relative_to(ROOT).parts[1] if md.relative_to(ROOT).parts[0] == "skills" else None
    for m in re.finditer(r"uv run\s+(?:--offline\s+)?\"?([^\s\"`]*?)([\w-]+\.py)\b", md.read_text(encoding="utf-8")):
        path, name = m.group(1), m.group(2)
        cands = by_name.get(name, [])
        pick = [c for c in cands if f"/{c.parts[-3]}/" in "/" + path] or \
               [c for c in cands if skill and skill in c.parts] or cands
        uv_docs.update(pick)
    # generic form `uv run ".../skills/<skill>/scripts/<script>.py"` = every CLI of that folder
    for m in re.finditer(r"uv run\s+\"?[^\s\"`]*?skills/([\w-]+)/(scripts|recipes)/<\w+>\.py", md.read_text(encoding="utf-8")):
        for c in (SKILLS / m.group(1) / m.group(2)).glob("*.py"):
            if "__main__" in c.read_text(encoding="utf-8") or m.group(2) == "recipes":
                uv_docs.add(c)
headered = {p for p in scripts if "# /// script" in p.read_text(encoding="utf-8")}
checked, cutoffs = 0, {}
for p in sorted(uv_docs | headered):
    rel = p.relative_to(ROOT).as_posix()
    first = p.read_text(encoding="utf-8").split("\n", 1)[0]
    if p not in headered and first.startswith("# Runs ") and "no PEP 723 header" in first.replace("uv / ", ""):
        continue                                          # runs in another interpreter (gpu_python, Blender, ...)
    try:
        meta = pep723(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        fail(f"PEP 723 block does not parse: {rel}: {e}")
        continue
    if meta is None:
        fail(f"a doc runs `uv run {p.name}` but {rel} has no PEP 723 block (# /// script ... # ///)")
        continue
    checked += 1
    declared = {}
    for dep in meta.get("dependencies", []):
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)", dep)
        declared[norm_dist(m.group(1))] = m.group(3)
        if not m.group(3).startswith("=="):
            fail(f"{rel}: dependency '{dep}' is not pinned with ==")
    if "requires-python" not in meta:
        fail(f"{rel}: PEP 723 block without requires-python")
    cutoff = meta.get("tool", {}).get("uv", {}).get("exclude-newer")   # pins the transitive dependencies too
    if not cutoff:
        fail(f"{rel}: PEP 723 block without [tool.uv] exclude-newer (one date for all scripts)")
    else:
        cutoffs.setdefault(cutoff, rel)
    for dist, where in sorted(needed(p).items()):
        if dist not in declared:
            fail(f"{rel}: imports {dist} (in {where}) but its PEP 723 dependencies do not declare it")

if len(cutoffs) > 1:
    fail(f"PEP 723 exclude-newer differs between scripts: {cutoffs} - use one date (move all when re-pinning)")

# 9 a script that starts another plugin script with sys.executable (same environment, no uv start-up) must declare
#   everything the callee needs - the same drift config.script_cmd() exists for (build.py -> credits.py lacked
#   svgelements). Calls through config.script_cmd / uv run resolve the callee's own header and are not checked.
def declared_of(p):
    try:
        meta = pep723(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    if meta is None:
        return None
    return {norm_dist(re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", d).group(1)) for d in meta.get("dependencies", [])}


calls = 0
for p in scripts:
    src = p.read_text(encoding="utf-8")
    if "sys.executable" not in src:
        continue
    tree = ast.parse(src, str(p))
    _, _, uses = import_scan(p)
    caller_deps = declared_of(p)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], (ast.List, ast.BinOp))):
            continue
        text = ast.unparse(node.args[0])
        if "sys.executable" not in text:
            continue
        for name in re.findall(r"['\"]([\w-]+)\.py['\"]", text)[:1]:   # the script sys.executable runs (later .py are its args)
            callee = plugin_module(name, p.parent if p.parent.name == "scripts" else SKILLS / "toon-2d" / "scripts", uses)
            if callee is None or callee == p:
                continue
            calls += 1
            if caller_deps is None:
                continue                                  # caller runs in another interpreter (documented in its line 1)
            missing = sorted(set(needed(callee)) - caller_deps)
            if missing:
                fail(f"{p.relative_to(ROOT).as_posix()} starts {callee.name} with sys.executable, but its PEP 723 "
                     f"header lacks {missing} that {callee.name} needs - declare them or use config.script_cmd()")

# 10 building blocks are BLOCK.md (not skills), user skills point to every block
BLOCK_NAMES = sorted(p.parent.name for p in SKILLS.glob("*/BLOCK.md"))
for d in SKILLS.iterdir():
    if d.is_dir() and not d.name.startswith(".") and (d / "SKILL.md").exists() == (d / "BLOCK.md").exists():
        fail(f"skills/{d.name}: needs exactly one of SKILL.md (user skill) or BLOCK.md (building block)")
for md in SKILLS.glob("*/SKILL.md"):
    t = md.read_text(encoding="utf-8")
    if "skills/<block>/BLOCK.md" not in t or any(f"`{b}`" not in t for b in BLOCK_NAMES):
        fail(f"{md.parent.name}/SKILL.md lacks the standard \"Building blocks\" paragraph naming every BLOCK.md")
for md in list(SKILLS.glob("*/SKILL.md")) + list(SKILLS.glob("*/BLOCK.md")) + list(SKILLS.glob("*/references/*.md")) + [ROOT / "README.md", ROOT / "TOOLS.md"]:
    for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
        for b in BLOCK_NAMES:                         # a block is not a skill any more: "<block> skill" / "<block> SKILL.md"
            if re.search(rf"`?{re.escape(b)}`?\s+(skill\b|SKILL\.md)", line):
                fail(f"{md.relative_to(ROOT).as_posix()}:{i}: calls the building block {b} a skill - say block / BLOCK.md")
for md in SKILLS.glob("*/SKILL.md"):
    t = md.read_text(encoding="utf-8")
    if "user-invocable: false" in t:
        fail(f"{md.parent.name}/SKILL.md is marked user-invocable: false - a building block belongs in BLOCK.md")

for n in notes:
    print("  " + n)
print(f"{len(scripts)} scripts, {len(copies)} _studio.py copies, {skipped} CLIs skipped for missing packages, "
      f"{checked} PEP 723 headers checked, {calls} sys.executable script calls checked")
if fails:
    print(f"\n{len(fails)} problem(s):")
    for f in fails:
        print("  FAIL " + f)
    sys.exit(1)
print("OK")
