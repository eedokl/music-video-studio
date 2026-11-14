# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Recipe "the rumour" - four figures at the office table react to a new idea (reference: ai_efficiency S4).

  intro    the explorer tells the news (lip sync), wing/arm opens on "imagine", a dream cloud pops on the keyword
           gag: the guardian's double take (glance up, back to reading, snaps up with big eyes, stays amazed)
  pan      quick pan to the guide: thought cloud with their (unspoken) line, head sinks, sigh, tail droops
  roles    narrator; four close-ups as hard cuts on the role words (explorer / guardian / guide / builder):
           wing up + glasses flash, eyes narrow + head tilts, head tilts + eyes up, stretch + star eyes "pling" + fist
  end      wide shot, the builder still with star eyes, the explorer nods to them
Inputs in the clip folder: voice files (three lines), the painted set (back + table layer); deck/figures at ../../.
Vary in recipe.json: cast (role -> figure), positions, texts, words (keywords in the lines), voices, set, seed.
Run: uv run s04_rumor.py <clip folder> [--plan]
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
    "cast": {"explorer": "felix", "guide": "hans", "guardian": "helmut", "builder": "fritz"},
    "x": {"guardian": -5.2, "guide": -2.1, "builder": 1.0, "explorer": 4.3},     # feet x at the table (left -> right)
    "feet_y": -2.55, "z": 0.25, "scale": 0.45,
    "set": {"back": "set/office.png", "front": "set/table.png", "steam": [[1008, 590], [1268, 618]]},
    "voices": {"explorer": {"audio": "voice/explorer.wav", "text": None},
               "guide": {"audio": "voice/guide.wav", "text": None, "level": -2},      # a thought: a bit quieter
               "narrator": {"audio": "voice/narrator.wav", "text": None}},
    "words": {"dream": "prompt", "imagine": "imagine", "explorer": "explorer", "guardian": "guardian",
              "guide": "guide", "builder": "builder", "what": "what", "build": "build"},
    "texts": {"dream": "Prompt\nStudio", "thought": "Not another\noffice change..."},
    "lead": 12,
}


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    R = P["cast"]
    ex, gu, ga, bu = R["explorer"], R["guide"], R["guardian"], R["builder"]
    S = SC.Scene(folder, seed=P["seed"])
    V, Wd = P["voices"], P["words"]
    S.narration("explorer", V["explorer"]["audio"], P["lead"], speaker=ex, text=V["explorer"].get("text"),
                level=V["explorer"].get("level", 0))
    S.narration("guide", V["guide"]["audio"], {"line": "explorer", "edge": "end", "offset": 10},
                text=V["guide"].get("text"), level=V["guide"].get("level", 0))
    S.narration("narrator", V["narrator"]["audio"], {"line": "guide", "edge": "end", "offset": 12},
                text=V["narrator"].get("text"), level=V["narrator"].get("level", 0))
    T = S.T

    def w(line, word):
        return T({"line": line, "word": Wd.get(word, word)})

    N_EX, N_GU, N_NA = T.line_at("explorer"), T.line_at("guide"), T.line_at("narrator")
    E_EX, E_GU, E_NA = (T({"line": n, "edge": "end"}) for n in ("explorer", "guide", "narrator"))
    END = E_NA + 32
    S.end = END
    T_PROMPT, T_IMAGINE = w("explorer", "dream"), w("explorer", "imagine")
    T_EXPL, T_GUARD, T_GUIDE, T_BUILD = (w("narrator", k) for k in ("explorer", "guardian", "guide", "builder"))
    T_WHAT, T_BUILD2 = w("narrator", "what"), w("narrator", "build")
    DT = T_PROMPT + 18                                                     # the guardian's double take
    CUT = [T_EXPL - 6, T_GUARD - 8, T_GUIDE - 8, T_BUILD - 8, E_NA + 4]    # close-up cuts

    SU, FY, Z = P["scale"], P["feet_y"], P["z"]
    X = {R[r]: P["x"][r] for r in ("guardian", "guide", "builder", "explorer")}
    breathe = SC.breathe
    K = {}
    K[ex] = {
        "head": [(0, 0), (N_EX, 0), (N_EX + 10, -3), (T_PROMPT - 6, -3), (T_PROMPT, 3), (T_IMAGINE, 4),
                 (E_EX + 6, 0), (T_EXPL, 0), (T_EXPL + 6, 5), (CUT[1] - 1, 4), (CUT[1] + 2, 0),
                 (E_NA + 6, 0), (E_NA + 11, -4), (E_NA + 17, 1), (E_NA + 22, -3), (E_NA + 28, 0)],
        "eyes": [(0, (0, 0)), (N_EX, (-0.08, 0)), (T_PROMPT - 2, (-0.08, 0)), (T_PROMPT + 4, (0.05, 0.07)),
                 (E_EX, (0.05, 0.07)), (E_EX + 8, (-0.09, 0)), (E_GU + 6, (-0.09, 0)),
                 (T_EXPL, (0.07, 0.07)), (CUT[1], (0.07, 0.07)), (CUT[1] + 2, (-0.08, 0)), (E_NA + 8, (-0.09, -0.02))],
        "gesture": [(0, 0), (T_IMAGINE - 4, 0), (T_IMAGINE + 6, 10, "halt"), (E_EX + 4, 9), (E_EX + 16, 0),
                    (T_EXPL, 0), (T_EXPL + 8, 10, "halt"), (CUT[1] - 1, 10), (CUT[1] + 2, 0)],
        "blink": [(0, 1), (N_EX + 60, 1), (N_EX + 62, 0.1), (N_EX + 65, 1), (E_GU, 1), (E_GU + 2, 0.1),
                  (E_GU + 5, 1), (E_NA + 24, 1), (E_NA + 26, 0.1), (E_NA + 29, 1)],
        "sq": [(0, (1, 1)), (T_IMAGINE - 4, (1, 1)), (T_IMAGINE + 4, (0.97, 1.04), "halt"), (E_EX + 10, (1, 1))]
              + breathe(E_EX + 20, END)}
    rest = S.mouth_rest(gu)
    K[gu] = {
        "mouth": [(0, rest), (N_GU - 6, rest), (N_GU - 2, 1 if rest else 0), (E_GU + 10, 1 if rest else 0),
                  (E_GU + 16, rest)],                                       # thinking: mouth closed
        "head": [(0, 0), (N_EX + 8, -3), (E_EX, -3), (N_GU, 0), (N_GU + 20, 4), (E_GU + 6, 4),
                 (E_GU + 20, 0), (T_GUIDE - 2, 0), (T_GUIDE + 8, -5, "halt"), (CUT[3] - 4, -5), (CUT[3], 0)],
        "tilt": [(0, 0), (N_GU, 0), (N_GU + 16, 2), (E_GU + 10, 2), (E_GU + 24, 0)],
        "eyes": [(0, (0, 0)), (N_EX + 6, (0.09, 0)), (E_EX, (0.09, 0)), (N_GU, (0, -0.08)),
                 (E_GU + 10, (0, -0.08)), (E_GU + 18, (0, 0)), (T_GUIDE, (0, 0)), (T_GUIDE + 6, (0.05, 0.09)),
                 (CUT[3], (0.05, 0.09)), (CUT[3] + 2, (0.07, 0)), (E_NA, (0.07, 0))],
        "sq": [(0, (1, 1)), (N_GU + 4, (1, 1)), (N_GU + 18, (1.03, 0.95), "halt"), (E_GU + 8, (1, 1))]
              + breathe(E_GU + 16, END),
        "follow": [(0, 0), (N_GU, 0), (N_GU + 14, -6), (E_GU + 12, -6), (E_GU + 24, 0)],
        "blink": [(0, 1), (N_GU + 30, 1), (N_GU + 33, 0.2), (N_GU + 40, 0.2), (N_GU + 44, 1),
                  (T_GUIDE + 20, 1), (T_GUIDE + 22, 0.1), (T_GUIDE + 25, 1)]}
    K[ga] = {
        "eyes": [(0, (0, -0.07)), (T_PROMPT + 1, (0, -0.07)), (T_PROMPT + 4, (0.05, -0.02)),
                 (T_PROMPT + 9, (0.05, -0.02)), (T_PROMPT + 12, (0, -0.07)), (DT - 1, (0, -0.07)),
                 (DT + 2, (0.08, 0.03)), (T_IMAGINE + 10, (0.08, 0.03)), (T_IMAGINE + 16, (0, -0.07)),
                 (T_GUARD - 2, (0, -0.07)), (T_GUARD + 4, (0.07, 0)), (E_NA, (0.07, 0))],
        "blink": [(0, 1), (DT, 1), (DT + 3, 1.15), (DT + 12, 1.15), (DT + 16, 1),
                  (T_GUARD, 1), (T_GUARD + 6, 0.45, "halt"), (CUT[2] - 2, 0.45), (CUT[2] + 4, 1)],
        "head": [(0, -2), (T_PROMPT + 1, -2), (T_PROMPT + 5, 0), (T_PROMPT + 12, -2), (DT - 1, -2),
                 (DT + 3, 5, "halt"), (DT + 8, 3.5), (T_IMAGINE + 16, -2), (T_GUARD, -2),
                 (T_GUARD + 10, 5, "halt"), (CUT[2] - 4, 5), (CUT[2] + 6, 0)],
        "sq": [(0, (1, 1)), (DT - 1, (1, 1)), (DT + 3, (0.97, 1.05)), (DT + 9, (1, 1))] + breathe(DT + 12, END, period=64)}
    K[bu] = {
        "eyes": [(0, (0, 0)), (N_EX + 4, (0.07, 0)), (E_EX, (0.07, 0)), (E_EX + 6, (0, 0))],
        "head": [(0, 0), (T_PROMPT, 0), (T_PROMPT + 6, 3), (E_EX, 3), (E_EX + 10, 0), (T_BUILD - 4, 0),
                 (T_BUILD + 4, -3), (T_WHAT, 2), (T_BUILD2, -3), (E_NA + 10, 0)],
        "sq": [(0, (1, 1)), (T_PROMPT, (1, 1)), (T_PROMPT + 6, (0.97, 1.05), "halt"), (E_EX, (1, 1)),
               (T_BUILD - 6, (1, 1)), (T_BUILD - 2, (1.06, 0.93)), (T_BUILD + 4, (0.94, 1.09), "halt"),
               (T_BUILD + 30, (0.97, 1.04)), (E_NA + 10, (1, 1))] + breathe(E_NA + 20, END),
        "gesture": [(0, 4), (T_WHAT - 4, 4), (T_WHAT + 4, 9.5, "halt"), (T_BUILD2 + 2, 9.5), (T_BUILD2 + 8, 5),
                    (T_BUILD2 + 14, 9.5), (E_NA + 30, 6)],
        "follow": [(0, 0), (T_BUILD, 0), (T_BUILD + 6, 4), (T_BUILD + 12, -3), (T_BUILD + 18, 2), (T_BUILD + 24, 0)]}

    st = P["set"]
    S.painted_set(st["back"], st.get("front"))
    for i, n in enumerate(X):
        S.figure(n, x=X[n], y=FY, z=Z, scale=SU, order=10 + i, keys=K[n])
    for px, py in st.get("steam", []):
        S.add_steam(*S.set_point(px, py, 0.5), 0.5)
    tex = folder / "tex"
    tex.mkdir(exist_ok=True)
    a_dream = PR.cloud(P["texts"]["dream"], tex / "dream.png", "dream", colour=PR.GREEN, size=150, seed=4)
    a_thought = PR.cloud(P["texts"]["thought"], tex / "thought.png", "thought", seed=2)
    PR.star_eye(tex / "star_eye.png")
    S.sprite("dream", "tex/dream.png", a_dream, 2.0, order=40)
    S.sprite("thought", "tex/thought.png", a_thought, 1.55, order=40)
    eyes = S.pupils(bu)
    for i in range(2):
        S.sprite(f"star{i}", "tex/star_eye.png", 1, 0.30, fig=bu)
    head_y = {n: S.eye_center(n)[1] for n in X}

    def close(n):
        y = FY + head_y[n] * SU - 0.35                                      # eyes in the upper third
        return [X[n] + 0.5, y + 0.15, Z + 5.4], [X[n], y, Z]
    wide = [0, 0.1, 15.4, 0, -0.1, 0]
    wide2 = [-0.4, 0.05, 14.2, -0.4, -0.15, 0.1]                            # all four for the double take
    ex_half = [X[ex] - 1.3, 0.4, 9.6, X[ex] - 1.7, 0.0, 0.25]
    gu_half = [X[gu] + 0.9, 0.5, 9.4, X[gu] + 0.8, 0.3, 0.25]
    gu_close = [X[gu] + 0.75, 0.55, 8.6, X[gu] + 0.7, 0.35, 0.25]

    def stage(f, F):
        if f < CUT[0]:
            c = SC.keyed([(0, wide), (N_EX + 4, wide), (DT + 6, wide2), (T_IMAGINE + 8, ex_half),
                          (E_EX - 2, ex_half), (N_GU + 4, gu_half), (CUT[0] - 1, gu_close)], f)
            cam, look = c[:3], c[3:]
        elif f < CUT[4]:
            i = max(i for i in range(4) if f >= CUT[i])
            p, look = close([ex, ga, gu, bu][i])
            u = (f - CUT[i]) / (CUT[i + 1] - CUT[i])
            cam = [p[0] - 0.3 * u, p[1], p[2] - 0.7 * u]                    # brisk push-in per close-up
        else:
            c = SC.keyed([(CUT[4], wide), (END, [0.3, 0.0, 14.6, 0.3, -0.2, 0])], f)
            cam, look = c[:3], c[3:]
        F["cam"], F["look"] = [round(v, 4) for v in cam], [round(v, 4) for v in look]
        wob = 0.03 * math.sin(f * 0.15)
        s, a = SC.pop(f, T_PROMPT, E_EX + 10)
        F["sprites"]["dream"] = {"p": [X[ex] - 1.85, 1.15 + wob, Z + 0.4], "s": s, "a": a, "rot": wob * 0.5}
        s, a = SC.pop(f, N_GU - 2, E_GU + 2)
        F["sprites"]["thought"] = {"p": [X[gu] + 1.75, 1.95 + wob, Z + 0.4], "s": s, "a": a}
        s, a = SC.pop(f, T_BUILD + 2, END + 10, rise=6, overshoot=0.35)
        spin = 0.0 if f < T_BUILD + 2 else 0.25 * math.sin((f - T_BUILD) * 0.3) * math.exp(-(f - T_BUILD) / 30)
        for i, (exx, eyy) in enumerate(eyes):
            F["sprites"][f"star{i}"] = {"p": [exx, eyy, 0], "s": s, "a": a, "rot": spin}
    S.per_frame(stage)

    pan = {n: max(-0.45, min(0.45, X[n] / 8)) for n in X}
    S.sound(T_PROMPT, "logo_sting/soft_bloom", level=-24, pan=0.3, align="start")
    S.sound(T_PROMPT + 1, "ui_pop/wide", level=-22, pan=0.3)
    S.sound(T_PROMPT + 4, "hover_tick/mid", level=-30, pan=-0.45)              # double take: glance ...
    S.sound(DT + 2, "pro_zip/up", level=-24, pan=-0.45)                         # ... and snap
    S.sound(E_EX + 4, "whoosh_fast/tight", level=-27, pan=-0.1)                # pan to the guide
    S.sound(T_IMAGINE + 4, "fit/whoosh.short/bamboo_swish", level=-27, pan=0.35)
    S.sound(N_GU - 1, "ui_pop/boop", level=-22, pan=-0.2)
    S.sound(E_EX + 13, "ui_pop/fall", level=-28, pan=0.3)
    S.sound(E_GU + 5, "ui_pop/fall", level=-28, pan=-0.2)
    for f in CUT[:4]:
        S.sound(f, "swish/flick", level=-27)
    S.sound(T_EXPL + 8, "mallet/celesta", ["--pitch", "E7"], level=-24, pan=0.2)
    S.sound(T_GUARD + 6, "fit/click/floss_lid", level=-25, pan=-0.2)
    S.sound(T_GUIDE + 6, "pluck/kalimba_soft", ["--pitch", "C5"], level=-27)
    S.sound(T_BUILD + 2, "mallet/flourish", level=-19)
    S.sound(T_BUILD + 4, "drip/plink", level=-20, pan=0.05)
    S.sound(T_BUILD + 8, "mallet/glock", ["--pitch", "E6"], level=-24)
    for f in (T_WHAT + 2, T_BUILD2 + 12):
        S.sound(f, "swish/flick", level=-22, pan=0.15)
    S.build()
    ev = {"lines": {"explorer": N_EX, "guide": N_GU, "narrator": N_NA}, "dream": T_PROMPT, "wing": T_IMAGINE,
          "thought": N_GU - 2, "cuts": CUT, "stars": T_BUILD + 2, "fist": [T_WHAT + 2, T_BUILD2 + 12],
          "guardian_narrow": T_GUARD + 6, "guide_ponder": T_GUIDE + 6, "flash": T_EXPL + 8, "dream_end": E_EX + 10,
          "thought_end": E_GU + 2, "double_take": [T_PROMPT + 4, DT + 2], "pan": [E_EX - 2, N_GU + 4], "end": END}
    SC.save_events(folder, ev)
    return S


if __name__ == "__main__":
    S = main(sys.argv[1])
    if "--plan" not in sys.argv:
        S.render()
