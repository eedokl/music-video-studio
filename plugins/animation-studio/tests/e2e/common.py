"""Shared helpers of the end-to-end tests (standard library only - the plugin scripts run with `uv run --offline`).

A test is a function `fn(ctx)` registered in its module's TESTS list as Test(name, fn, slow=..., about=...).
It builds in ctx.dir (a fresh temp folder), raises Skip("reason") when an external tool is missing and Fail("what")
(or any exception) when the build path is broken. ctx.run(...) logs every command and its output to ctx.dir/log.txt.
"""
import array
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]
SKILLS = PLUGIN / "skills"
FPS = 24


def full():
    """--full: everything real and at the sizes of the first version of each test (default: the fast settings, which
    only drop work that the test does not check - e.g. "look": "none" where the look is not what the test protects)."""
    return os.environ.get("ANIMATION_STUDIO_E2E_FULL") == "1"


class Skip(Exception):
    pass


class Fail(AssertionError):
    pass


class Test:
    def __init__(self, name, fn, slow=False, about=""):
        self.name, self.fn, self.slow, self.about = name, fn, slow, about


def script(skill, name):
    return SKILLS / skill / "scripts" / name


# ------------------------------------------------------------------ machine config (studio-core config.py)
def config():
    p = str(SKILLS / "studio-core" / "scripts")
    if p not in sys.path:
        sys.path.insert(0, p)
    import config as c                      # stdlib only
    return c


def tool(key):
    """Path of a configured external program / setting that exists, else None (studio-core config.get)."""
    v = config().get(key)
    if not v:
        return None
    if Path(v).exists() or shutil.which(v):
        return v
    return None


def need(*keys):
    """Skip the test unless every key is configured and exists."""
    missing = [k for k in keys if not tool(k)]
    if missing:
        raise Skip(f"not configured / not found: {', '.join(missing)} (studio-core check_tools.py)")


def ffmpeg():
    f = tool("ffmpeg")
    if not f:
        raise Skip("ffmpeg not configured")
    return f


def ffprobe():
    f = tool("ffprobe")
    if f:
        return f
    cand = Path(ffmpeg()).with_name("ffprobe" + Path(ffmpeg()).suffix)
    return str(cand) if cand.exists() else shutil.which("ffprobe")


# ------------------------------------------------------------------ the test context
class Ctx:
    def __init__(self, folder, verbose=False):
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.logf = self.dir / "log.txt"
        self.verbose = verbose
        self.notes = []
        self.times = []                     # (seconds, command) of every ctx.run

    def log(self, msg):
        with open(self.logf, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
        if self.verbose:
            print("      " + msg.rstrip()[:300], flush=True)

    def note(self, msg):
        """A fact for the PASS line (measured numbers)."""
        self.notes.append(msg)
        self.log("NOTE " + msg)

    def run(self, cmd, cwd=None, timeout=900, check=True, env=None):
        """Run a command; its output (stdout + stderr) goes to log.txt with the elapsed seconds in front of every line,
        so the log shows where a step spends its time. Returns a CompletedProcess (stdout = the whole output)."""
        import threading
        cmd = [str(c) for c in cmd]
        self.log(f"$ {' '.join(cmd)}" + (f"   (cwd {cwd})" if cwd else ""))
        t0 = time.time()
        p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, errors="replace", env=dict(os.environ, PYTHONUNBUFFERED="1", **(env or {})))
        lines = []

        def pump():
            for line in p.stdout:
                lines.append(line)
                self.log(f"  [+{time.time() - t0:5.1f}s] {line.rstrip()}")
        th = threading.Thread(target=pump, daemon=True)
        th.start()
        try:
            p.wait(timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            th.join(5)
            raise Fail(f"timed out after {timeout} s: {next((Path(c).name for c in cmd if c.endswith('.py')), cmd[0])}")
        th.join(30)
        out = "".join(lines)
        dt = time.time() - t0
        self.log(f"  [exit {p.returncode}, {dt:.1f} s]")
        self.times.append((dt, next((Path(c).name for c in cmd if c.endswith((".py", ".exe"))), Path(cmd[0]).name)))
        if check and p.returncode != 0:
            tail = "\n".join(out.strip().splitlines()[-12:])
            name = next((Path(c).name for c in cmd if c.endswith(".py")), Path(cmd[0]).name)
            raise Fail(f"{name} exited {p.returncode}:\n{tail}")
        return subprocess.CompletedProcess(cmd, p.returncode, out, "")

    def uv(self, path, *args, **kw):
        """`uv run --offline <plugin script> args` (the script's own PEP 723 dependencies, never a download)."""
        return self.run(["uv", "run", "--offline", path, *args], **kw)

    def py(self, code, deps_from=(), name="driver.py", args=(), **kw):
        """Run Python code under `uv run --offline` with the merged PEP 723 dependencies of the given plugin scripts
        (so a driver that imports plugin modules gets exactly their pins). The driver is written into ctx.dir."""
        deps, py = [], ">=3.12"
        for s in deps_from:
            d, p = pep723(Path(s))
            deps += [x for x in d if x not in deps]
            py = p or py
        head = "# /// script\n# requires-python = \"%s\"\n# dependencies = %s\n# ///\n" % (py, json.dumps(deps))
        f = self.driver_path(name)
        if not f.exists() or f.read_text(encoding="utf-8") != head + code:
            f.write_text(head + code, encoding="utf-8")
        return self.run(["uv", "run", "--offline", f, *args], **kw)

    def driver_path(self, name="driver.py"):
        """Drivers live in ONE fixed folder (not the test's temp folder): uv keys a script's environment by the
        script's path, so a fresh path would re-install all packages (~10 s for the animated-powerpoint pins) on
        every run."""
        import tempfile
        d = Path(tempfile.gettempdir()) / "animation_studio_e2e_drivers"
        d.mkdir(exist_ok=True)
        return d / f"{self.dir.name}_{name}"

    def ff(self, *args, **kw):
        return self.run([ffmpeg(), "-y", "-v", "error", *args], **kw)


_PEP = re.compile(r"(?m)^# /// script$\s(?P<c>(^#(| .*)$\s)+)^# ///$")


def pep723(path):
    """(dependencies, requires-python) of a plugin script's inline metadata."""
    m = _PEP.search(path.read_text(encoding="utf-8"))
    if not m:
        return [], None
    body = "\n".join(l[2:] if l.startswith("# ") else l[1:] for l in m.group("c").splitlines())
    try:
        import tomllib
        d = tomllib.loads(body)
        return list(d.get("dependencies", [])), d.get("requires-python")
    except ImportError:                                # python < 3.11: a small fallback parser
        deps = re.search(r"dependencies\s*=\s*\[(.*?)\]", body, re.S)
        rp = re.search(r'requires-python\s*=\s*"([^"]+)"', body)
        return re.findall(r'"([^"]+)"', deps.group(1)) if deps else [], rp.group(1) if rp else None


# ------------------------------------------------------------------ media measurements (ffmpeg, stdlib)
def video_frames(path):
    """Number of decoded video frames."""
    r = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "rawvideo", "-f", "null", "-",
                        "-progress", "pipe:1", "-nostats"], capture_output=True, text=True, errors="replace")
    n = re.findall(r"frame=(\d+)", r.stdout)
    if not n:
        raise Fail(f"cannot count frames of {path}: {r.stderr[-300:]}")
    return int(n[-1])


def video_fps(path):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Video:.*?([\d.]+) fps", r.stderr)
    return float(m.group(1)) if m else None


def check_video(path):
    """'' when the whole file decodes without one error line (as studio-core media.check_video)."""
    r = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-map", "0", "-f", "null", "-"], capture_output=True,
                       text=True, errors="replace")
    return r.stderr.strip()


def audio_samples(path, sr=48000):
    """Mono 16-bit samples of the first audio stream (array('h'))."""
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if sys.byteorder != "little":
        a.byteswap()
    return a


def audio_seconds(path, sr=48000):
    return len(audio_samples(path, sr)) / sr


def has_audio(path):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    return "Audio:" in r.stderr


def frame_colours(path, w=16, h=9):
    """Mean (r, g, b) of every decoded frame (scaled to w x h first)."""
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-map", "0:v:0", "-vf", f"scale={w}:{h}:flags=area",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = w * h * 3
    out = []
    for k in range(len(raw) // n):
        b = raw[k * n:(k + 1) * n]
        out.append(tuple(sum(b[c::3]) / (w * h) for c in range(3)))
    return out


def first_loud(samples, sr, thresh, start=0.0):
    """Second of the first sample with |x| >= thresh at or after `start`, or None."""
    for i in range(int(start * sr), len(samples)):
        if abs(samples[i]) >= thresh:
            return i / sr
    return None


def loudest(samples, sr, t0, t1):
    i0, i1 = int(t0 * sr), min(int(t1 * sr), len(samples))
    best = max(range(i0, i1), key=lambda i: abs(samples[i]))
    return best / sr, abs(samples[best])


def expect(cond, msg):
    if not cond:
        raise Fail(msg)


def expect_film(ctx, path, frames, fps=FPS, audio=True, tol_audio=0.05):
    """film exists, decodes with 0 errors, has exactly `frames` frames and (optionally) audio of the same length."""
    path = Path(path)
    expect(path.exists(), f"{path.name} missing")
    err = check_video(path)
    expect(not err, f"{path.name}: decode errors: {err[:300]}")
    n = video_frames(path)
    expect(n == frames, f"{path.name}: {n} frames, expected {frames}")
    if audio:
        expect(has_audio(path), f"{path.name}: no audio stream")
        a = audio_seconds(path)
        expect(abs(a - frames / fps) <= tol_audio,
               f"{path.name}: audio {a:.3f} s vs picture {frames / fps:.3f} s (difference > {tol_audio} s)")
    return n


# ------------------------------------------------------------------ synthetic inputs
def tone(ctx, out, seconds, freq=220, loud_from=None, sr=48000):
    """Stereo test song: a soft two-tone chord with a short click on every 0.5 s; from `loud_from` s on 12 dB louder
    (a sound mark to measure sync against)."""
    vol = "0.25" if loud_from is None else f"if(lt(t\\,{loud_from})\\,0.06\\,0.25)"
    expr = (f"{vol}*(sin(2*PI*{freq}*t)+0.6*sin(2*PI*{freq * 1.5}*t))/1.6"
            f"+0.3*exp(-60*mod(t\\,0.5))*sin(2*PI*1200*t)*{vol}")
    ctx.ff("-f", "lavfi", "-i", f"aevalsrc={expr}:s={sr}:d={seconds}", "-ac", "2", str(out))
    return Path(out)


def song_sheet(duration, words, beat=0.5, fps=FPS):
    """analysis/song_sheet.json content in the format of song-analysis track_read.py.
    words: [(word, t, end, line_index)]; lines are built from the words."""
    beats, t, k = [], 0.0, 0
    while t < duration:
        beats.append({"t": round(t, 3), "frame": round(t * fps), "bar": k // 4, "beat": k % 4 + 1,
                      "downbeat": k % 4 == 0})
        t += beat
        k += 1
    W = [{"word": w, "t": t0, "end": t1, "frame": round(t0 * fps), "end_frame": round(t1 * fps), "line": li,
          "source": "recognized"} for w, t0, t1, li in words]
    lines = []
    for li in sorted({w["line"] for w in W}):
        ws = [w for w in W if w["line"] == li]
        lines.append({"line": li, "text": " ".join(w["word"] for w in ws), "t": ws[0]["t"], "end": ws[-1]["end"],
                      "frame": ws[0]["frame"], "end_frame": ws[-1]["end_frame"]})
    return {"source": "song.wav", "fps": fps, "duration": round(duration, 3), "tempo_bpm": round(60 / beat, 1),
            "beats": beats, "accents": [{"t": b["t"], "frame": b["frame"], "strength": 0.5} for b in beats[::2]],
            "sections": [{"start": 0.0, "end": duration, "frame": 0}], "words": W, "lines": lines}


def assignment(figures, sung, fps=FPS):
    """analysis/assignment.json in the format of song-analysis voices.py: sung = {figure: [(t0, t1)]} -> mouth cues
    alternating B/C/D while singing, X otherwise."""
    out = {"fps": fps, "figures": {}}
    for k in figures:
        cues = [[0.0, "X"]]
        for t0, t1 in sung.get(k, []):
            t, i = t0, 0
            while t < t1 - 1e-6:
                cues.append([round(t, 3), "BCDC"[i % 4]])
                t += 0.125
                i += 1
            cues.append([round(t1, 3), "X"])
        out["figures"][k] = cues
    return out


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ cleanup that never follows links
def _is_link(p):
    try:
        st = os.lstat(p)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)      # FILE_ATTRIBUTE_REPARSE_POINT (junction)


def unlink_links(root):
    """Remove every symlink / junction below root (the link only, never its target)."""
    for dirpath, dirnames, filenames in os.walk(root):
        for d in list(dirnames):
            p = os.path.join(dirpath, d)
            if _is_link(p):
                try:
                    os.rmdir(p)
                except OSError:
                    os.unlink(p)
                dirnames.remove(d)


def safe_rmtree(root):
    if not Path(root).exists():
        return
    unlink_links(root)

    def onerr(func, path, exc):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass
    shutil.rmtree(root, onerror=onerr)


def make_junction(link, target):
    """Directory link (junction on Windows, symlink elsewhere)."""
    link, target = Path(link), Path(target).resolve()
    if os.name == "nt":
        r = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        if r.returncode or not link.exists():
            raise Fail(f"mklink /J failed: {(r.stdout + r.stderr).decode(errors='replace')}")
    else:
        os.symlink(target, link, target_is_directory=True)


def link_tree(dst, src, skip=(".vite", ".cache")):
    """A real folder dst whose entries link to the entries of src (sub-folders as junctions, files copied): tools may
    create new entries in dst (e.g. vite's node_modules/.vite cache) without writing into src.
    Returns the links made (remove them with unlink_links / safe_rmtree, never with a plain rmtree)."""
    dst, src = Path(dst), Path(src)
    dst.mkdir(parents=True, exist_ok=True)
    made = []
    for e in sorted(src.iterdir()):
        if e.name in skip:
            continue
        if e.is_dir():
            make_junction(dst / e.name, e)
            made.append(dst / e.name)
        else:
            shutil.copy2(e, dst / e.name)
    return made
