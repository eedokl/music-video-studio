"""animated-powerpoint: the scene finishing path (stage video -> look -> sound cues), once with a faked stage render
(scene_stage.mp4 + frames_3d written as the 3D step would) and once with the real 2.5D stage renderer on a scene
with one painted layer and no figure (node + headless browser); and the step-out clip path on a synthetic slide
(deck.py -> figures.py -> parts.py -> clip.py plan / synfig / light / tex, with the 3D stage, final and sound in the
slow variant)."""
import xml.etree.ElementTree as ET
from pathlib import Path

from common import (Test, audio_samples, config, expect, expect_film, first_loud, loudest, need, read_json, script,
                    write_json, SKILLS)

SCENE = script("animated-powerpoint", "scene.py")
DECK, FIGURES, PARTS, CLIP = (script("animated-powerpoint", n) for n in ("deck.py", "figures.py", "parts.py", "clip.py"))
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


SLIDE = r'''
import sys
from PIL import Image, ImageDraw
im = Image.new("RGB", (1920, 1080), (255, 255, 255))      # one ink-outlined figure on a white page image
d = ImageDraw.Draw(im)
INK, LW, cx, feet = (20, 20, 22), 7, %(cx)d, %(feet)d
d.ellipse((cx - 70, feet - 20, cx - 10, feet + 10), fill=(60, 60, 64), outline=INK, width=LW)
d.ellipse((cx + 10, feet - 20, cx + 70, feet + 10), fill=(60, 60, 64), outline=INK, width=LW)
d.rounded_rectangle((cx - 110, feet - 330, cx + 110, feet - 10), radius=60, fill=(210, 80, 60), outline=INK, width=LW)
d.rounded_rectangle((cx + 100, feet - 300, cx + 150, feet - 140), radius=24, fill=(210, 80, 60), outline=INK, width=LW)
d.ellipse((cx - 120, feet - 560, cx + 120, feet - 320), fill=(250, 220, 190), outline=INK, width=LW)
for ex in (cx - 45, cx + 45):
    d.ellipse((ex - 28, feet - 480, ex + 28, feet - 424), fill=(255, 255, 255), outline=INK, width=5)
    d.ellipse((ex - 11, feet - 463, ex + 11, feet - 441), fill=INK)
d.arc((cx - 50, feet - 420, cx + 50, feet - 360), 20, 160, fill=INK, width=6)
im.save(sys.argv[1])
'''
CX, FEET = 1300, 940


def run_clip(ctx, film=False):
    """A figure steps out of a synthetic slide: deck import, figure cut, parts (auto + an arm), clip.py."""
    need("synfig", *(("ffmpeg", "node", "browser", "earshot") if film else ()))
    ctx.py(SLIDE % {"cx": CX, "feet": FEET}, deps_from=[PARTS], name="slide.py", args=[ctx.dir / "slide.png"])
    ctx.uv(DECK, ctx.dir / "slide.png", "--out", ctx.dir / "deck", "--width", "1920")
    ctx.uv(FIGURES, "--deck", ctx.dir / "deck" / "deck.json", "--slide", "1", "--names", "bob", "--upscale", "1",
           "--out", ctx.dir / "figures")
    fig = ctx.dir / "figures" / "bob"
    ctx.uv(PARTS, fig, "--auto")
    x0, y0 = read_json(fig / "figure.json")["crop"][:2]
    pj = read_json(fig / "parts.json")
    expect("head" in pj["parts"] and "eyes" in pj["parts"], f"parts.py --auto found no head / eyes: {pj['parts']}")
    pj["parts"] = ["body", "arm_r", "head", "eyes"]               # a jointed arm: the gesture channel of the rig
    pj["poly"]["arm_r"] = [[CX + 94 - x0, FEET - 306 - y0], [CX + 170 - x0, FEET - 306 - y0],
                           [CX + 170 - x0, FEET - 131 - y0], [CX + 94 - x0, FEET - 131 - y0]]
    pj["pivots"]["arm_r"] = [CX + 122 - x0, FEET - 284 - y0]
    pj.pop("auto", None)
    write_json(fig / "parts.json", pj)
    ctx.uv(PARTS, fig)
    d = ctx.dir / "clips" / "c1"
    d.mkdir(parents=True)
    write_json(d / "clip.json", {"deck": "../../deck/deck.json", "slide": 1, "figures_dir": "../../figures", "seed": 5,
                                 "boil": 0, "ending": "return", "hold": 20, "look": "none",
                                 "figures": [{"name": "bob", "action": "step_out", "start": 10, "tag": ["Bob", "Tester"],
                                              "gesture": "fist", "spin": "flip"}]})
    steps = ["plan", "synfig", "light", "tex"] + (["3d", "final", "sound"] if film else [])
    for s in steps:
        ctx.uv(CLIP, d / "clip.json", "--only", s, timeout=900)
    plan = read_json(d / "plan.json")
    end, ev = plan["end"], plan["events"]["bob"]
    order = ["start", "take_off", "pop", "land", "tag", "back_take_off", "back_in_slot"]
    expect(all(ev[a] < ev[b] for a, b in zip(order, order[1:])) and ev["back_in_slot"] < end,
           f"events out of order: {ev} (end {end})")
    expect(read_json(d / "clip.json").get("end") == end, "clip.json was not updated with the clip end")
    stage = read_json(d / "stage.json")
    expect(len(stage["frames"]) == end + 1 and stage["end"] == end, f"stage.json: {len(stage['frames'])} frames, end {end}")
    expect(stage["figures"][0]["tag"] and len(stage["slide"]["states"]) == 2,
           f"stage.json: tag {stage['figures'][0]['tag']}, slide states {stage['slide']['states']}")
    root = ET.parse(d / "bob.sif").getroot()
    groups = {e.get("desc") for e in root.iter("layer")}
    expect({"bob", "spin", "squash", "head", "eyes", "arm_r"} <= groups, f"bob.sif groups {sorted(g for g in groups if g)}")
    for sub, pat in (("frames/bob", "bob.*.png"), ("light/bob", "s.*.png")):
        n = len(list((d / sub).glob(pat)))
        expect(n == end + 1, f"{sub}: {n} frames, expected {end + 1}")
    tex = {p.name for p in (d / "tex").glob("*.png")}
    expect({"floor.png", "wall.png", "shadow.png", "sparkle.png", "tag_bob.png", "slide_00.png", "slide_01.png"} <= tex,
           f"tex/: {sorted(tex)}")
    if film:
        expect_film(ctx, d / "c1.mp4", end + 1)
        chk = read_json(d / "check.json")
        expect(chk["first_vs_slide"] < 3 and chk["last_vs_first"] < 0.5,
               f"check.json {chk}: the clip must start on the slide and loop (ending return)")
        ctx.note(f"{end + 1} frames, first vs slide {chk['first_vs_slide']}, last vs first {chk['last_vs_first']}")
    else:
        ctx.note(f"{end + 1} frames, events take_off {ev['take_off']} land {ev['land']} back {ev['back_in_slot']}, "
                 f"{len(groups)} sif layers, {len(tex)} textures")


TESTS = [
    Test("animated-powerpoint", run_fake_stage, about="Scene.build + faked stage video -> render(final, sound), cue positions"),
    Test("animated-powerpoint-clip", run_clip,
         about="synthetic slide -> deck.py, figures.py, parts.py -> clip.py plan, synfig, light, tex (events, sif, stage)"),
    Test("animated-powerpoint-clip-film", lambda ctx: run_clip(ctx, film=True), slow=True,
         about="the same clip through the 2.5D stage (node + headless browser), final and sound: loop check, film"),
    Test("animated-powerpoint-stage", run_real_stage, slow=True,
         about="Scene with one layer through the real 2.5D stage renderer (node + headless browser) -> final + sound"),
]
