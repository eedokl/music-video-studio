"""animated-powerpoint: the scene finishing path (stage video -> look -> sound cues), once with a faked stage render
(scene_stage.mp4 + frames_3d written as the 3D step would) and once with the real 2.5D stage renderer on a scene
with one painted layer and no figure (node + headless browser)."""
from pathlib import Path

from common import (Test, audio_samples, config, expect, expect_film, first_loud, loudest, need, read_json, script,
                    SKILLS)

SCENE = script("animated-powerpoint", "scene.py")
END = 47                                         # frames 0..47 = 2 s
START_CUE, PEAK_CUE = 6, 34

DRIVER = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import scene as SC
folder, steps, layer = sys.argv[2], sys.argv[3].split(","), sys.argv[4]
S = SC.Scene(folder, end=%(end)d, look="standard")
if layer != "-":
    S.layer("wall", layer, w=16, h=9, z=0, order=0)
    S.camera([(0, [0, 0, 16.79, 0, 0, 0]), (%(end)d, [0.4, 0.1, 15.5, 0, 0, 0])])
S.sound(%(start)d, "ui_pop/blip", level=-6, align="start")
S.sound(%(peak)d, "ui_pop/soft", level=-6, align="peak")
print("step: build", flush=True)
S.build()
print("step: built", flush=True)
if "fake" in steps:                               # what the "3d" step leaves behind: frames_3d/ + scene_stage.mp4
    import subprocess, config
    from pathlib import Path
    d = Path(folder); (d / "frames_3d").mkdir(exist_ok=True)
    ff = config.need("ffmpeg")
    subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=24", "-frames:v", "%(n)d",
                    str(d / "frames_3d" / "mp_%%04d.png")], check=True)
    # toon-2d render_multiplane.py names the video after its config: scene_stage.json -> scene_stage.mp4
    SC.encode(d / "frames_3d", d / "scene_stage.mp4", 24)
    steps = [s for s in steps if s != "fake"]
print("step: render", steps, flush=True)
S.render(steps=tuple(steps))
print("RENDERED", S.dir / (S.dir.name + ".mp4"))
''' % {"end": END, "start": START_CUE, "peak": PEAK_CUE, "n": END + 1}


def attack(d, sid="ui_pop/blip", frac=0.05):
    """Seconds from the start of the rendered bank sound to its first sample >= frac of its peak, after the same
    10 ms linear fade-in and peak normalisation as studio-core sfx_mix.py (cue level -6 dB -> peak 0.5)."""
    bank = Path(config().get("sfx_cache") or d.parent.parent / "cache" / "sfx") / (sid.replace("/", "__") + ".wav")
    expect(bank.exists(), f"rendered sound {bank} not found")
    y = audio_samples(bank)
    k = min(480, len(y) // 2)
    z = [v * (i / (k - 1) if i < k else 1.0) for i, v in enumerate(y)]
    pk = max(abs(v) for v in z)
    return next(i for i, v in enumerate(z) if abs(v) >= frac * pk) / 48000


def check_clip(ctx, d):
    clip = d / f"{d.name}.mp4"
    expect_film(ctx, clip, END + 1, tol_audio=0.06)
    ton = d / "ton.wav"
    expect(ton.exists(), "ton.wav missing (sound step)")
    cues = read_json(d / "sound.json")["cues"]
    expect(sorted(c["frame"] for c in cues) == [START_CUE, PEAK_CUE], f"sound.json cue frames {cues}")
    y = audio_samples(ton)
    lead = attack(d)                         # the blip's own first loud sample after the mixer's 10 ms fade-in
    on = first_loud(y, 48000, 0.05 * 0.5 * 32767)
    on = None if on is None else on - lead   # = where the sound file starts in the mix
    expect(on is not None and abs(on - START_CUE / 24) <= 0.0011,
           f'start-aligned cue begins at {on} s, its frame {START_CUE} is {START_CUE / 24:.4f} s')
    t, _ = loudest(y, 48000, (PEAK_CUE - 8) / 24, (PEAK_CUE + 8) / 24)
    expect(abs(t - PEAK_CUE / 24) <= 0.003, f"peak-aligned cue peaks at {t:.4f} s, its frame is {PEAK_CUE / 24:.4f} s")
    return on, t


def run_fake_stage(ctx):
    need("ffmpeg", "earshot")
    d = ctx.dir / "clips" / "s01"
    ctx.py(DRIVER, deps_from=[SCENE], args=[SKILLS / "animated-powerpoint" / "scripts", d, "fake,final,sound", "-"])
    on, t = check_clip(ctx, d)
    ctx.note(f"{END + 1} frames, start cue begins {on * 1000:.1f} ms (frame {START_CUE} = {START_CUE / 24 * 1000:.1f} ms), "
             f"peak cue at {t * 1000:.1f} ms (frame {PEAK_CUE} = {PEAK_CUE / 24 * 1000:.1f} ms)")


def run_real_stage(ctx):
    need("ffmpeg", "earshot", "node", "browser")
    d = ctx.dir / "clips" / "s02"
    d.mkdir(parents=True)
    ctx.ff("-f", "lavfi", "-i", "testsrc2=s=1600x900", "-frames:v", "1", d / "wall.png")
    ctx.py(DRIVER, deps_from=[SCENE], args=[SKILLS / "animated-powerpoint" / "scripts", d, "3d,final,sound", "wall.png"],
           timeout=900)
    expect((d / "scene_stage.mp4").exists(), "the 3D stage step wrote no scene_stage.mp4 (the name scene.py finishes)")
    on, t = check_clip(ctx, d)
    ctx.note(f"real 2.5D stage render: {END + 1} frames, cues at {on * 1000:.1f} / {t * 1000:.1f} ms")


TESTS = [
    Test("animated-powerpoint", run_fake_stage, about="Scene.build + faked stage video -> render(final, sound), cue positions"),
    Test("animated-powerpoint-stage", run_real_stage, slow=True,
         about="Scene with one layer through the real 2.5D stage renderer (node + headless browser) -> final + sound"),
]
