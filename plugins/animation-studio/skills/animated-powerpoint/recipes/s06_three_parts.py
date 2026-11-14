# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# ///
"""Recipe "hall - office - machine" - one clip in three parts with their own sets, joined with hard cuts
(reference: ai_efficiency S6 "Coding & Agent office").

  A hall     the builder hops past three doors, one door lights up - gag: overshoots, stops (glance back), slides
             back and jumps into the light (fades into the door gap, flash)
  B office   the builder hops in, already calling out the news (lip sync) -> a big check sign with confetti, builder and
             explorer jump for joy; gag: in the guardian's close-up a single confetti sails down in front of the face,
             the eyes follow it dryly - then the guardian's doubt; the guide's line (close-up)
  C machine  narrator; a document travels through five stations on a conveyor, two bots work in parallel, findings
             with evidence arrive with a check, findings without fly into the bin - gag: the second bounces off the rim
             first; counters roll up
Inputs: four voice files, the hall set (one image), the office set (back + table). Vary in recipe.json: cast, door
signs, check text, stations, counters, words, voices, sets, seed.
Run: uv run s06_three_parts.py <clip folder> [--plan]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import props as PR  # noqa: E402
import scene as SC  # noqa: E402

DEFAULTS = {
    "seed": 1,
    "cast": {"builder": "fritz", "explorer": "felix", "guardian": "helmut", "guide": "hans"},
    "x": {"guardian": -5.2, "guide": -2.1, "builder": 1.0, "explorer": 4.3}, "feet_y": -2.55, "z": 0.25, "scale": 0.45,
    "set": {"hall": "set/hall.png", "back": "set/office.png", "front": "set/table.png", "steam": [[1008, 590]]},
    "doors": [[630, 300, "Traditional Office"], [995, 300, "QA Lab"], [1405, 300, "Coding & Agent Buro"]],
    "voices": {"builder": {"audio": "voice/builder.wav"}, "guardian": {"audio": "voice/guardian.wav"},
               "guide": {"audio": "voice/guide.wav"}, "narrator": {"audio": "voice/narrator.wav"}},
    "words": {"cheer": "worked", "doubt": "accurate", "safe": "safe"},
    "texts": {"check": "BUILD\nSUCCESSFUL", "title": "AI-assisted code review",
              "stations": [["PR opened", "Jenkins CI"], ["Understand & plan", "deep reasoning"],
                           ["Investigate", "2 parallel agents"], ["Validate", "deep reasoning"],
                           ["Verify & publish", "deterministic checks"]],
              "station_x": [230, 590, 960, 1330, 1690], "document": "PR", "bin": "no evidence -> discarded", "pass": "evidence + code anchor",
              "counters": [[42, "repositories", ""], [350, "pull requests", "~"], [3000, "review comments", "~"]]},
}
A_END = 99


def part_a(folder, P):
    bu = P["cast"]["builder"]
    S = SC.Scene(folder / "a_hall", deck="../../../deck/deck.json", figures_dir="../../../figures", end=A_END,
                 seed=P["seed"], look="none")
    S.painted_set("../" + P["set"]["hall"])
    tex = S.dir / "tex"
    tex.mkdir(exist_ok=True)
    doors = [(*S.set_point(px, py), t) for px, py, t in P["doors"]]
    for i, (_, _, t) in enumerate(doors):
        S.sprite(f"sign{i}", f"tex/sign{i}.png", PR.sign(t, tex / f"sign{i}.png", height=200), 0.42, order=2)
    a_light = PR.soft_light(tex / "light.png")
    S.sprite("light", "tex/light.png", a_light, 4.2, order=3)
    S.sprite("flash", "tex/light.png", a_light, 3.0, order=90)
    START_X, GOAL_X, FY, Z = -9.5, doors[-1][0] - 0.158, -2.6, 0.35
    H0, H1, STOP, SLIDE, JUMP = 4, 56, 58, 60, 70
    s = SC.steps(H0, H1, 6, height=0.9, squash=0.14, rock=4)
    K = {"pos": s["pos"] + [(JUMP + 2, (0, 0)), (JUMP + 4, (0, -0.15)), (JUMP + 10, (0, 1.6), "halt"),
                            (JUMP + 20, (0, 0.6))],
         "sq": s["sq"] + [(SLIDE + 4, (1.06, 0.95)), (SLIDE + 8, (1, 1)), (JUMP, (1.12, 0.86), "halt"),
                          (JUMP + 5, (0.84, 1.22)), (JUMP + 16, (0.9, 1.1))],
         "tilt": s["tilt"] + [(SLIDE + 2, 5), (SLIDE + 8, 0), (JUMP + 4, -6), (JUMP + 14, -12)],
         "eyes": [(0, (0.09, 0)), (H1, (0.09, 0)), (STOP, (-0.09, 0.02)), (SLIDE + 6, (-0.09, 0.02)),
                  (SLIDE + 9, (0.06, 0.05))],
         "head": [(0, -2), (30, 0), (50, 3), (H1, 3), (STOP + 1, -4), (SLIDE + 7, -4), (JUMP + 2, -2)],
         "follow": [(f, 5 if i % 2 else -5) for i, f in enumerate(range(H0, H1, 9))]
                   + [(STOP, 8), (SLIDE + 4, -5), (JUMP + 8, 8), (JUMP + 20, -6)],
         "gesture": [(0, 4), (40, 9), (H1, 9), (SLIDE, 4), (SLIDE + 8, 9)]}
    S.figure(bu, x=START_X, y=FY, z=Z, scale=0.30, order=10, keys=K, shadow=0.3)
    OVER = 0.9                                                   # how far the builder overshoots the door

    def stage(f, F):
        x = START_X + (GOAL_X + OVER - START_X) * SC.smooth((f - H0) / (H1 - H0)) if f <= H1 else \
            GOAL_X + OVER * (1 - SC.smooth((f - SLIDE) / 8))
        z, op = Z, 1.0
        if f > JUMP + 4:                                         # into the light gap
            v = SC.smooth((f - JUMP - 4) / 16)
            z, op = Z - 0.6 * v, 1 - v
        cx = min(max(x, -2.8), 2.6)
        cam = [cx, -0.55, 10.8 - 1.6 * SC.smooth((f - JUMP + 4) / 34)]
        look = [cx + 0.2, -1.1, 0]
        if f > JUMP - 4:
            cam[0] = cx + 0.9 * SC.smooth((f - JUMP + 4) / 26)
            look[0] = cam[0] + 0.2
        F["cam"], F["look"] = [round(v, 4) for v in cam], [round(v, 4) for v in look]
        F["figs"][bu] = {"feet": [round(x, 4), FY, round(z, 4)], "shade": 1, "opacity": round(op, 3), "soft": 0.3 * op}
        for i, (tx, ty, _) in enumerate(doors):
            F["sprites"][f"sign{i}"] = {"p": [tx, ty, 0.03], "s": 1, "a": 1}
        lz = SC.smooth((f - 40) / 12)
        fl = max(0.0, 1 - abs(f - JUMP - 18) / 10) if f > JUMP + 8 else 0
        F["sprites"]["light"] = {"p": [doors[-1][0], -0.5, 0.05], "s": 1 + 0.5 * fl, "a": round(min(1, lz + fl), 3)}
        F["sprites"]["flash"] = {"p": [cam[0], cam[1], cam[2] - 1.2], "s": 1, "a": round(max(0.0, (fl - 0.3) * 1.4), 3)}
    S.per_frame(stage)
    for i in range(6):
        S.sound(round(H0 + i * (H1 - H0) / 6), "ui_pop/step", ["--pitch", "D4"], level=-26)
    S.sound(40, "riser/swell", level=-24, align="start")
    S.sound(JUMP + 4, "whoosh_fast/whip", ["--dur", "0.6", "--apex", "0.2"], level=-20)
    S.sound(JUMP + 16, "logo_sting/whoosh_glass", level=-19)
    S.sound(STOP, "pro_pop/chirp", level=-26, pan=0.3)
    S.sound(SLIDE, "swish/zing", ["--dur", "0.35", "--apex", "0.15"], level=-23, pan=0.2)
    S.sound(SLIDE + 8, "knock/wood", level=-28, pan=0.2)
    S.build()
    return S, {"jump": JUMP + 4, "light": 40, "stop": STOP, "slide": SLIDE}


def part_b(folder, P):
    R, V, Wd = P["cast"], P["voices"], P["words"]
    bu, ex, ga, gu = R["builder"], R["explorer"], R["guardian"], R["guide"]
    S = SC.Scene(folder / "b_office", deck="../../../deck/deck.json", figures_dir="../../../figures",
                 seed=P["seed"], look="none")
    S.narration("builder", "../" + V["builder"]["audio"], 12, speaker=bu, text=V["builder"].get("text"))
    S.narration("guardian", "../" + V["guardian"]["audio"], {"line": "builder", "edge": "end", "offset": 20},
                speaker=ga, text=V["guardian"].get("text"))
    S.narration("guide", "../" + V["guide"]["audio"], {"line": "guardian", "edge": "end", "offset": 6}, speaker=gu,
                text=V["guide"].get("text"))
    T = S.T
    N_F, N_HE, N_HA = (T.line_at(n) for n in ("builder", "guardian", "guide"))
    E_F, E_HE, E_HA = (T({"line": n, "edge": "end"}) for n in ("builder", "guardian", "guide"))
    END = E_HA + 14
    S.end = END
    T_KONF = N_HE - 18
    T_WORK = T({"line": "builder", "word": Wd["cheer"]})
    T_SAFE = T({"line": "guardian", "word": Wd["safe"]})
    T_ACC = T({"line": "guardian", "word": Wd["doubt"]})
    SU, FY, Z = P["scale"], P["feet_y"], P["z"]
    X = {R[r]: P["x"][r] for r in ("guardian", "guide", "builder", "explorer")}
    hop_in = SC.steps(0, 20, 3, height=0.8, squash=0.15, rock=-4)
    K = {bu: {"pos": hop_in["pos"] + [(T_WORK + 1, (0, 0)), (T_WORK + 6, (0, 0.5), "halt"), (T_WORK + 11, (0, 0))],
              "sq": hop_in["sq"] + [(T_WORK - 4, (1, 1)), (T_WORK, (1.08, 0.9)), (T_WORK + 5, (0.92, 1.1), "halt"),
                                    (T_WORK + 11, (1, 1)), (T_WORK + 12, (1.07, 0.94)), (T_WORK + 17, (1, 1))],
              "tilt": hop_in["tilt"],
              "gesture": [(0, 6), (N_F, 6), (N_F + 6, 9.5), (N_F + 20, 5), (T_WORK, 5), (T_WORK + 4, 9.5),
                          (T_WORK + 10, 4), (T_WORK + 16, 9.5), (E_F + 20, 5)],
              "head": [(0, 2), (N_F, 2), (N_F + 10, -3), (N_F + 40, 3), (T_WORK, -3), (E_F, 0),
                       (N_HE + 10, 0), (N_HE + 20, -3), (E_HA, -3), (E_HA + 10, 0)],
              "eyes": [(0, (-0.08, 0)), (N_F + 4, (-0.08, 0)), (N_F + 30, (-0.08, 0.02)), (E_F, (-0.08, 0))],
              "follow": [(0, 4), (10, -4), (20, 5), (30, 0), (T_WORK, 0), (T_WORK + 6, 6), (T_WORK + 12, -5),
                         (T_WORK + 18, 3), (T_WORK + 26, 0)]},
         ex: {"eyes": [(0, (0, 0)), (10, (-0.08, 0)), (E_F + 10, (-0.08, 0)), (N_HE, (-0.09, 0)), (E_HA, (-0.09, 0))],
              "pos": [(0, (0, 0)), (T_WORK + 4, (0, 0)), (T_WORK + 9, (0, 0.5), "halt"), (T_WORK + 14, (0, 0)),
                      (T_WORK + 18, (0, 0.25), "halt"), (T_WORK + 22, (0, 0))],
              "gesture": [(0, 0), (T_WORK + 2, 0), (T_WORK + 10, 10, "halt"), (T_WORK + 30, 10), (T_WORK + 42, 0)],
              "head": [(0, 0), (T_WORK + 2, 0), (T_WORK + 8, 4), (T_WORK + 30, 0)]},
         ga: {"eyes": [(0, (0, -0.07)), (12, (0.07, 0)), (T_KONF, (0.07, 0)), (T_KONF + 3, (0.01, 0.07)),
                       (N_HE - 3, (0.01, -0.08)), (N_HE + 3, (0.07, 0)), (E_HA, (0.07, 0))],
              "blink": [(0, 1), (N_HE - 2, 1), (N_HE, 0.4), (N_HE + 3, 1), (T_ACC, 1), (T_ACC + 4, 0.55, "halt"),
                        (E_HE, 0.55), (E_HE + 6, 1)],
              "head": [(0, -2), (12, 2), (T_WORK, 3), (T_KONF, 1), (N_HE - 3, -2), (N_HE + 2, 0), (N_HE + 10, -3),
                       (T_SAFE, 4), (E_HE, 0)]},
         gu: {"eyes": [(0, (0, 0)), (12, (0.08, 0)), (N_HE, (-0.08, 0)), (E_HE, (-0.08, 0)), (N_HA, (0.06, 0))],
              "head": [(0, 0), (T_WORK, 3), (N_HA, 0), (N_HA + 8, -4), (E_HA, 0)],
              "follow": [(0, 0), (T_WORK, 0)] + [(T_WORK + 4 + 5 * i, 6 if i % 2 else -6) for i in range(8)]
                        + [(T_WORK + 46, 0)]}}
    st = P["set"]
    S.painted_set("../" + st["back"], "../" + st["front"])
    for i, n in enumerate(X):
        path = [(0, [X[n] + 8.0, FY, Z]), (20, [X[n], FY, Z])] if n == bu else None
        S.figure(n, x=X[n], y=FY, z=Z, scale=SU, order=10 + i, keys=K[n], path=path)
    for px, py in st.get("steam", []):
        S.add_steam(*S.set_point(px, py, 0.5), 0.5)
    tex = S.dir / "tex"
    tex.mkdir(exist_ok=True)
    S.sprite("check", "tex/check.png", PR.check_sign(P["texts"]["check"], tex / "check.png"), 1.5, order=60)
    conf = PR.confetti_set(tex)
    burst = SC.confetti(T_WORK + 2, (X[bu] + 1.3, 1.0, 1.4), n=46, seed=6)
    for i in range(len(burst)):
        S.sprite(f"k{i}", conf[i % len(conf)], 1.6, 0.13, order=61)
    S.sprite("kh", conf[3 % len(conf)], 1.6, 0.17, order=62)
    eyes = {n: S.eye_center(n)[1] for n in X}
    ye_ga = FY + eyes[ga] * SU

    def close(n):
        y = FY + eyes[n] * SU - 0.35 + (0.35 if n == gu else 0)
        return [X[n] + 0.5, y + 0.15, Z + 5.4], [X[n], y, Z]
    wide = [0, 0.1, 15.4, 0, -0.1, 0]
    c_bu = [X[bu] + 0.6, 0.3, 9.6, X[bu] + 0.3, -0.2, 0.25]

    def stage(f, F):
        if f < T_KONF:
            c = SC.keyed([(0, wide), (N_F, wide), (N_F + 18, c_bu), (T_WORK - 6, c_bu), (T_WORK + 8, wide)], f)
            cam, look = c[:3], c[3:]
        else:
            n, t0, t1 = (ga, T_KONF, N_HA) if f < N_HA - 4 else (gu, N_HA, END)
            p, look = close(n)
            u = (f - t0) / (t1 - t0)
            cam = [p[0] - 0.2 * u, p[1], p[2] - 0.6 * u]
        F["cam"], F["look"] = [round(v, 4) for v in cam], [round(v, 4) for v in look]
        s, a = SC.pop(f, T_WORK, T_WORK + 56, rise=7, overshoot=0.3)
        F["sprites"]["check"] = {"p": [X[bu] - 0.3, 2.35, 1.2], "s": s, "a": a}
        for i, b in enumerate(burst):
            r = b(f)
            if r:
                F["sprites"][f"k{i}"] = r
        if T_KONF - 2 <= f <= N_HE + 6:                           # one confetti sails down past the guardian's face
            u = (f - T_KONF + 2) / 20
            F["sprites"]["kh"] = {"p": [X[ga] + 0.12 + 0.14 * math.sin(u * 9), ye_ga + 1.0 - 2.1 * u, Z + 0.7],
                                  "s": 1, "a": 1, "rot": round(0.7 * math.sin(u * 11), 3)}
    S.per_frame(stage)
    for f in (0, 7, 13, 20):
        S.sound(f, "ui_pop/step", ["--pitch", "E4"], level=-24, pan=0.5)
    S.sound(T_WORK, "logo_sting/zip_ping", level=-18)
    S.sound(T_WORK + 2, "impact/punch", level=-24)
    for k in range(6):
        S.sound(T_WORK + 6 + 5 * k, "fit/click/floss_lid", level=-32, pan=0.3 * (k % 3 - 1))
    S.sound(T_ACC + 4, "fit/click/floss_lid", level=-25, pan=-0.4)
    S.sound(T_WORK + 11, "ui_pop/step", ["--pitch", "G4"], level=-25, pan=0.1)
    S.sound(T_WORK + 14, "ui_pop/step", ["--pitch", "C5"], level=-27, pan=0.5)
    S.sound(T_KONF, "downlifter/air_fall", ["--dur", "0.8"], level=-30, pan=-0.4, align="start")
    S.sound(N_HE, "fit/click/floss_lid", level=-26, pan=-0.4)
    S.build()
    return S, {"lines": {"builder": N_F, "guardian": N_HE, "guide": N_HA}, "check": T_WORK, "confetti_face": T_KONF,
               "doubt": T_ACC + 4}


def part_c(folder, P):
    tx = P["texts"]
    S = SC.Scene(folder / "c_machine", deck="../../../deck/deck.json", figures_dir="../../../figures",
                 seed=P["seed"], look="none")
    V = P["voices"]["narrator"]
    S.narration("narrator", "../" + V["audio"], 6, text=V.get("text"))
    END = max(150, S.T({"line": "narrator", "edge": "end"}) + 16)
    S.end = END
    tex = S.dir / "tex"
    tex.mkdir(exist_ok=True)
    SX, BELT_Y, BIN_X = PR.pipeline_board(tex / "board.png", tx["title"], tx["stations"], tx["bin"], tx["pass"],
                                           xs=tx.get("station_x"))
    S.painted_set("tex/board.png")
    a_doc = PR.document(tx["document"], tex / "doc.png")
    PR.document("", tex / "found_ok.png", check=True)
    PR.document("", tex / "found_x.png", cross=True)
    a_bot = PR.mini_bot(tex / "bot.png")

    def W(px, py):
        return S.set_point(px, py)
    yb = W(0, BELT_Y - 6)[1] + 0.4
    n_st = len(SX)
    stops = [(4, 0), (18, 1), (40, 2), (76, 3), (100, 4)][:n_st]           # arrival at the last station ~ last words
    HOLD = 8

    def doc_x(f):
        for (f0, i0), (f1, i1) in zip(stops, stops[1:]):
            if f < f1:
                if f < f0 + HOLD:
                    return W(SX[i0], 0)[0]
                return W(SX[i0], 0)[0] + (W(SX[i1], 0)[0] - W(SX[i0], 0)[0]) * SC.smooth((f - f0 - HOLD) / (f1 - f0 - HOLD))
        return W(SX[-1], 0)[0]
    T_F = stops[3][0] + 4
    found = [("found_ok", T_F, (W(SX[-1], 0)[0] + 0.4, yb - 0.1, 0.1), 0.6),
             ("found_x", T_F + 2, (W(BIN_X, 860)[0] - 0.2, W(0, 860)[1], 0.1), 0.9),
             ("found_ok", T_F + 6, (W(SX[-1], 0)[0] + 1.1, yb - 0.15, 0.1), 0.6),
             ("found_x", T_F + 10, (W(BIN_X, 860)[0] + 0.25, W(0, 860)[1], 0.1), 0.9)]
    RIM = (W(BIN_X + 82, 780)[0], W(0, 780)[1] + 0.12, 0.1)                 # gag: bounces off the bin rim first
    T_RIM = T_F + 22
    T_IN = T_RIM + 12
    T_COUNT = stops[-1][0] + 6
    S.sprite("doc", "tex/doc.png", a_doc, 0.95, order=30)
    for i in range(2):
        S.sprite(f"bot{i}", "tex/bot.png", a_bot, 0.9, order=31)
    for i, (n, *_) in enumerate(found):
        S.sprite(f"found{i}", f"tex/{n}.png", a_doc, 0.7, order=32 + i)

    def stage(f, F):
        sp = F["sprites"]
        if f < stops[-1][0] + 14:
            sp["doc"] = {"p": [doc_x(f), yb + 0.05 * math.sin(f * 0.5), 0.1], "s": 1,
                         "a": round(min(1, f / 6, (stops[-1][0] + 14 - f) / 4), 3)}
        for i in range(2):                                          # two agents at the middle station
            s, a = SC.pop(f, stops[2][0] + 4 * i, stops[3][0], rise=6)
            sp[f"bot{i}"] = {"p": [W(SX[2], 0)[0] + (-0.75 if i == 0 else 0.75),
                                   W(0, 470)[1] + 0.1 * abs(math.sin(f * 0.4 + i)), 0.12], "s": s, "a": a}
        for i, (n, t0, goal, h) in enumerate(found):
            start = (W(SX[3], 0)[0], yb + 0.3, 0.1)
            if i == 3:
                b = SC.arc(t0, start, RIM, dur=12, height=h)(f) if f < T_RIM else \
                    SC.arc(T_RIM, RIM, goal, dur=T_IN - T_RIM, height=0.55)(f)
                rot = 0.4 * min(1, (f - t0) / 12) + (1.6 * SC.smooth((f - T_RIM) / 12) if f > T_RIM else 0)
            else:
                b = SC.arc(t0, start, goal, dur=16, height=h)(f)
                rot = 0.4 * (i % 2) * min(1, (f - t0) / 16)
            if b:
                sp[f"found{i}"] = {"p": b, "s": 1, "a": 1, "rot": round(rot, 3)}
        F["cam"], F["look"] = [0, 0, 16.79 - 0.9 * SC.smooth(f / END)], [0, 0, 0]
    S.per_frame(stage)
    S.post(lambda f, im: PR.counters(im, tx["counters"], SC.smooth((f - T_COUNT) / 30), show=f >= T_COUNT - 2))
    for f, _ in stops[1:]:
        S.sound(f, "fit/tick/domino", level=-24)
    S.sound(stops[2][0], "drip/bloop", level=-24)
    landing = [found[0][1] + 16, found[1][1] + 16, found[2][1] + 16, T_IN]
    for i, f in enumerate(landing):
        if i % 2 == 0:
            S.sound(f, "ui_pop/soft", level=-24, pan=0.6)
        else:
            S.sound(f, "ui_pop/fall", level=-24, pan=0.4)
            S.sound(f + 1, "fit/hit/bamboo_tok", level=-24, pan=0.4)
    S.sound(T_RIM, "knock/plastic", level=-20, pan=0.45)
    S.sound(T_RIM + 1, "swish/zing", ["--dur", "0.3", "--apex", "0.1"], level=-28, pan=0.45)
    S.sound(T_COUNT, "mallet/flourish", level=-26)
    S.build()
    return S, {"stops": [s[0] for s in stops], "found": [x[1] for x in found], "landing": landing, "rim": T_RIM,
               "counters": T_COUNT}


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    (A, ea), (B, eb), (C, ec) = part_a(folder, P), part_b(folder, P), part_c(folder, P)
    SC.save_events(folder, {"a": ea, "b": eb, "c": ec, "lengths": [A.end + 1, B.end + 1, C.end + 1],
                            "end": A.end + B.end + C.end + 2})
    return folder, (A, B, C)


if __name__ == "__main__":
    folder, parts = main(sys.argv[1])
    if "--plan" not in sys.argv:
        for S in parts:
            S.render(steps=("synfig", "light", "3d", "post"))
        SC.join(folder, parts)
