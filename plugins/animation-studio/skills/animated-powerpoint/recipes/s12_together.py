# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Recipe "together at the table" - finale: all figures at one table, a chain of steps lights up on the board, little
bots carry results, everybody cheers with confetti (reference: ai_efficiency S12 "Agentic workflow lab").

  room     sign pops, the chain (e.g. Data -> Ingest -> Analyze -> Decide -> Execute) pops on the board step by step,
           a light pulse runs along it from a keyword, three bots carry documents across the table
  cheer    on the last keyword all hop twice, arm/wing/tail up, three confetti bursts
  gag      one confetti piece sails down and stays on the guardian's head; the guardian squints up and blinks
Inputs: one narrator line, the room set (back + table). Vary in recipe.json: cast, positions, sign, chain steps,
words, voices, set, seed.
Run: uv run s12_together.py <clip folder> [--plan]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import props as PR  # noqa: E402
import scene as SC  # noqa: E402

DEFAULTS = {
    "seed": 1,
    "cast": {"guardian": "helmut", "guide": "hans", "builder": "fritz", "explorer": "felix"},
    "x": {"guardian": -4.3, "guide": -1.6, "builder": 1.75, "explorer": 4.1}, "feet_y": -2.9,
    "lift": {"builder": 0.75}, "z": 0.25, "scale": 0.36,
    "set": {"back": "set/lab.png", "front": "set/lab_table.png"},
    "voices": {"narrator": {"audio": "voice/narrator.wav"}},
    "words": {"seat": "seat", "pulse": "automation", "team": "team", "cheer": "together"},
    "texts": {"sign": "AGENTIC WORKFLOW LAB", "chain": ["Data", "Ingest", "Analyze", "Decide", "Execute"]},
    "head_gag": "guardian",
    "lead": 10,
}


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    R, V, Wd, tx = P["cast"], P["voices"], P["words"], P["texts"]
    S = SC.Scene(folder, seed=P["seed"])
    S.narration("narrator", V["narrator"]["audio"], P["lead"], text=V["narrator"].get("text"))
    T = S.T
    NE = T.line_at("narrator")
    T_SEAT, T_AUTO, T_TEAM, T_TOG = (T({"line": "narrator", "word": Wd[k]}) for k in ("seat", "pulse", "team", "cheer"))
    E_NE = T({"line": "narrator", "edge": "end"})
    END = max(E_NE + 30, T_TOG + 50)
    S.end = END
    SIGN = 4
    chain = tx["chain"]
    CHAIN_T = [T_SEAT - 6 + 6 * i for i in range(len(chain))]
    BOTS = [12 + 24 * i for i in range(3)]
    T_STICK = T_TOG + 26
    SU, FY, Z = P["scale"], P["feet_y"], P["z"]
    roles = ["guardian", "guide", "builder", "explorer"]
    X = {R[r]: P["x"][r] for r in roles}
    LIFT = {R[r]: v for r, v in P["lift"].items()}
    hg = R[P["head_gag"]]
    hop = SC.steps(T_TOG - 2, T_TOG + 22, 2, height=1.4, squash=0.16, rock=0)
    look = {}
    xs = sorted(X.values())
    for n, x in X.items():                                     # everybody looks towards the middle of the table
        i = xs.index(x)
        look[n] = [(0.08, 0.06), (0.05, 0.08), (-0.05, 0.08), (-0.08, 0.06)][min(3, round(i * 3 / max(1, len(xs) - 1)))]
    K = {}
    for n in X:
        K[n] = {"eyes": [(0, (0, 0)), (T_AUTO - 10, look[n]), (T_TEAM, look[n]), (T_TEAM + 6, (0, 0))],
                "head": [(0, 0), (T_AUTO - 10, 3), (T_TEAM, -2), (T_TOG, 0)],
                "pos": hop["pos"], "sq": [(0, (1, 1))] + hop["sq"]}
    K[hg]["head"] = [(0, 0), (NE, 0), (NE + 6, 3), (T_SEAT, -2), (T_SEAT + 8, 0)] + K[hg]["head"][1:]
    K[hg]["eyes"] += [(T_STICK, (0, 0)), (T_STICK + 4, (0.02, 0.11), "halt"), (T_STICK + 22, (0.02, 0.11)),
                      (T_STICK + 28, (0, 0.02))]
    K[hg]["blink"] = [(0, 1), (T_STICK + 6, 1), (T_STICK + 8, 0.1), (T_STICK + 10, 1), (T_STICK + 13, 0.1),
                      (T_STICK + 15, 1)]
    K[R["guide"]]["follow"] = [(0, 0), (T_TEAM, 0)] + [(T_TEAM + 4 * i, 7 if i % 2 else -7) for i in range(1, 22)]
    K[R["explorer"]]["gesture"] = [(0, 0), (T_TOG - 4, 0), (T_TOG + 4, 10, "halt"), (T_TOG + 40, 10), (T_TOG + 52, 0)]
    K[R["builder"]]["gesture"] = [(0, 4), (T_TOG - 4, 4), (T_TOG + 4, 9.5, "halt"), (T_TOG + 40, 9.5), (T_TOG + 52, 5)]
    S.painted_set(P["set"]["back"], P["set"].get("front"))
    for i, n in enumerate(X):
        S.figure(n, x=X[n], y=FY + LIFT.get(n, 0), z=Z, scale=SU, order=10 + i, keys=K[n])
    tex = folder / "tex"
    tex.mkdir(exist_ok=True)
    S.sprite("sign", "tex/sign.png", PR.sign(tx["sign"], tex / "sign.png"), 0.55, order=3)
    S.sprite("pulse", "tex/pulse.png", PR.warm_light(tex / "pulse.png", colour=(140, 230, 190)), 1.4, order=4, add=True)
    for i, k in enumerate(chain):
        S.sprite(f"k{i}", f"tex/k{i}.png", PR.sign(k, tex / f"k{i}.png", height=200), 0.55, order=5)
    a_bot = PR.mini_bot(tex / "bot.png")
    a_doc = PR.document("", tex / "doc.png", check=True)
    for i in range(3):
        S.sprite(f"bot{i}", "tex/bot.png", a_bot, 0.6, order=40 + i)
    for i in range(3):
        S.sprite(f"doc{i}", "tex/doc.png", a_doc, 0.42, order=43 + i)
    conf = PR.confetti_set(tex)
    burst = SC.confetti(T_TOG + 4, (0, 0.5, 1.6), n=60, seed=9, force=1.2) + \
        SC.confetti(T_TOG + 8, (-2.5, 0.2, 1.6), n=20, seed=10) + SC.confetti(T_TOG + 8, (2.5, 0.2, 1.6), n=20, seed=11)
    for i in range(len(burst)):
        S.sprite(f"kf{i}", conf[i % len(conf)], 1.6, 0.13, order=60)
    S.sprite("kf_head", conf[3 % len(conf)], 1.6, 0.16, order=61)
    hx, hy = S.head_top(hg)
    HEAD = (X[hg] + hx * SU, FY + LIFT.get(hg, 0) + hy * SU - 0.02)
    n_c = len(chain)
    kx = [-3.7 + 7.4 * i / max(1, n_c - 1) for i in range(n_c)]
    ky = 1.9
    S.camera([(0, [0, 0.3, 16.2, 0, 0.2, 0]), (NE, [0, 0.2, 14.6, 0, 0.3, 0]), (T_AUTO, [0, 0.6, 13.4, 0, 0.9, 0]),
              (T_TEAM, [0, 0.3, 12.8, 0, 0.4, 0.25]), (T_TOG + 30, [0, 0.2, 12.6, 0, 0.3, 0.25]),
              (END, [0, 0.4, 14.0, 0, 0.3, 0])])

    def stage(f, F):
        sp = F["sprites"]
        s_, a_ = SC.pop(f, SIGN, END + 20)
        sp["sign"] = {"p": [0, 3.05, 0.05], "s": s_, "a": a_}
        for i in range(n_c):
            s_, a_ = SC.pop(f, CHAIN_T[i], END + 20, rise=6, overshoot=0.3)
            sp[f"k{i}"] = {"p": [kx[i], ky, 0.06], "s": s_, "a": a_}
        if f > T_AUTO:                                         # light pulse runs along the chain (loop)
            u = ((f - T_AUTO) / 30) % 1
            px = kx[0] + (kx[-1] - kx[0]) * u
            sp["pulse"] = {"p": [px, ky, 0.07], "s": 1, "a": 0.9}
            for i in range(n_c):
                near = max(0.0, 1 - abs(px - kx[i]) / 0.9)
                sp[f"k{i}"]["s"] = round(sp[f"k{i}"]["s"] * (1 + 0.12 * near), 3)
        for i in range(3):                                     # bots carry documents across the table
            t0 = BOTS[i]
            if f >= t0:
                u = ((f - t0) / 96) % 1
                x = -2.0 + 4.0 * (0.5 - 0.5 * math.cos(u * 2 * math.pi))
                h = 0.08 * abs(math.sin((f - t0) * 0.35))
                s_, a_ = SC.pop(f, t0, END + 20, rise=6)
                sp[f"bot{i}"] = {"p": [x + (i - 1) * 0.4, -0.55 + h, 0.75 + 0.02 * i], "s": s_, "a": a_}
                sp[f"doc{i}"] = {"p": [x + (i - 1) * 0.4, -0.1 + h, 0.76 + 0.02 * i], "s": s_, "a": a_,
                                 "rot": 0.1 * math.sin(f * 0.2 + i)}
        for i, b in enumerate(burst):
            r = b(f)
            if r:
                sp[f"kf{i}"] = r
        if f >= T_TOG + 6:                                     # one piece for the guardian's head
            u = min(1.0, (f - T_TOG - 6) / (T_STICK - T_TOG - 6))
            x = HEAD[0] + 0.35 * (1 - u) * math.cos(u * 9)
            y = HEAD[1] + 3.6 * (1 - u)
            rot = 0.0 if u >= 1 else 0.6 * math.sin(u * 14)
            sp["kf_head"] = {"p": [round(x, 3), round(y, 3), Z + 0.02], "s": 1.0, "a": 1.0, "rot": round(rot, 3)}
    S.per_frame(stage)
    S.sound(SIGN, "ui_pop/wide", level=-21)
    for i, f in enumerate(CHAIN_T):
        S.sound(f, "mallet/celesta", ["--pitch", ["C5", "D5", "E5", "G5", "C6", "D6", "E6"][i % 7]], level=-23,
                pan=-0.6 + 0.3 * i)
    S.sound(T_AUTO, "riser/air", level=-30, align="start")
    for f in BOTS:
        S.sound(f, "drip/bloop", level=-26)
    S.sound(T_TOG, "impact/punch", level=-23)
    S.sound(T_TOG + 2, "logo_sting/zip_ping", level=-19)
    for k in range(8):
        S.sound(T_TOG + 6 + 4 * k, "fit/click/floss_lid", level=-33, pan=0.25 * ((k % 5) - 2))
    S.sound(T_STICK, "drip/plink", ["--pitch", "C6"], level=-24, pan=-0.5)
    S.sound(T_STICK + 9, "ui_pop/blip", level=-29, pan=-0.5)
    S.build()
    SC.save_events(folder, {"lines": {"narrator": NE}, "sign": SIGN, "chain": CHAIN_T, "pulse": T_AUTO, "bots": BOTS,
                            "cheer": T_TOG, "head_confetti": T_STICK, "end": END})
    return S


if __name__ == "__main__":
    S = main(sys.argv[1])
    if "--plan" not in sys.argv:
        S.render()
