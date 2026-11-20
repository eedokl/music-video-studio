"""ai-video night_run.py kill-and-resume with a fake job runner (no ComfyUI, no GPU): the LTX render is replaced by a
fake that writes a test clip; the second job is killed (hard process kill) while it writes its output. Afterwards no
final file of that job may exist (only its .part file), and a rerun must redo exactly that job and complete it."""
import subprocess
import time

from common import Fail, Test, check_video, expect, need, read_json, script, video_frames, write_json

NIGHT = script("ai-video", "night_run.py")

DRIVER = r'''
import json, os, subprocess, sys, time
from pathlib import Path
if sys.argv[1] == "python":
    print(sys.executable)
    sys.exit(0)
mode, scripts, jobs = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, scripts)
import night_run, comfy, ltx, clips, config
work = Path(jobs).parent
comfy.ensure = lambda *a, **k: True                   # no ComfyUI, no GPU lock
comfy.lock = lambda *a, **k: None
comfy.unlock = lambda *a, **k: None
comfy.free = lambda *a, **k: None
comfy.comfy_dir = lambda *a, **k: None

def fake_render(mode_, image, audio, prompt, out, frames=97, seed=31, strength=1.0, neg=None, meta=None, **kw):
    out = Path(out)
    with open(work / "calls.txt", "a") as f:
        f.write(out.name + "\n")
    tmp = work / ("fake_" + out.stem + ".mp4")
    subprocess.run([config.need("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x176:r=24",
                    "-frames:v", str(frames), "-pix_fmt", "yuv420p", str(tmp)], check=True)
    data = tmp.read_bytes()
    tmp.unlink()
    if mode == "kill" and "s02" in out.name:          # killed in the middle of writing the clip
        with open(out, "wb") as f:
            f.write(data[: len(data) // 2])
            f.flush()
            (work / "writing_s02").write_text("x")
            time.sleep(600)
    out.write_bytes(data)
    m = dict(kind="ltx_" + mode_, fps=24, frames=frames, seed=seed, delay_frames=1, image=str(image))
    m.update(meta or {})
    clips.write_meta(out, **m)
    return out

ltx.render = fake_render
sys.argv = ["night_run.py", jobs, "--min-free-gb", "0", "--no-preflight"]   # no ComfyUI here (test_ai_preflight)
night_run.main()
'''


def run_night(ctx):
    need("ffmpeg")
    d = ctx.dir / "proj"
    (d / "ai" / "start").mkdir(parents=True)
    ctx.ff("-f", "lavfi", "-i", "testsrc2=s=320x176", "-frames:v", "1", d / "ai" / "start" / "s01_v1.png")
    ctx.ff("-f", "lavfi", "-i", "testsrc2=s=320x176", "-frames:v", "1", d / "ai" / "start" / "s02_v1.png")
    ctx.ff("-f", "lavfi", "-i", "sine=f=220:r=48000:d=4", "-ac", "2", d / "song.wav")
    jobs = {"phases": ["ltx"], "jobs": [
        {"id": f"{s}/ltx_s1", "kind": "ltx_lipsync", "out": f"ai/lipsync/{s}_{{img}}_s1.mp4",
         "args": {"image": {"pick": "start", "key": s, "candidates": [f"ai/start/{s}_v1.png"]},
                  "audio": {"src": "song.wav", "from": t, "dur": 1.0}, "prompt": "test", "frames": 25, "seed": 41,
                  "meta": {"song_start": t, "lead_in": 0.0, "shot": s}}}
        for s, t in (("s01", 0.0), ("s02", 1.5))]}
    write_json(d / "jobs.json", jobs)
    drv = ctx.driver_path("driver.py")
    # build the driver's uv environment once and take its python: the kill must hit the python process itself
    py = ctx.py(DRIVER, deps_from=[NIGHT], name="driver.py", args=["python"]).stdout.strip().splitlines()[-1].strip()
    args = [str(script("ai-video", "night_run.py").parent), str(d / "jobs.json")]

    ctx.log(f"$ {py} driver.py kill ...")
    p = subprocess.Popen([py, str(drv), "kill", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    t0 = time.time()
    while not (d / "writing_s02").exists():
        if p.poll() is not None or time.time() - t0 > 180:
            out = p.stdout.read().decode(errors="replace") if p.stdout else ""
            p.kill()
            raise Fail(f"the fake job never reached the s02 write (exit {p.returncode}):\n{out[-1500:]}")
        time.sleep(0.2)
    p.kill()                                                                  # hard kill mid-write
    p.wait(30)
    ctx.log(p.stdout.read().decode(errors="replace"))
    lip = d / "ai" / "lipsync"
    names = sorted(f.name for f in lip.iterdir() if f.is_file())
    ctx.log(f"after kill: {names}")
    expect((lip / "s01_v1_s1.mp4").exists() and (lip / "s01_v1_s1.json").exists(),
           f"job s01 (finished before the kill) is not complete: {names}")
    expect(not (lip / "s02_v1_s1.mp4").exists() and not (lip / "s02_v1_s1.json").exists(),
           f"the killed job left a FINAL file (a rerun would skip it): {names}")
    expect((lip / "s02_v1_s1.part.mp4").exists(), f"no .part file of the killed job: {names}")
    st = ctx.uv(NIGHT, d / "jobs.json", "--status").stdout
    expect("1/2 done" in st, f"--status after the kill: {st.strip()}")

    (d / "calls.txt").unlink()
    ctx.run([py, drv, "resume", *args], timeout=300)
    calls = (d / "calls.txt").read_text().split()
    expect(calls == ["s02_v1_s1.part.mp4"], f"the rerun rendered {calls}, expected only the killed job s02")
    names = sorted(f.name for f in lip.iterdir() if f.is_file())
    expect(not any(".part" in n for n in names), f".part files left after the rerun: {names}")
    f = lip / "s02_v1_s1.mp4"
    expect(f.exists() and not check_video(f) and video_frames(f) == 25, "the rerun's clip is missing or broken")
    m = read_json(lip / "s02_v1_s1.json")
    expect(m.get("song_start") == 1.5 and m.get("frames") == 25, f"clip meta after the rerun: {m}")
    log = (d / "milestones.log").read_text(encoding="utf-8")
    expect("ltx OK     s02/ltx_s1" in log, "milestones.log has no OK line for the resumed job")
    # a changed job is redone and the old output kept (Das Warum: a rewritten prompt made nothing new while the old
    # file was there). An untouched rerun renders nothing; outputs from before the fingerprints are adopted.
    expect((d / "jobs_made.json").exists(), "no jobs_made.json (fingerprints of the finished outputs)")
    (d / "calls.txt").unlink()
    ctx.run([py, drv, "resume", *args], timeout=300)
    expect(not (d / "calls.txt").exists(), "an unchanged rerun rendered a job again")
    jobs["jobs"][0]["args"]["prompt"] = "test, rewritten"
    write_json(d / "jobs.json", jobs)
    st = ctx.uv(NIGHT, d / "jobs.json", "--status").stdout
    expect("1/2 done" in st and "1 to redo" in st, f"--status after a prompt change: {st.strip()}")
    ctx.run([py, drv, "resume", *args], timeout=300)
    calls = (d / "calls.txt").read_text().split()
    expect(calls == ["s01_v1_s1.part.mp4"], f"after the prompt change the rerun rendered {calls}, expected only s01")
    kept = sorted(f.name for f in (lip / "replaced").iterdir())
    expect(len(kept) == 2 and all(n.startswith("s01_v1_s1.") for n in kept), f"old s01 clip + meta not kept: {kept}")
    expect((lip / "s01_v1_s1.mp4").exists() and (lip / "s01_v1_s1.json").exists(), "the redone s01 is incomplete")
    (d / "jobs_made.json").unlink()                                            # a project from before the fingerprints
    (d / "calls.txt").unlink()
    ctx.run([py, drv, "resume", *args], timeout=300)
    expect(not (d / "calls.txt").exists(), "outputs without a fingerprint were redone instead of adopted")
    ctx.note("kill mid-write left only s02 .part (no final file), --status 1/2, rerun redid only s02, clip + meta complete; "
             "a rewritten prompt redid only that job and kept the old clip in replaced/; old outputs are adopted")


TESTS = [Test("night-run-resume", run_night, about="ai-video night_run.py: hard kill mid-write, .part outputs, rerun completes")]
