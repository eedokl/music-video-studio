"""Recipe "coin rain and the balance" - two figures left behind in the office, costs rain down, a balance weighs cost
against value (reference: ai_efficiency S8 "token costs").

  rain     coins rain ever denser onto the guide's desk and pile up, a counter top right rattles up;
           the guide's worried line (tail droops), the guardian's hopeful line (looks at the empty seats)
  gag      as an answer three coins clink onto the guardian's head (flinches and blinks at every hit)
  narrator a balance COST | VALUE appears and tips towards value on the keyword ("boing"); on "remove" calendar sheets
           fly away
Inputs: three voice files, the office set (back + table). Vary in recipe.json: cast, positions, labels, counter,
coin count, words, voices, set, seed.
Run: uv run --no-project --with pillow --with numpy --with scipy --with scikit-image --with faster-whisper
     python s08_coin_rain.py <clip folder> [--plan]
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import props as PR  # noqa: E402
import scene as SC  # noqa: E402

DEFAULTS = {
    "seed": 1,
    "cast": {"guardian": "helmut", "guide": "hans"},
    "x": {"guardian": -5.2, "guide": -2.1}, "feet_y": -2.55, "z": 0.25, "scale": 0.45, "table_y": -1.25,
    "set": {"back": "set/office.png", "front": "set/table.png", "steam": [[1008, 590]]},
    "voices": {"guide": {"audio": "voice/guide.wav"}, "guardian": {"audio": "voice/guardian.wav"},
               "narrator": {"audio": "voice/narrator.wav"}},
    "words": {"cost": "token", "back": "back", "value": "value", "days": "remove"},
    "texts": {"labels": ["TOKENS", "VALUE"], "coin": "T", "counter": 18_400_000, "counter_label": "tokens used",
              "sheet": "DAY"},
    "coins": 72, "balance_x": 1.6,
}


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    R, V, Wd, tx = P["cast"], P["voices"], P["words"], P["texts"]
    ga, gu = R["guardian"], R["guide"]
    S = SC.Scene(folder, seed=P["seed"])
    S.narration("guide", V["guide"]["audio"], 14, speaker=gu, text=V["guide"].get("text"))
    S.narration("guardian", V["guardian"]["audio"], {"line": "guide", "edge": "end", "offset": 6}, speaker=ga,
                text=V["guardian"].get("text"))
    T = S.T
    NH, NM = T.line_at("guide"), T.line_at("guardian")
    EH, EM = T({"line": "guide", "edge": "end"}), T({"line": "guardian", "edge": "end"})
    HIT = [EM + 3, EM + 8, EM + 14]                                   # gag: coins hit the guardian's head
    S.narration("narrator", V["narrator"]["audio"], EM + 8, text=V["narrator"].get("text"))
    NE, EE = T.line_at("narrator"), T({"line": "narrator", "edge": "end"})
    T_COST, T_BACK = T({"line": "guide", "word": Wd["cost"]}), T({"line": "guardian", "word": Wd["back"]})
    T_VALUE, T_DAYS = T({"line": "narrator", "word": Wd["value"]}), T({"line": "narrator", "word": Wd["days"]})
    END = max(EE + 18, T_DAYS + 3 * 6 + 24)
    S.end = END
    SU, FY, Z, TY = P["scale"], P["feet_y"], P["z"], P["table_y"]
    X = {R[r]: P["x"][r] for r in ("guardian", "guide")}
    K = {gu: {"eyes": [(0, (0, 0)), (6, (0, 0.09)), (NH, (0.05, -0.06)), (T_COST, (0.05, -0.08)),
                       (EH + 4, (0, 0.06)), (NM, (-0.08, 0)), (EM, (-0.08, 0)), (HIT[0] + 2, (-0.08, 0.06)),
                       (HIT[2] + 16, (0.08, 0))],
              "head": [(0, 0), (6, 3), (NH, -3), (T_COST, 4), (EH + 4, 0), (HIT[0] + 2, -2), (HIT[2] + 16, 0), (T_VALUE, 3)],
              "follow": [(0, 0), (NH, -7), (EM, -7), (T_VALUE, 0)] + [(T_VALUE + 4 + 6 * i, 6 if i % 2 else -6)
                                                                     for i in range(6)],
              "sq": [(0, (1, 1)), (T_COST, (1, 1)), (T_COST + 6, (1.04, 0.95), "halt"), (EH + 20, (1, 1))]},
         ga: {"eyes": [(0, (0.06, 0.07)), (NH, (0.06, -0.04)), (NM, (0.08, 0.01)), (T_BACK, (0.08, 0.03)),
                       (HIT[0] + 1, (0.02, 0.1)), (HIT[2] + 10, (0.05, 0.08)), (HIT[2] + 22, (0.08, 0.03))],
              "head": [(0, 0), (NM, 0), (NM + 10, 4), (T_BACK, 5), (EM, 5), (HIT[0], 5), (HIT[0] + 2, 1),
                       (HIT[1], 2.5), (HIT[1] + 2, -1), (HIT[2], 0), (HIT[2] + 2, -3), (HIT[2] + 14, 0),
                       (T_VALUE, 0), (T_VALUE + 6, -3), (T_VALUE + 18, 0)],
              "blink": [(0, 1), (NM - 20, 1), (NM - 18, 0.1), (NM - 15, 1)]
                       + [k for h in HIT for k in ((h, 1), (h + 1, 0.15), (h + 4, 1))]
                       + [(T_VALUE + 30, 1), (T_VALUE + 32, 0.1), (T_VALUE + 35, 1)]}}
    st = P["set"]
    S.painted_set(st["back"], st.get("front"))
    for i, n in enumerate(X):
        S.figure(n, x=X[n], y=FY, z=Z, scale=SU, order=10 + i, keys={k: sorted(dict((x[0], x) for x in v).values())
                                                                     for k, v in K[n].items()})
    for px, py in st.get("steam", []):
        S.add_steam(*S.set_point(px, py, 0.5), 0.5)
    tex = folder / "tex"
    tex.mkdir(exist_ok=True)
    PR.coin(tex / "coin.png", text=tx["coin"])
    a_base, a_beam, a_pan = PR.scale_parts(tex / "b_base.png", tex / "b_beam.png", tex / "b_left.png",
                                           tex / "b_right.png", labels=tx["labels"])
    a_sheet = PR.calendar_sheet(tex / "sheet.png", text=tx["sheet"])
    rng = random.Random(10 + P["seed"])
    coins, piles = [], {}
    n_c = P["coins"]
    for i in range(n_c):
        t0 = int(4 + (NE - 24) * (i / n_c) ** 0.7) + rng.randint(-2, 2)
        x = X[gu] + rng.uniform(-1.6, 1.8)
        b = round(x / 0.35)
        k = piles.get(b, 0)
        piles[b] = k + 1
        coins.append((t0, x, TY + 0.05 * k + rng.uniform(-0.03, 0.03), rng.uniform(-3, 3), rng.uniform(0.55, 0.8)))
    days = [SC.arc(T_DAYS + 3 * i, (2.6, 0.2, 0.7), (6.5 + i * 0.6, 4.5 + rng.uniform(0, 1.5), 2.0), dur=26, height=0.8)
            for i in range(7)]
    WX = P["balance_x"]
    top = (X[ga] + S.eye_center(ga)[0] * SU, FY + S.head_top(ga)[1] * SU - 0.12)     # coins hit just below the top
    for i in range(n_c):
        S.sprite(f"c{i}", "tex/coin.png", 1, 0.32, order=30 + (i % 10))
    S.sprite("b_base", "tex/b_base.png", a_base, 2.0, order=50)
    S.sprite("b_left", "tex/b_left.png", a_pan, 1.0, order=51)
    S.sprite("b_right", "tex/b_right.png", a_pan, 1.0, order=51)
    S.sprite("b_beam", "tex/b_beam.png", a_beam, 0.15, order=52)
    for i in range(7):
        S.sprite(f"sheet{i}", "tex/sheet.png", a_sheet, 0.6, order=60)
    for j in range(3):
        S.sprite(f"h{j}", "tex/coin.png", 1, 0.32, order=15)
    wide = [0, 0.1, 15.4, 0, -0.1, 0]
    gu_m = [X[gu] + 0.5, 0.4, 10.0, X[gu] + 0.5, -0.3, 0.25]
    ga_m = [X[ga] + 2.5, 0.3, 9.8, X[ga] + 2.3, -0.3, 0.25]
    bal = [WX - 1.6, 0.2, 12.6, WX - 1.4, -0.2, 0.25]
    S.camera([(0, wide), (NH + 10, gu_m), (EH, gu_m), (NM + 8, ga_m), (HIT[2] + 4, ga_m), (HIT[2] + 18, bal),
              (END, [WX - 1.4, 0.2, 11.8, WX - 1.3, -0.2, 0.25])])

    def stage(f, F):
        sp = F["sprites"]
        for j, h in enumerate(HIT):
            tt = (f - h) / 24
            hx, hy = top[0] + (-0.12, 0.1, 0.0)[j], top[1]
            if tt < -0.45:
                continue
            if tt < 0:
                p, r = [hx, hy + 9.0 * tt * tt], 4 * tt
            else:
                vx = (-1.4, 1.2, 0.6)[j]
                p, r = [hx + vx * tt, hy + 2.6 * tt - 9.0 * tt * tt], 9 * tt * (1 if vx > 0 else -1)
                if p[1] < -3.5:
                    continue
            sp[f"h{j}"] = {"p": [round(p[0], 3), round(p[1], 3), 0.4], "s": 1, "a": 1, "rot": round(r, 3)}
        for i, (t0, x, yl, rot, zz) in enumerate(coins):
            if f < t0:
                continue
            tt = (f - t0) / 24
            y = 5.0 - 9.0 * tt * tt
            if y <= yl:
                t_hit = math.sqrt((5 - yl) / 9)
                bounce = max(0.0, 0.12 * math.sin((tt - t_hit) * 22) * math.exp(-(tt - t_hit) * 9))
                y, r = yl + abs(bounce), 1.45
            else:
                r = rot * tt
            sp[f"c{i}"] = {"p": [round(x, 3), round(y, 3), zz], "s": 1, "a": 1, "rot": round(r, 3),
                           "sx": 1.0 if y > yl + 0.01 else 0.45}
        s_, a_ = SC.pop(f, NE, END + 20, rise=8)
        if s_ > 0:
            ang = 0.22 if f < T_VALUE else 0.22 - 0.44 * SC.smooth((f - T_VALUE) / 14) - 0.05 * math.sin(
                (f - T_VALUE) * 0.4) * math.exp(-(f - T_VALUE) / 18)
            pv = (WX, 0.55)
            sp["b_base"] = {"p": [WX, -0.3, 0.7], "s": s_, "a": a_}
            sp["b_beam"] = {"p": [pv[0], pv[1], 0.72], "s": s_, "a": a_, "rot": round(ang, 4)}
            for k, sgn in (("b_left", -1), ("b_right", 1)):
                ex = pv[0] + sgn * 1.25 * math.cos(ang) * s_
                ey = pv[1] + sgn * 1.25 * math.sin(ang) * s_
                sp[k] = {"p": [round(ex, 3), round(ey - 0.5 * s_, 3), 0.74], "s": s_, "a": a_}
        for i, b in enumerate(days):
            p = b(f)
            if p:
                sp[f"sheet{i}"] = {"p": p, "s": 1, "a": max(0.0, 1 - (f - T_DAYS - 3 * i) / 40), "rot": 0.12 * (f - T_DAYS)}
    S.per_frame(stage)

    def counter(f, im):
        if f < 4:
            return im
        u = min(1.0, (f - 4) / (NE - 4)) ** 1.8
        a = min(1.0, (f - 4) / 8) * (1 if f < END - 9 else max(0, (END - f) / 9))
        return PR.counter_box(im, int(tx["counter"] * u + (f * 7919) % 997), tx["counter_label"], a)
    S.post(counter)
    for i, (t0, *_r) in enumerate(sorted(coins)):
        if i % 2 == 0:
            S.sound(t0 + int(24 * (5.0 / 9.0) ** 0.5), "drip/plink", ["--pitch", ["F5", "A5", "C6", "E6"][i % 4]],
                    level=-30 + min(6, i // 12), pan=-0.2)
    for j, f in enumerate(HIT):
        S.sound(f, "drip/plink", ["--pitch", ["A5", "C6", "E6"][j]], level=-20, pan=-0.5)
        S.sound(f, "pro_click/tink", level=-24, pan=-0.5)
    S.sound(NE, "ui_pop/wide", level=-21)
    S.sound(T_VALUE, "knock/wood", level=-20, pan=0.2)
    S.sound(T_VALUE + 1, "pluck/kalimba_ring", level=-21, pan=0.2)
    S.sound(T_VALUE + 2, "pro_zip/up", level=-26, pan=0.2)
    S.sound(T_VALUE + 2, "mallet/marimba", ["--pitch", "C5"], level=-24, pan=0.2)
    for k in range(7):
        S.sound(T_DAYS + 3 * k + 4, "fit/whoosh.short/bamboo_swish", level=-28, pan=0.4)
    S.build()
    SC.save_events(folder, {"lines": {"guide": NH, "guardian": NM, "narrator": NE}, "balance": NE, "tip": T_VALUE,
                            "days": T_DAYS, "head_coins": HIT, "end": END})
    return S


if __name__ == "__main__":
    S = main(sys.argv[1])
    if "--plan" not in sys.argv:
        S.render()
