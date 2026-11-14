# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# ///
"""Recipe "night shift with holograms" - one figure at night, neon sign, glowing panels pop on spoken words
(reference: ai_efficiency S7 "Vibe coding").

  intro    night room, the neon sign flickers on, the builder types furiously (head bobs, key flashes)
  words    builder line: one hologram per keyword (here CODE / TEST / ITERATE / SHIP) - gag: the last panel (a rocket)
           takes off vertically out of the frame
  narrator a prompt line appears on "describe", on "minutes" an app assembles from panels (bars, line, surface,
           wafer, app, check) that circle the builder
  dream    the builder leans back dreamily (second line); gag: the panels glitch - the builder startles (double take)
Scene light: blue tint + magenta rim on the figure. Inputs: three voice files, the night set (back + table).
Vary in recipe.json: cast, neon text, word panels [[kind, title, word]], app panels, words, colours, voices, set, seed.
Run: uv run s07_night_holograms.py <clip folder> [--plan]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import props as PR  # noqa: E402
import scene as SC  # noqa: E402

DEFAULTS = {
    "seed": 1,
    "cast": {"builder": "fritz"},
    "feet": [0.17, -3.15], "z": 0.25, "scale": 0.45,
    "set": {"back": "set/vibe.png", "front": "set/vibe_table.png"}, "background": "#0b1230",
    "light": {"tint": [0.70, 0.78, 1.0], "rim": [1.0, 0.35, 0.85]},
    "voices": {"builder": {"audio": "voice/builder.wav"}, "narrator": {"audio": "voice/narrator.wav"},
               "builder2": {"audio": "voice/builder2.wav"}},
    "neon": "VIBE CODING",
    "word_panels": [["code", "CODE", "code"], ["test", "TEST", "test"], ["app", "ITERATE", "iterate"],
                    ["rocket", "SHIP", "ship"]],                 # the last one takes off
    "app_panels": ["bars", "line", "surface", "wafer", "app", "check"],
    "prompt": "> build me a wafer dashboard",
    "words": {"describe": "describe", "minutes": "minutes", "works": "works", "expertise": "expertise"},
    "lead": 14,
}


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    bu = P["cast"]["builder"]
    V, Wd = P["voices"], P["words"]
    S = SC.Scene(folder, seed=P["seed"], background=P["background"])
    S.narration("builder", V["builder"]["audio"], P["lead"], speaker=bu, text=V["builder"].get("text"))
    S.narration("narrator", V["narrator"]["audio"], {"line": "builder", "edge": "end", "offset": 6},
                text=V["narrator"].get("text"))
    S.narration("builder2", V["builder2"]["audio"], {"line": "narrator", "edge": "end", "offset": 6}, speaker=bu,
                text=V["builder2"].get("text"))
    T = S.T
    N1, NE, N2 = T.line_at("builder"), T.line_at("narrator"), T.line_at("builder2")
    E1 = T({"line": "builder", "edge": "end"})
    G = T({"line": "builder2", "edge": "end"}) + 8                     # glitch gag
    END = G + 22
    S.end = END
    WP = [(k, t, T({"line": "builder", "word": w})) for k, t, w in P["word_panels"]]
    T_CODE, T_TEST, T_ITER, T_SHIP = [x[2] for x in WP[:4]]
    T_DESC, T_MIN, T_WORKS, T_EXP = (T({"line": "narrator", "word": Wd[k]}) for k in ("describe", "minutes", "works", "expertise"))
    KEYS = list(range(2, N1, 2)) + list(range(T_WORKS - 30, T_WORKS, 2))
    T_START = T_SHIP + 8                                               # the rocket takes off
    SU, Z = P["scale"], P["z"]
    FX, FY = P["feet"]
    tap = [(f, 2 if i % 2 else -1) for i, f in enumerate(range(2, N1 - 1, 3))]
    tap2 = [(f, 2 if i % 2 else -1) for i, f in enumerate(range(T_WORKS - 30, T_WORKS, 3))]
    K = {"head": [(0, 0)] + tap + [(N1, 0), (T_CODE, 3), (T_TEST, -3), (T_ITER, 3), (T_SHIP, -2), (E1 + 6, 0)]
         + tap2 + [(T_WORKS, 0), (T_WORKS + 6, 3), (N2 - 10, 0), (N2, 4, "halt"), (G, 4), (G + 3, -2),
                   (G + 12, -1), (END, -1)],
         "eyes": [(0, (0, -0.08)), (N1 - 2, (0, -0.08)), (N1 + 4, (0, 0)), (T_CODE, (-0.09, 0.05)),
                  (T_TEST, (-0.04, 0.08)), (T_ITER, (0.04, 0.08)), (T_SHIP, (0.09, 0.05)), (T_START + 4, (0.06, 0.1)),
                  (NE - 2, (0, 0)), (T_DESC, (0, -0.08)), (T_WORKS, (0, -0.08)), (T_WORKS + 4, (0.05, 0.08)),
                  (N2 - 6, (0.05, 0.08)), (N2, (0.02, 0.1)), (G, (0.02, 0.1)), (G + 3, (-0.07, 0.09)), (END, (-0.07, 0.09))],
         "blink": [(0, 1), (N1 + 30, 1), (N1 + 32, 0.1), (N1 + 35, 1), (T_WORKS + 16, 1), (T_WORKS + 18, 0.1),
                   (T_WORKS + 21, 1), (N2 + 4, 1), (N2 + 10, 0.55, "halt"), (G, 0.55), (G + 2, 1.0), (END, 1.0)],
         "sq": [(0, (1, 1)), (T_SHIP - 4, (1, 1)), (T_SHIP, (1.06, 0.93)), (T_SHIP + 5, (0.95, 1.07), "halt"),
                (T_SHIP + 14, (1, 1)), (G, (1, 1)), (G + 2, (1.04, 0.95)), (G + 6, (0.98, 1.02)), (G + 10, (1, 1))],
         "tilt": [(0, 0), (N2 - 4, 0), (N2 + 12, 5, "halt"), (G, 5), (G + 4, 1.5), (END, 1.5)],
         "gesture": [(0, 4), (T_SHIP - 2, 4), (T_SHIP + 4, 9.5), (T_SHIP + 18, 5)],
         "follow": [(0, 0), (T_SHIP, 0), (T_SHIP + 5, 5), (T_SHIP + 11, -4), (T_SHIP + 17, 2), (T_SHIP + 23, 0)]}
    S.painted_set(P["set"]["back"], P["set"].get("front"))
    S.figure(bu, x=FX, y=FY, z=Z, scale=SU, order=10, keys=K, tint=P["light"]["tint"], rim=P["light"]["rim"])
    tex = folder / "tex"
    tex.mkdir(exist_ok=True)
    S.sprite("neon", "tex/neon.png", PR.neon(P["neon"], tex / "neon.png", height=240), 0.8, order=2, add=True)
    S.sprite("flash", "tex/flash.png", PR.key_flash(tex / "flash.png"), 0.3, order=41, add=True)
    S.sprite("prompt", "tex/prompt.png", PR.holo("prompt", tex / "prompt.png", W=900, H=260, prompt=P["prompt"]), 1.0,
             order=50)
    pos = [(-3.6, 1.5), (-1.3, 2.4), (1.5, 2.4), (3.8, 1.5)]
    for i, (k, t, _) in enumerate(WP):
        last = i == len(WP) - 1
        a = PR.holo(k, tex / f"w_{i}.png", title=t, colour=(255, 90, 210) if last else (60, 230, 230))
        S.sprite(f"w_{i}", f"tex/w_{i}.png", a, 1.6, order=45 + i)
    APP = P["app_panels"]
    for i, k in enumerate(APP):
        S.sprite(f"a_{i}", f"tex/a_{i}.png", PR.holo(k, tex / f"a_{i}.png"), 1.3, order=55 + i)
    cam_k = [(0, [0, 0.5, 13.4, 0, 0.5, 0]), (N1 + 8, [0, 0.4, 11.4, 0.1, 0.5, 0]),
             (T_DESC + 6, [0.2, 0.4, 11.0, 0.1, 0.6, 0]), (T_WORKS + 10, [-0.3, 0.3, 10.6, 0.1, 0.6, 0.5]),
             (N2 + 4, [-0.3, 0.0, 8.6, FX, 0.1, 0.5]), (G, [-0.25, 0.0, 8.1, FX, 0.1, 0.5]),
             (G + 5, [-0.25, 0.05, 8.5, FX, 0.15, 0.5]), (END, [-0.2, 0.05, 8.3, FX, 0.15, 0.5])]
    S.camera(cam_k)

    def stage(f, F):
        sp = F["sprites"]
        flick = 1.0 if f > 12 else (1.0 if (f // 3) % 3 and f > 3 else 0.15)
        sp["neon"] = {"p": [-0.2, 3.75, 0.05], "s": 1, "a": round(flick * (0.92 + 0.08 * math.sin(f * 0.7)), 3)}
        sp["flash"] = {"p": [FX + 0.2 * (1 if f % 4 < 2 else -1), -0.95, 0.6],
                       "s": 1.0 if any(0 <= f - t < 2 for t in KEYS) else 0, "a": 1}
        for i, (k, t, t0) in enumerate(WP):
            px, py = pos[i % len(pos)]
            if i == len(WP) - 1:                                       # gag: the rocket takes off
                s, a = SC.pop(f, t0, END + 20, rise=6, overshoot=0.25)
                u = max(0.0, (f - T_START) / 24)
                py = py + 30 * u * u - (0.12 * math.sin(min(1.0, (f - T_START + 6) / 6) * math.pi)
                                        if T_START - 6 <= f < T_START else 0)
                px = px + 0.05 * math.sin(f * 2.1) * (u > 0)
                if py > 7:
                    a = 0.0
            else:
                s, a = SC.pop(f, t0, T_DESC - 6, rise=6, overshoot=0.25)
            sp[f"w_{i}"] = {"p": [round(px, 3), round(py + 0.06 * math.sin(f * 0.12 + px), 3), 0.9], "s": s, "a": a}
        s, a = SC.pop(f, T_DESC, T_WORKS - 4, rise=8)
        sp["prompt"] = {"p": [FX, 2.6, 1.0], "s": s, "a": a}
        orbit = 0 if f < T_WORKS else (f - T_WORKS) / 24 * 0.35
        for i in range(len(APP)):
            s, a = SC.pop(f, T_MIN + 6 + 5 * i, END + 20, rise=7, overshoot=0.3)
            ang = -2.6 + i * 1.04 + orbit
            dim = 1.0 if f < T_EXP else 0.75 + 0.25 * math.cos((f - T_EXP) * 0.08)
            x, y, z = FX + 4.1 * math.cos(ang), 2.05 + 0.8 * math.sin(ang), 1.0 + 0.9 * math.sin(ang)
            if G <= f < G + 9:                                         # glitch gag
                x += 0.18 * math.sin(f * 7.3 + i * 2.1)
                y += 0.06 * math.cos(f * 5.1 + i)
                dim *= 0.35 if (f + i) % 3 == 0 else 1.0
            sp[f"a_{i}"] = {"p": [round(x, 3), round(y, 3), round(z, 3)], "s": s, "a": round(a * dim, 3)}
    S.per_frame(stage)
    S.sound(3, "glitch/mid", level=-26)
    S.sound(10, "glitch/chirp", level=-28)
    for f in KEYS:
        S.sound(f, "fit/key/medium", level=-30)
    notes = ["E5", "G5", "B5", "E6", "G6", "B6"]
    for i, (_, _, f) in enumerate(WP):
        S.sound(f, "mallet/glock", ["--pitch", notes[i % 6]], level=-21, pan=-0.6 + 0.4 * i)
        S.sound(f + 1, "ui_pop/wide", level=-25)
    S.sound(T_START - 2, "whoosh_fast/whistle", level=-22, pan=0.5)
    S.sound(T_START, "pro_zip/up_hi", level=-26, pan=0.5)
    S.sound(T_DESC, "hover_tick/ping", level=-24)
    for i in range(len(APP)):
        S.sound(T_MIN + 6 + 5 * i, "mallet/celesta", ["--pitch", ["C5", "E5", "G5", "C6", "E6", "G6"][i % 6]], level=-22)
    S.sound(T_WORKS + 12, "logo_sting/spark", level=-22)
    S.sound(N2, "downlifter/air_fall", level=-28, align="start")
    S.sound(G, "glitch/stutter", level=-22)
    S.sound(G + 2, "fit/pop/lip_pop", level=-24)
    S.build()
    SC.save_events(folder, {"lines": {"builder": N1, "narrator": NE, "builder2": N2}, "neon": 3, "rocket": T_START,
                            "glitch": G, "word_panels": [x[2] for x in WP], "prompt": T_DESC,
                            "app": [T_MIN + 6 + 5 * i for i in range(len(APP))], "works": T_WORKS, "lean_back": N2,
                            "end": END})
    return S


if __name__ == "__main__":
    S = main(sys.argv[1])
    if "--plan" not in sys.argv:
        S.render()
