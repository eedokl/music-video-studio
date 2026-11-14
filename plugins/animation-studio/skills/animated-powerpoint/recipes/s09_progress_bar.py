"""Recipe "learning step by step" - a figure opens a book, a progress bar grows beside its head, warm light comes up
(reference: ai_efficiency S9 "most of us are Hans").

  book     the book pops onto the desk, the guide reads (tail wags on the keyword), the bar grows with the line
  sceptic  the guardian's line ("show me the data"), eyes half shut
  narrator camera pushes in on the guide, warm light comes up; gag: on the guide's name the figure looks caught into
           the camera (double blink, small hop); on "but" the bar sags back a bit, the guide squints at it
Inputs: three voice files, the office set (back + table). Vary in recipe.json: cast, positions, book title, bar label,
words, voices, set, seed.
Run: uv run --no-project --with pillow --with numpy --with scipy --with scikit-image --with faster-whisper
     python s09_progress_bar.py <clip folder> [--plan]
"""
import math
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
    "words": {"like": "like", "data": "data", "name": "hans", "learn": "learn", "but": "but"},
    "texts": {"book": "AI\nFundamentals\nfor Engineers", "bar": "AI skills"},
}


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    R, V, Wd, tx = P["cast"], P["voices"], P["words"], P["texts"]
    ga, gu = R["guardian"], R["guide"]
    S = SC.Scene(folder, seed=P["seed"])
    S.narration("guide", V["guide"]["audio"], 12, speaker=gu, text=V["guide"].get("text"))
    S.narration("guardian", V["guardian"]["audio"], {"line": "guide", "edge": "end", "offset": 6}, speaker=ga,
                text=V["guardian"].get("text"))
    S.narration("narrator", V["narrator"]["audio"], {"line": "guardian", "edge": "end", "offset": 8},
                text=V["narrator"].get("text"))
    T = S.T
    NH, NM, NE = T.line_at("guide"), T.line_at("guardian"), T.line_at("narrator")
    EH, EM, EE = (T({"line": n, "edge": "end"}) for n in ("guide", "guardian", "narrator"))
    END = EE + 20
    S.end = END
    T_LIKE = T({"line": "guide", "word": Wd["like"]})
    T_DATA = T({"line": "guardian", "word": Wd["data"]})
    T_NAME, T_LEARN, T_BUT = (T({"line": "narrator", "word": Wd[k]}) for k in ("name", "learn", "but"))
    T_CAUGHT = T_NAME - 2
    SU, FY, Z, TY = P["scale"], P["feet_y"], P["z"], P["table_y"]
    X = {R[r]: P["x"][r] for r in ("guardian", "guide")}
    K = {gu: {"eyes": [(0, (0, -0.09)), (NH, (0, -0.09)), (T_LIKE - 2, (0, -0.09)), (T_LIKE + 2, (0.04, 0.02)),
                       (EH + 4, (0, -0.09)), (NM, (-0.08, 0)), (EM, (-0.08, 0)), (NE, (0, -0.09)),
                       (T_CAUGHT, (0, -0.09)), (T_CAUGHT + 2, (0, 0.0)), (T_CAUGHT + 22, (0, 0.0)),
                       (T_LEARN, (0.0, 0.07)), (T_BUT, (0.03, 0.07)), (T_BUT + 6, (0.09, 0.1)),
                       (T_BUT + 24, (0.09, 0.1)), (T_BUT + 30, (0, -0.06))],
              "head": [(0, 2), (NH, 2), (T_LIKE, -3), (EH + 4, 2), (T_CAUGHT, 2), (T_CAUGHT + 3, -4), (T_CAUGHT + 22, -3),
                       (T_LEARN, 3), (T_BUT + 4, 4), (T_BUT + 26, 4), (T_BUT + 34, 1)],
              "blink": [(0, 1), (NH + 30, 1), (NH + 32, 0.1), (NH + 35, 1), (NM + 30, 1), (NM + 32, 0.1),
                        (NM + 35, 1), (T_CAUGHT + 3, 1), (T_CAUGHT + 4, 0.1), (T_CAUGHT + 6, 1), (T_CAUGHT + 8, 0.1),
                        (T_CAUGHT + 10, 1.08), (T_CAUGHT + 18, 1), (T_BUT + 40, 1), (T_BUT + 42, 0.1), (T_BUT + 45, 1)],
              "follow": [(0, 0), (T_LIKE, 0)] + [(T_LIKE + 4 + 6 * i, 5 if i % 2 else -5) for i in range(5)]
                        + [(T_LEARN, 0)] + [(T_LEARN + 4 + 6 * i, 6 if i % 2 else -6) for i in range(6)] + [(T_BUT + 26, 0)],
              "sq": [(0, (1, 1)), (T_CAUGHT + 2, (1, 1)), (T_CAUGHT + 5, (1.05, 0.94)), (T_CAUGHT + 9, (0.97, 1.04)),
                     (T_CAUGHT + 14, (1, 1)), (T_LEARN - 4, (1, 1)), (T_LEARN, (0.97, 1.04), "halt"), (T_BUT + 10, (1, 1))]},
         ga: {"eyes": [(0, (0.07, -0.03)), (NM, (0.08, 0)), (T_DATA, (0.08, 0.02)), (EM + 10, (0.07, -0.03))],
              "blink": [(0, 1), (NM, 1), (NM + 4, 0.6, "halt"), (T_DATA, 0.6), (T_DATA + 4, 1)],
              "head": [(0, 0), (NM, 0), (NM + 8, 3), (T_DATA, -3), (T_DATA + 8, 2), (EM, 0)]}}
    st = P["set"]
    S.painted_set(st["back"], st.get("front"))
    for i, n in enumerate(X):
        S.figure(n, x=X[n], y=FY, z=Z, scale=SU, order=10 + i, keys={k: sorted(dict((x[0], x) for x in v).values())
                                                                     for k, v in K[n].items()})
    for px, py in st.get("steam", []):
        S.add_steam(*S.set_point(px, py, 0.5), 0.5)
    tex = folder / "tex"
    tex.mkdir(exist_ok=True)
    a_book = PR.book(tx["book"], tex / "book.png")
    a_frame = PR.progress_frame(tex / "bar_frame.png", label=tx["bar"])
    a_fill = PR.progress_fill(tex / "bar_fill.png")
    PR.warm_light(tex / "light.png")
    BW = 1.55
    S.sprite("book", "tex/book.png", a_book, 0.75, order=30)
    S.sprite("bar_frame", "tex/bar_frame.png", a_frame, BW / a_frame, order=40)
    S.sprite("bar_fill", "tex/bar_fill.png", a_fill, BW * (660 / 700) / a_fill, order=41)
    S.sprite("light", "tex/light.png", 1, 5.5, order=5, add=True)
    hx = X[gu]
    head_y = FY + S.head_top(gu)[1] * SU + 0.3                     # a bit above the head top
    wide = [0, 0.1, 15.4, 0, -0.1, 0]
    gu_m = [hx + 0.4, 0.6, 9.8, hx + 0.2, 0.0, 0.25]
    ga_m = [X[ga] + 2.5, 0.3, 9.8, X[ga] + 2.3, -0.3, 0.25]
    gu_c = [hx + 0.3, 0.7, 7.2, hx + 0.1, 0.2, 0.25]
    S.camera([(0, wide), (NH + 4, gu_m), (EH + 2, gu_m), (NM + 8, ga_m), (EM, ga_m), (NE + 8, wide),
              (T_CAUGHT, wide), (T_CAUGHT + 5, gu_m), (END, gu_c)])

    def stage(f, F):
        sp = F["sprites"]
        s_, a_ = SC.pop(f, 4, END + 20, rise=6)
        sp["book"] = {"p": [hx + 0.2, TY + 0.25, 0.62], "s": s_, "a": a_}
        s_, a_ = SC.pop(f, NH - 4, END + 20, rise=8)
        prog = 0.06 + 0.24 * SC.smooth((f - NH) / (EH - NH)) + 0.3 * SC.smooth((f - NE) / (T_LEARN + 12 - NE))
        prog -= 0.14 * SC.smooth((f - T_BUT - 2) / 8)                     # gag: "... not yet" - the bar sags
        wob = 0.02 * math.sin((f - T_BUT - 10) * 0.6) * math.exp(-(f - T_BUT - 10) / 14) if f > T_BUT + 10 else 0
        bx, by = hx + 1.75, head_y - 1.15                                 # beside the head
        sp["bar_frame"] = {"p": [bx, by + 0.12, 0.4], "s": s_, "a": a_}
        fw = BW * (660 / 700)
        sp["bar_fill"] = {"p": [bx - fw / 2 + fw * (prog + wob) / 2, by, 0.41], "s": s_,
                          "sx": round(max(0.001, prog + wob) * s_, 4), "a": a_}
        sp["light"] = {"p": [hx, FY + 2.6, 0.1], "s": 1, "a": round(0.85 * SC.smooth((f - T_NAME + 10) / 50), 3)}
    S.per_frame(stage)
    S.sound(4, "fit/land.light/fingertip_book", level=-22, pan=-0.2)
    S.sound(10, "swish/soft", ["--dur", "0.4", "--apex", "0.2"], level=-28)
    S.sound(NH - 4, "ui_pop/boop", level=-24)
    S.sound(T_CAUGHT + 3, "fit/pop/lip_pop", level=-22, pan=-0.15)
    S.sound(T_CAUGHT + 8, "pro_tap/double", level=-28, pan=-0.15)
    S.sound(T_NAME, "logo_sting/soft_bloom", level=-24, align="start")
    S.sound(T_LEARN, "mallet/up4", level=-22)
    S.sound(T_BUT + 2, "pro_zip/down", level=-24, pan=0.3)
    S.build()
    SC.save_events(folder, {"lines": {"guide": NH, "guardian": NM, "narrator": NE}, "book": 4, "bar": NH - 4,
                            "light": T_NAME, "learn": T_LEARN, "caught": T_CAUGHT, "sag": T_BUT + 2, "end": END})
    return S


if __name__ == "__main__":
    S = main(sys.argv[1])
    if "--plan" not in sys.argv:
        S.render()
