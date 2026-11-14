# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# ///
"""Recipe "drifting islands" - four figures on island dioramas drift apart and are called back one by one
(reference: ai_efficiency S10 + S11, one continuous shot).

Four islands (round floor plate + set wall + sign + figure), e.g. one room per figure.
  apart    islands stand close together -> on a keyword they drift apart, the walls grow, colour fades, the figures
           look around searching; a title card + key figures over the blurred picture (post)
  calls    one narrator line per figure: a spotlight + a reaction (arm up / tail wags / wing up / looks up);
           camera pans to each island
  together on each name in the last line an island slides back and snaps in - gag: the cautious one only slides half
           way, hesitates, watches the others and then rushes after ("thump", the neighbour wobbles); colour returns,
           everybody hops
Inputs: seven narrator lines, one set image per island. Vary in recipe.json: cast, island order, names (as spoken),
signs, floor tones, title card + figures, words, voices, walls, seed.
Run: uv run s10_islands.py <clip folder> [--plan]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import props as PR  # noqa: E402
import scene as SC  # noqa: E402

DEFAULTS = {
    "seed": 1,
    "cast": {"guardian": "helmut", "guide": "hans", "explorer": "felix", "builder": "fritz"},
    "order": ["guardian", "guide", "explorer", "builder"],           # islands left -> right
    "calls": ["guardian", "guide", "builder", "explorer"],           # order of the narrator's calls
    "hesitant": "guardian",                                          # the one that only slides half way at first
    "names": {"guardian": "helmut", "guide": "hans", "explorer": "felix", "builder": "fritz"},   # as spoken
    "first_name": "builder",                                         # "... become <name>": the others glance at them
    "signs": {"guardian": "Traditional Engineering", "guide": "Prompt Studio", "explorer": "Coding & Agent Buro",
              "builder": "Vibe Coding Office"},
    "walls": {r: f"set/wall_{r}.png" for r in ("guardian", "guide", "explorer", "builder")},
    "tones": {"guardian": [244, 242, 234], "guide": [236, 244, 240], "explorer": [240, 240, 246],
              "builder": [226, 228, 244]},
    "z_off": {"guardian": -0.6, "guide": 0.5, "explorer": -0.3, "builder": 0.6},
    "voices": {k: {"audio": f"voice/{k}.wav"} for k in ("apart", "team", "call_guardian", "call_guide",
                                                        "call_builder", "call_explorer", "together")},
    "words": {"drift": "offices", "walls": "tools", "alone": "rarely", "team": "team", "figures": "familiar",
              "data": "data", "color": "working", "hop": "together"},
    "texts": {"title": "Could this be your team?",
              "figures": [[">", 600, "", "users of GitHub Copilot"], ["<", 25, "%", "use more than 30K tokens a month"]],
              "note": "1 hour of meeting transcript  ≈  15,000 tokens"},
    "gap": 8, "near": 4.5, "far": 6.2, "scale": 0.27, "floor": -2.2, "background": "#2a2724",
}


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    R, V, Wd = P["cast"], P["voices"], P["words"]
    ORDER = [R[r] for r in P["order"]]
    role = {v: k for k, v in R.items()}
    S = SC.Scene(folder, seed=P["seed"], background=P["background"])
    gap = P["gap"]
    S.narration("apart", V["apart"]["audio"], 12, text=V["apart"].get("text"))
    S.narration("team", V["team"]["audio"], {"line": "apart", "edge": "end", "offset": gap}, text=V["team"].get("text"))
    prev = ("team", 30)
    for r in P["calls"]:
        lid = f"call_{r}"
        S.narration(lid, V[lid]["audio"], {"line": prev[0], "edge": "end", "offset": prev[1]}, text=V[lid].get("text"))
        prev = (lid, gap)
    S.narration("together", V["together"]["audio"], {"line": prev[0], "edge": "end", "offset": gap},
                text=V["together"].get("text"))
    T = S.T
    N10b = T.line_at("team")
    N11 = {R[r]: T.line_at(f"call_{r}") for r in P["calls"]}
    CALL_END = {R[r]: T({"line": f"call_{r}", "edge": "end"}) for r in P["calls"]}
    NALL = T.line_at("together")
    E_ALL = T({"line": "together", "edge": "end"})
    END = E_ALL + 24
    S.end = END
    T_OFF, T_TOOLS, T_RARE = (T({"line": "apart", "word": Wd[k]}) for k in ("drift", "walls", "alone"))
    T_TEAM, T_FAM, T_DATA = (T({"line": "team", "word": Wd[k]}) for k in ("team", "figures", "data"))
    T_NAME = {R[r]: T({"line": "together", "word": P["names"][r], "nth": -1}) for r in P["order"]}
    T_FIRST = T({"line": "together", "word": P["names"][P["first_name"]]})
    T_WORK, T_TOG = T({"line": "together", "word": Wd["color"]}), T({"line": "together", "word": Wd["hop"]})
    DRIFT, SNAP = 40, 8
    hes = R[P["hesitant"]]
    HALF = 0.55
    last_call = R[P["calls"][-1]]
    H_GO = max(T_NAME[n] for n in ORDER if n != hes) + SNAP - 2     # the hesitant one rushes after the others
    H_LAND = H_GO + 6
    NEAR, FAR, SU, FLOOR = P["near"], P["far"], P["scale"], P["floor"]
    first = R[P["first_name"]]

    def back(n, f):
        """0 = apart, 1 = snapped in again; plus an overshoot -> (u, wobble)"""
        if n == hes:
            u = HALF * SC.smooth((f - T_NAME[n]) / SNAP) + (1 - HALF) * SC.smooth((f - H_GO) / (H_LAND - H_GO))
            t = f - H_LAND
            return u, (-0.22 * math.sin(t * 0.7) * math.exp(-t / 5) if t > 0 else 0.0)
        u = SC.smooth((f - T_NAME[n]) / SNAP)
        t = f - T_NAME[n] - SNAP
        return u, (-0.12 * math.sin(t * 0.8) * math.exp(-t / 4) if t > 0 else 0.0)

    def island_x(n, f):
        sep = NEAR + (FAR - NEAR) * SC.smooth((f - T_OFF) / DRIFT)
        if f > T_NAME[n]:
            u, w = back(n, f)
            sep = FAR + (NEAR - FAR) * u + w
        return (ORDER.index(n) - 1.5) * sep

    def island_z(n, f):
        return P["z_off"][role[n]] * SC.smooth((f - T_OFF) / DRIFT) * (1 - back(n, f)[0])

    def wall_h(f):
        return 2.4 + 1.1 * SC.smooth((f - T_TOOLS) / 36) * (1 - SC.smooth((f - T_WORK) / 20))

    K = {}
    for n in ORDER:
        side = [] if n == first else [(T_FIRST + 2, (0.09, 0.01)), (T_FIRST + 14, (0.09, 0.01))]
        if n == hes:
            end_k = [(T_NAME[n] + 4, (0.09, 0.0)), (H_GO - 2, (0.09, 0.0)), (H_GO + 2, (0, 0.08)), (H_LAND + 8, (0, 0))]
        else:
            end_k = [(T_NAME[n], (0.02, 0.06)), (T_NAME[n] + 10, (0, 0))]
        k = {"eyes": [(0, (0, 0)), (T_OFF + 12, (-0.08, 0)), (T_OFF + 30, (0.08, 0)), (T_OFF + 48, (0, -0.06)),
                      (T_RARE, (0, -0.07)), (N11[n] - 4, (0, -0.07)), (N11[n] + 2, (0.02, 0.09)),
                      (CALL_END[n], (0.02, 0.06))] + side + end_k,
             "head": [(0, 0), (T_OFF + 12, 3), (T_OFF + 30, -3), (T_RARE, -2), (T_RARE + 30, 2), (T_RARE + 44, -3),
                      (N11[n] - 4, -2), (N11[n] + 6, 3), (CALL_END[n], 1), (T_WORK, 0)]}
        hop = SC.steps(T_TOG - 2, T_TOG + 22, 2, height=1.3, squash=0.16, rock=0)
        k["pos"] = [(0, (0, 0))] + hop["pos"]
        k["sq"] = [(0, (1, 1)), (N11[n] - 2, (1, 1)), (N11[n] + 4, (0.95, 1.07), "halt"), (N11[n] + 20, (1, 1))]
        nb = ORDER[ORDER.index(hes) + (1 if ORDER.index(hes) < 3 else -1)]
        if n == nb:                                                  # thump: the hesitant island bumps -> wobble
            k["sq"] += [(H_LAND, (1, 1)), (H_LAND + 2, (1.08, 0.92)), (H_LAND + 4, (0.96, 1.05)),
                        (min(H_LAND + 7, T_TOG - 3), (1, 1))]
        if n == first:                                               # "become <name>": a small proud pop
            k["sq"] += [(T_FIRST, (1, 1)), (T_FIRST + 3, (0.94, 1.08)), (T_FIRST + 10, (1, 1))]
        k["sq"] += hop["sq"]
        k["sq"] = sorted(k["sq"], key=lambda x: x[0])
        K[n] = k
    gu, ex, bu, ga = R["guide"], R["explorer"], R["builder"], R["guardian"]
    K[gu]["follow"] = [(0, 0), (T_OFF, 0), (T_OFF + 20, -7), (N11[gu], -7)] + \
        [(N11[gu] + 4 + 6 * i, 7 if i % 2 else -7) for i in range(14)] + [(T_TOG, 0)] + \
        [(T_TOG + 6 * i, 7 if i % 2 else -7) for i in range(1, 8)]
    K[ex]["gesture"] = [(0, 0), (N11[ex], 0), (N11[ex] + 8, 10, "halt"), (N11[ex] + 40, 10),
                        (N11[ex] + 50, 0), (T_TOG - 2, 0), (T_TOG + 6, 10), (T_TOG + 30, 0)]
    K[bu]["gesture"] = [(0, 4), (N11[bu], 4), (N11[bu] + 6, 9.5), (CALL_END[bu], 9), (CALL_END[bu] + 10, 4),
                        (T_TOG, 4), (T_TOG + 6, 9.5), (T_TOG + 26, 5)]
    K[ga]["blink"] = [(0, 1), (T_RARE, 1), (T_RARE + 6, 0.6, "halt"), (N11[ga], 0.6), (N11[ga] + 4, 1),
                      (N11[ga] + 40, 1), (N11[ga] + 42, 0.1), (N11[ga] + 45, 1)]
    tex = folder / "tex"
    tex.mkdir(exist_ok=True)
    WW = 4.3
    S.layer("floor", "tex/floor.png", 90, 50, z=0, order=0, rotx=-math.pi / 2)
    a_cone = PR.light_cone(tex / "cone.png")
    PR.star_eye(tex / "sparkle.png")
    for i, n in enumerate(ORDER):
        r = role[n]
        PR.island_floor(tex / f"floor_{r}.png", tuple(P["tones"][r]))
        S.layer(f"floor_{r}", f"tex/floor_{r}.png", 4.6, 4.6, z=0, order=1 + i * 0.01, rotx=-math.pi / 2)
        S.layer(f"wall_{r}", P["walls"][r], WW, WW / 1.765, z=0, order=2 + i * 0.01)
        S.figure(n, x=island_x(n, 0), y=FLOOR, z=-0.1, scale=SU, order=10 + i, keys=K[n], shadow=0.45)
        S.sprite(f"sign_{r}", f"tex/sign_{r}.png", PR.sign(P["signs"][r], tex / f"sign_{r}.png", height=180), 0.42, order=3)
        S.sprite(f"cone_{r}", "tex/cone.png", a_cone, 5.4, order=30, add=True)
    S.sprite("sparkle", "tex/sparkle.png", 1, 0.35, order=40, add=True)
    ga_eye = S.eye_center(ga)[1]

    top, wide = [0, 3.0, 19.5, 0, -0.6, 0], [0, 3.4, 25.0, 0, -0.5, 0]
    cam_k = [(0, top), (T_OFF - 4, top), (T_OFF + 40, [-1.6, 3.5, 25.6, -0.4, -0.5, 0]),
             (N10b, [1.2, 3.2, 23.6, 0.3, -0.5, 0]), (N11[R[P["calls"][0]]] - 8, wide)]
    for r in P["calls"]:
        n = R[r]
        x = (ORDER.index(n) - 1.5) * FAR
        cam_k += [(N11[n] + 6, [x * 0.92, 1.4, 8.6, x, -0.8, 0]), (CALL_END[n] - 4, [x * 0.92, 1.3, 8.0, x, -0.8, 0])]
    cam_k += [(NALL + 10, wide), (T_TOG, [0, 2.8, 20.0, 0, -0.6, 0]), (END, [0, 2.6, 19.2, 0, -0.6, 0])]
    S.camera(cam_k)

    def stage(f, F):
        wh = wall_h(f)
        lp = {"floor": [0, FLOOR - 0.01, 10, 1, 1]}
        for n in ORDER:
            r = role[n]
            x, z = island_x(n, f), island_z(n, f)
            lp[f"floor_{r}"] = [x, FLOOR + 0.01, z, 1, 1]
            lp[f"wall_{r}"] = [x, FLOOR + wh / 2, z - 1.5, 1, wh / (WW / 1.765)]
            F["figs"][n] = {"feet": [round(x, 4), FLOOR, round(z - 0.1, 4)], "shade": 1, "soft": 0.45}
            F["sprites"][f"sign_{r}"] = {"p": [x, FLOOR + wh + 0.35, z - 1.45], "s": 1, "a": 1}
            on = SC.smooth((f - N11[n] + 4) / 8) * (1 - SC.smooth((f - CALL_END[n] - 10) / 16))
            on = max(on, 0.6 * SC.smooth((f - T_TOG) / 20))
            F["sprites"][f"cone_{r}"] = {"p": [x, FLOOR + 2.4, z + 0.2], "s": 1, "a": round(on, 3)}
        F["lpos"] = {k: [round(v, 4) for v in vv] for k, vv in lp.items()}
        s_, a_ = SC.pop(f, N11[ga] + 26, N11[ga] + 40, rise=4, overshoot=0.4)
        F["sprites"]["sparkle"] = {"p": [island_x(ga, f) + 0.25, FLOOR + ga_eye * SU + 0.2, island_z(ga, f) + 0.4],
                                   "s": s_, "a": a_, "rot": f * 0.2}
    S.per_frame(stage)
    tx = P["texts"]
    S11 = N11[R[P["calls"][0]]] - 10

    def grade(f, im):
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
        sat = 1 - 0.75 * SC.smooth((f - T_OFF) / 100) + 0.75 * SC.smooth((f - T_WORK) / 20)
        light = 1 - 0.18 * SC.smooth((f - T_OFF) / 100) + 0.18 * SC.smooth((f - T_WORK) / 20)
        im = ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(sat)).enhance(light)
        a = SC.smooth((f - T_TEAM + 10) / 10) * (1 - SC.smooth((f - S11 + 12) / 12))
        if a > 0.001:                                                  # title card over the blurred picture
            blur = im.filter(ImageFilter.GaussianBlur(10 * a))
            im = Image.blend(im, ImageEnhance.Brightness(blur).enhance(0.45), a)
            d = ImageDraw.Draw(im)
            d.text((960, 300 if f > T_FAM else 520), tx["title"], font=PR.font("bold", 92),
                   fill=(int(250 * a), int(249 * a), int(244 * a)), anchor="mm")
            if f > T_FAM:
                u = SC.smooth((f - T_FAM) / 30)
                b = SC.smooth((f - T_FAM) / 10) * a
                c1 = (int(0x8F * b), int(0xC9 * b), int(0xA9 * b))
                wc = (int(240 * b), int(240 * b), int(236 * b))
                nfig = len(tx["figures"])
                for i, (pre, num, post, label) in enumerate(tx["figures"]):
                    x = 960 + (i - (nfig - 1) / 2) * 720
                    d.text((x, 560), f"{pre}{int(num * u)}{post}", font=PR.font("bold", 170), fill=c1, anchor="mm")
                    d.text((x, 690), label, font=PR.font("regular", 50), fill=wc, anchor="mm")
                if tx.get("note"):
                    d.text((960, 840), tx["note"], font=PR.font("regular", 40),
                           fill=(int(200 * b), int(200 * b), int(196 * b)), anchor="mm")
        return im
    S.post(grade)
    S.sound(T_OFF, "downlifter/sub_sink", level=-24, align="start")
    S.sound(T_OFF + 20, "whoosh_big/deep", ["--dur", "1.4", "--apex", "0.7"], level=-26)
    S.sound(T_TEAM, "impact/deep", level=-22)
    for k, f in enumerate([T_DATA + 4, T_DATA + 10]):
        S.sound(f, "mallet/glock", ["--pitch", ["A5", "E6"][k]], level=-24)
    for r in P["calls"]:
        S.sound(N11[R[r]] - 4, "fit/snap/switch_flip", level=-22)
        S.sound(N11[R[r]], "logo_sting/soft_bloom", level=-26, align="start")
    for i, r in enumerate(P["calls"]):
        S.sound(CALL_END[R[r]] + 5, "whoosh_fast/tight", ["--dur", "0.5", "--apex", "0.25"], level=-25 - 2 * (i == 3),
                pan=0.3 if i != 1 else 0.5)
    pan = {n: -0.6 + 0.4 * i for i, n in enumerate(ORDER)}
    S.sound(T_NAME[hes] + 4, "whoosh_fast/tight", ["--dur", "0.4", "--apex", "0.2"], level=-29, pan=pan[hes])
    rest = sorted((n for n in ORDER if n != hes), key=lambda n: T_NAME[n])
    for i, n in enumerate(rest):
        S.sound(T_NAME[n] + SNAP // 2, "whoosh_fast/tight", ["--dur", "0.4", "--apex", "0.2"], level=-24, pan=pan[n])
        S.sound(T_NAME[n] + SNAP, "fit/hit/bamboo_tok", level=-19, pan=pan[n])
        S.sound(T_NAME[n] + SNAP + 1, "mallet/marimba", ["--pitch", ["E5", "G5", "C6"][i % 3]], level=-22, pan=pan[n])
    S.sound(H_LAND - 1, "whoosh_fast/whistle", ["--dur", "0.45", "--apex", "0.3"], level=-24, pan=-0.5)
    S.sound(H_LAND, "knock/double", level=-19, pan=-0.4)
    S.sound(H_LAND + 1, "mallet/marimba", ["--pitch", "C4"], level=-21, pan=-0.4)
    S.sound(T_FIRST + 2, "ui_pop/blip", level=-28, pan=0.3)
    S.sound(T_FIRST + 4, "ui_pop/boop", level=-27, pan=0.6)
    S.sound(T_WORK, "logo_sting/reverse_bloom", level=-20, align="start")
    for k in range(4):
        S.sound(T_TOG + 2 + 12 * (k % 2), "ui_pop/soft", ["--pitch", ["C4", "E4", "G4", "C5"][k]], level=-24,
                pan=-0.6 + 0.4 * k)
    S.build()
    SC.save_events(folder, {"lines": {ln["id"]: T.line_at(ln["id"]) for ln in S.p["narration"]}, "drift": T_OFF,
                            "walls": T_TOOLS, "team": T_TEAM, "figures": T_FAM, "data": T_DATA, "calls": N11,
                            "back": T_NAME, "colour": T_WORK, "hop": T_TOG, "hesitant_go": H_GO,
                            "hesitant_land": H_LAND, "first_name": T_FIRST, "end": END})
    return S


if __name__ == "__main__":
    S = main(sys.argv[1])
    if "--plan" not in sys.argv:
        S.render()
