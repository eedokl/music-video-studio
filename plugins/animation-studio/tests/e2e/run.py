"""End-to-end tests of the animation-studio plugin: per film type a tiny build from synthetic input to the final film.

    python tests/e2e/run.py                      all tests
    python tests/e2e/run.py animated-music-video claudia        only these (name or prefix)
    python tests/e2e/run.py --full               everything real (the film look in every test, longer sections)
    python tests/e2e/run.py --skip-slow          skip the tests marked slow
    python tests/e2e/run.py --list               names, slow marks, what each test covers
    options: --keep (keep every temp folder; failed ones are always kept), -v (stream the build log),
             --profile (slowest commands per test; log.txt has every output line with its elapsed seconds)

Plain Python (standard library) - the plugin scripts themselves run with `uv run --offline` (their PEP 723 pins from
the local uv cache, never a download). No GPU AI jobs, no network: slow model steps (Whisper, Demucs, ComfyUI) are
replaced by synthetic analysis files / a fake job runner; everything after them runs the real build scripts.
External programs come from the machine config (studio-core config.py); a test SKIPs when one it needs is missing.
The tests use a copy of the machine config (ANIMATION_STUDIO_CONFIG), so scene shims never rewrite the real one.
Output: one line per test, PASS / FAIL / SKIP with the reason and the runtime; exit code 1 when any test FAILs.
"""
import argparse
import importlib
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402


def discover():
    tests = []
    for f in sorted(HERE.glob("test_*.py")):
        mod = importlib.import_module(f.stem)
        tests += list(getattr(mod, "TESTS", []))
    return tests


def isolate_env(root):
    """Copy of the machine config + offline switches for every subprocess."""
    src = Path(os.environ.get("ANIMATION_STUDIO_CONFIG") or Path.home() / ".animation-studio" / "config.json")
    cfg = root / "config.json"
    if src.exists():
        shutil.copyfile(src, cfg)
    else:
        cfg.write_text("{}", encoding="utf-8")
    os.environ.update({"ANIMATION_STUDIO_CONFIG": str(cfg), "UV_OFFLINE": "1", "HF_HUB_OFFLINE": "1",
                       "TRANSFORMERS_OFFLINE": "1", "WHISPER_CPU": "1", "PYTHONIOENCODING": "utf-8"})
    for k in ("PREVIEW", "TTS_ENGINE", "INSTALL_BROWSER"):
        os.environ.pop(k, None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*")
    ap.add_argument("--full", action="store_true", help="no fast settings: film look everywhere, longer sections")
    ap.add_argument("--skip-slow", action="store_true", help="skip tests marked slow")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the temp folders of passed / skipped tests too")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--profile", action="store_true", help="print the slowest commands of every test (log.txt has "
                    "every output line with its elapsed seconds)")
    a = ap.parse_args()
    tests = discover()
    if a.list:
        for t in tests:
            print(f"{t.name:34s} {'slow' if t.slow else '    '}  {t.about}")
        return 0
    if a.names:
        unknown = [n for n in a.names if not any(t.name == n or t.name.startswith(n) for t in tests)]
        if unknown:
            print(f"unknown test(s): {', '.join(unknown)} - see --list")
            return 2
        tests = [t for t in tests if any(t.name == n or t.name.startswith(n) for n in a.names)]
    if not shutil.which("uv"):
        print("uv is not on PATH - every plugin script runs with `uv run`; install uv first")
        return 2
    root = Path(tempfile.mkdtemp(prefix="as_e2e_"))
    isolate_env(root)
    os.environ["ANIMATION_STUDIO_E2E_FULL"] = "1" if a.full else "0"
    print(f"animation-studio e2e: {len(tests)} test(s), {'full' if a.full else 'fast'} mode, temp {root}")
    results, t_all = [], time.time()
    for t in tests:
        if a.skip_slow and t.slow:
            results.append((t.name, "SKIP", "slow (--skip-slow)", 0.0))
            print(f"SKIP  {t.name:34s}    0s  slow (--skip-slow)", flush=True)
            continue
        ctx = common.Ctx(root / t.name, verbose=a.verbose)
        t0 = time.time()
        try:
            t.fn(ctx)
            status, why = "PASS", "; ".join(ctx.notes)
        except common.Skip as e:
            status, why = "SKIP", str(e)
        except Exception as e:                       # Fail or a broken test
            status = "FAIL"
            why = str(e) if isinstance(e, common.Fail) else f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
        dt = time.time() - t0
        results.append((t.name, status, why, dt))
        keep = a.keep or status == "FAIL"
        lines = why.strip().splitlines() or [""]
        print(f"{status}  {t.name:34s} {dt:5.0f}s  {lines[0]}", flush=True)
        for l in lines[1:]:
            print(f"      {l}")
        if a.profile and ctx.times:
            print("      slowest: " + ", ".join(f"{n} {s:.1f}s" for s, n in sorted(ctx.times, reverse=True)[:4]))
        if status == "FAIL":
            print(f"      log and files kept: {ctx.dir}")
        if not keep:
            common.safe_rmtree(ctx.dir)
    n = {s: sum(1 for r in results if r[1] == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"\n{n['PASS']} passed, {n['FAIL']} failed, {n['SKIP']} skipped in {time.time() - t_all:.0f} s")
    if not any(r[1] == "FAIL" for r in results) and not a.keep:
        common.safe_rmtree(root)
    else:
        print(f"temp folder kept: {root}")
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
