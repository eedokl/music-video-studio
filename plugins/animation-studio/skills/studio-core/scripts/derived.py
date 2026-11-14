"""Derived files and folders (caches, renders of renders): remember WHAT an artefact was built from and rebuild it
atomically when that changes. Every new cache in this plugin uses this module (CONVENTIONS.md).

    import derived
    if not derived.fresh(png, inputs=[svg], spec={"sif": text, "w": 960}):
        with derived.build(png, inputs=[svg], spec={"sif": text, "w": 960}) as b:
            render(b.path)                      # write the temp path; it becomes `png` only when the block succeeds

- Freshness = a CONTENT hash (blake2b) of the inputs (files, folders, or missing - creating an input counts as a
  change) plus a JSON-able `spec` (settings, text, versions). Never mtimes: copying, zipping or checking out a project
  does not make anything stale, editing an input does.
- Records live next to the target in `<parent>/.derived/<name>.json` and hold no absolute paths (inputs are named by
  their base name only), so a project or the shared bank can move. A record also carries `extra` (the build's own
  metadata, e.g. word times of a spoken line): `derived.recorded(target)["extra"]`.
- Atomic: `build()` writes `<parent>/.tmp.<pid>.<name>` (file, or folder with folder=True); on success the old record is
  dropped, the temp replaces the target, then the record is written. An interrupted or failed build leaves no record
  for the new content, so it never looks fresh (the temp is removed, or cleaned by the next build). The key is taken
  when the build STARTS: an input edited during the build makes the result stale at once.
- `commit(tmp, target, ...)` is the same last step for batch builders that write several temps first (speak.py).
- `Ledger(store, name)`: the other direction - content hashes of the files a step WROTE into a folder, so a later run
  can tell its own outputs from files another program put there (captions.py: composites vs. a re-render). Each file
  is written under a temp name, its hash is logged (fsync), and only then renamed - every file visible under its
  final name is known, even after a kill at any moment.
Standard library only.
"""
import contextlib
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

VERSION = 1
STORE = ".derived"                      # <parent>/.derived/<target name>.json
MISSING = "missing"


# ------------------------------------------------------------------ hashing
def file_hash(path):
    """Content hash of one file (blake2b, 128 bit, hex)."""
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def input_hash(path):
    """Hash of an input: a file's content, a folder's relative names + contents (records and temps excluded), or
    "missing"."""
    p = Path(path)
    if p.is_file():
        return file_hash(p)
    if p.is_dir():
        h = hashlib.blake2b(digest_size=16)
        for f in sorted(x for x in p.rglob("*") if x.is_file()):
            rel = f.relative_to(p)
            if STORE in rel.parts or any(part.startswith(".tmp.") for part in rel.parts):
                continue
            h.update(rel.as_posix().encode("utf-8") + b"\0" + file_hash(f).encode() + b"\n")
        return "dir:" + h.hexdigest()
    return MISSING


def _spec_json(spec):
    return json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def key(inputs=(), spec=None):
    """The build key of these inputs (in this order) + spec."""
    h = hashlib.blake2b(digest_size=16)
    h.update(f"v{VERSION}\n".encode())
    for p in inputs:
        h.update(input_hash(p).encode() + b"\n")
    h.update(_spec_json(spec).encode("utf-8"))
    return h.hexdigest()


# ------------------------------------------------------------------ records
def record_path(target):
    t = Path(target)
    return t.parent / STORE / (t.name + ".json")


def _replace(src, dst, tries=8):
    """os.replace with a few retries (Windows: a virus scanner or indexer may hold the file for a moment)."""
    for i in range(tries):
        try:
            return os.replace(src, dst)
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.05 * (i + 1))


def write_text(path, text):
    """Write a text file atomically (temp + rename): readers see the old or the new file, never half of one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp.{os.getpid()}.{path.name}"
    tmp.write_text(text, encoding="utf-8")
    _replace(tmp, path)


def recorded(target):
    """The record of target ({"key", "inputs", "spec_hash", "extra", ...}) or None."""
    try:
        r = json.loads(record_path(target).read_text(encoding="utf-8"))
        return r if isinstance(r, dict) and "key" in r else None
    except (OSError, ValueError):
        return None


def fresh(target, inputs=(), spec=None):
    """True when target exists and was built (completely) from exactly these inputs + spec."""
    if not Path(target).exists():
        return False
    r = recorded(target)
    return r is not None and r.get("key") == key(inputs, spec)


def record(target, inputs=(), spec=None, extra=None, built_key=None):
    """Write target's record (after the target is complete). built_key: the key taken when the build started."""
    sj = _spec_json(spec)
    data = {"version": VERSION, "key": built_key or key(inputs, spec),
            "inputs": [{"name": Path(p).name, "hash": input_hash(p)} for p in inputs],
            "spec_hash": hashlib.blake2b(sj.encode("utf-8"), digest_size=16).hexdigest(),
            "built": time.strftime("%Y-%m-%d %H:%M:%S")}
    if len(sj) <= 2000:
        data["spec"] = spec                                # readable for small specs (diagnostics only)
    if extra is not None:
        data["extra"] = extra
    write_text(record_path(target), json.dumps(data, ensure_ascii=False, indent=1, default=str))


def forget(target):
    """Drop target's record (it no longer counts as fresh)."""
    record_path(target).unlink(missing_ok=True)


def temp_path(target):
    """`<parent>/.tmp.<pid>.<name>` - per process, so two processes building the same target never share a temp
    (the suffix stays, tools that pick the format from the extension still work)."""
    t = Path(target)
    return t.parent / f".tmp.{os.getpid()}.{t.name}"


def clean_temps(target, older=3600):
    """Remove temps of target that killed builds left behind (older than `older` s - a running build keeps its own)."""
    t = Path(target)
    now = time.time()
    for x in t.parent.glob(f".tmp.*.{t.name}"):
        try:
            if now - x.stat().st_mtime > older:
                _remove(x)
        except OSError:
            pass


def _remove(p):
    p = Path(p)
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p, ignore_errors=True)
    else:
        p.unlink(missing_ok=True)


def commit(tmp, target, inputs=(), spec=None, extra=None, built_key=None):
    """Finished temp -> target, then the record. Order: record dropped, target replaced, record written - a kill
    anywhere leaves either the old target with its old record or no record (= stale), never new content under an old
    record."""
    tmp, target = Path(tmp), Path(target)
    forget(target)
    if tmp.is_dir() and target.exists():
        _remove(target)                                    # a folder cannot be replaced in one step on Windows
    _replace(tmp, target)
    record(target, inputs, spec, extra=extra, built_key=built_key)
    return target


class Build:
    def __init__(self, path):
        self.path = path                                   # write here
        self.extra = None                                  # optional metadata for the record


@contextlib.contextmanager
def build(target, inputs=(), spec=None, folder=False):
    """Build target atomically: `with derived.build(t, inputs, spec) as b: write(b.path)`. b.extra -> the record."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    built_key = key(inputs, spec)                          # inputs as they are when the build starts
    tmp = temp_path(target)
    clean_temps(target)
    _remove(tmp)
    if folder:
        tmp.mkdir()
    b = Build(tmp)
    try:
        yield b
        if not tmp.exists():
            raise RuntimeError(f"the build of {target.name} wrote nothing to {tmp.name}")
    except BaseException:
        _remove(tmp)
        raise
    commit(tmp, target, inputs, spec, extra=b.extra, built_key=built_key)


# ------------------------------------------------------------------ ledger of written files
class Ledger:
    """Content hashes of the files a step wrote into a folder: `<store>/<name>.json` ({file name: hash}, the last
    finished pass) + `<store>/<name>.partial` (one hash per line, the pass in progress or an interrupted one)."""

    def __init__(self, store, name):
        self.store = Path(store)
        self.manifest = self.store / f"{name}.json"
        self.partial = self.store / f"{name}.partial"

    def known(self):
        """Every hash this ledger ever logged for the current files (finished manifest + log of an interrupted pass),
        or None when there is no record in the hash format (no manifest, or an older format)."""
        known, have = set(), False
        try:
            m = json.loads(self.manifest.read_text(encoding="utf-8"))
            if m and all(isinstance(v, str) for v in m.values()):
                known |= set(m.values())
                have = True
        except (OSError, ValueError, AttributeError):
            pass
        try:
            known |= {h for h in self.partial.read_text(encoding="utf-8").split() if h}
            have = True
        except OSError:
            pass
        return known if have else None

    def foreign(self, files):
        """The files whose content this ledger never wrote ([] = all ours), or None without a hash record."""
        known = self.known()
        if known is None:
            return None
        return [f for f in files if file_hash(f) not in known]

    @staticmethod
    def clean(folder, pattern="*"):
        """Remove half-written temps (`.tmp.<pattern>`) an interrupted pass left in folder."""
        for t in Path(folder).glob(f".tmp.{pattern}"):
            _remove(t)

    @contextlib.contextmanager
    def session(self):
        """`with ledger.session() as s: s.save(final_path, lambda tmp: img.save(tmp, format="PNG"))`. On success the
        manifest becomes this pass's {name: hash} and the partial log is removed; an interrupted pass keeps its log."""
        self.store.mkdir(parents=True, exist_ok=True)
        s = _Session()
        with open(self.partial, "a", encoding="utf-8") as log:   # opened before the first file is written
            s.log = log
            yield s
        write_text(self.manifest, json.dumps(s.written))
        self.partial.unlink(missing_ok=True)


class _Session:
    def __init__(self):
        self.written, self.log = {}, None

    def save(self, final, write):
        """write(tmp) -> hash logged + fsynced -> renamed to final. Returns the hash."""
        final = Path(final)
        tmp = final.parent / f".tmp.{final.name}"          # a name the caller's glob ("f.*.png") does not match
        write(tmp)
        h = file_hash(tmp)
        self.log.write(h + "\n")
        self.log.flush()
        os.fsync(self.log.fileno())
        _replace(tmp, final)
        self.written[final.name] = h
        return h
