# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Recipe "new room + split screen" - two figures build things in a new room, a sceptic answers from the old room in a
split screen (reference: ai_efficiency S5 "Fritz builds chatbots").

  room     a sign pops, the builder types (key flashes), chat bubbles rise from the laptop, on a keyword a mini bot
           jumps out onto the table; the explorer answers (wing up) and on a keyword project cards fly out of the
           laptop and fan out in two rows; a big info card with key figures
  split    the old room slides in from the left (divider with ink edges); gag: the sceptic's double take towards the
           new room (glance, back, snaps over with narrow eyes); the sceptic's line
  narrator the builder types on, more bots hop out, a question mark pops on "trusted", the sceptic shakes the head,
           the builder nods happily on the last word; gag: the sceptic blinks slowly and dryly into the camera
Inputs: four voice files, the new room (back + table), the old room (back + table). Vary in recipe.json: cast,
texts (sign, cards, info card), words, laptop position, voices, sets, seed.
Run: uv run s05_split_screen.py <clip folder> [--plan]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import props as PR  # noqa: E402
import scene as SC  # noqa: E402

DEFAULTS = {
    "seed": 1,
    "cast": {"builder": "fritz", "explorer": "felix", "guardian": "helmut"},
    "room": {"builder": [-2.9, -2.6], "explorer": [3.3, -2.9]},        # feet (x, y) in the new room
    "old_room": {"guardian": [-5.2, -2.55]},
    "z": 0.25, "scale": 0.45,
    "laptop": [-2.93, -0.57, 0.55], "table_y": -1.30,                   # top edge of the laptop lid, table top (world)
    "set": {"back": "set/studio.png", "front": "set/studio_table.png",
            "old_back": "set/office.png", "old_front": "set/table.png", "old_steam": [[1008, 590]]},
    "voices": {"builder": {"audio": "voice/builder.wav"}, "explorer": {"audio": "voice/explorer.wav"},
               "guardian": {"audio": "voice/guardian.wav"}, "narrator": {"audio": "voice/narrator.wav"}},
    "words": {"bot": "chat", "rocks": "rocks", "help": "help", "verify": "verification", "trust": "trusted",
              "last": "enthusiasm"},
    "texts": {"sign": "PROMPT STUDIO",
              "cards": [["EasyBot", "Engineering chatbot using BST Hadoop data"],
                        ["Semiconductor Expertise", "Knowledge graphs + LLM for root-cause analysis"],
                        ["Virtual Group Leader", "Sparring partner for reviews and coaching"],
                        ["ASIC Architecture Bot", "Jama, Docupedia and meeting transcripts"],
                        ["FAE Chatbot", "Knowledge base for customer support"],
                        ["PUR Chatbot", "Purchasing quotes and project data"],
                        ["Innovation Coach", "Helps writing invention reports"],
                        ["8D Report Bot", "Chatbot for 8D report creation"],
                        ["SPI Bot", "Special knowledge on SPI details"],
                        ["JamaAgent", "Natural-language interface to Jama"]],
              "info_title": "EasyBot",
              "info_rows": [["50-70", "users\nper month"], ["1,000+", "questions\nper month"],
                            ["since", "April 2025\nin production"]]},
    "lead": 14,
}


def breathe(start, end, amp=0.008, period=52):
    out, f = [], start
    while f < end:
        out.append((f, (1, 1), "halt"))
        if f + period // 2 < end:
            out.append((f + period // 2, (1 + amp * 0.5, 1 + amp), "halt"))
        f += period
    return out


def main(folder):
    folder = Path(folder).resolve()
    P = SC.recipe_config(folder, DEFAULTS)
    R = P["cast"]
    bu, ex, ga = R["builder"], R["explorer"], R["guardian"]
    V, Wd = P["voices"], P["words"]
    S = SC.Scene(folder, seed=P["seed"])
    S.narration("builder", V["builder"]["audio"], P["lead"], speaker=bu, text=V["builder"].get("text"))
    S.narration("explorer", V["explorer"]["audio"], {"line": "builder", "edge": "end", "offset": 6}, speaker=ex,
                text=V["explorer"].get("text"))
    T = S.T
    E_BU, E_EX = T({"line": "builder", "edge": "end"}), T({"line": "explorer", "edge": "end"})
    N_BU, N_EX = T.line_at("builder"), T.line_at("explorer")
    T_INFO = E_EX + 8                                            # info card big
    SPLIT = T_INFO + 42                                          # the old room slides in
    N_GA = SPLIT + 20
    S.narration("guardian", V["guardian"]["audio"], N_GA, text=V["guardian"].get("text"))  # sound; lips on the side
    S.narration("narrator", V["narrator"]["audio"], {"line": "guardian", "edge": "end", "offset": 8},
                text=V["narrator"].get("text"))
    E_GA = T({"line": "guardian", "edge": "end"})
    N_NA, E_NA = T.line_at("narrator"), T({"line": "narrator", "edge": "end"})
    T_DEADPAN = E_NA + 2
    END = T_DEADPAN + 18
    S.end = END

    def w(line, k):
        return T({"line": line, "word": Wd.get(k, k)})
    T_BOT, T_ROCKS, T_HELP = w("builder", "bot"), w("builder", "rocks"), w("explorer", "help")
    T_VERIF, T_TRUST, T_LAST = w("guardian", "verify"), w("narrator", "trust"), w("narrator", "last")
    T_TAKE, T_TAKE2 = SPLIT + 8, SPLIT + 17
    BOT_T = [T_BOT, N_NA + 8, N_NA + 22]
    T_CARDS = T_HELP + 2
    KEYS = list(range(2, N_BU, 3)) + list(range(N_NA - 4, N_NA + 26, 3))       # key strokes (flash + click)

    tap = [(f, 1.5 if i % 2 else -0.5) for i, f in enumerate(range(2, N_BU, 4))]
    K = {bu: {
        "eyes": [(0, (0, -0.08)), (N_BU - 2, (0, -0.08)), (N_BU + 4, (0.08, 0)), (T_BOT - 2, (0.08, 0)),
                 (T_BOT + 2, (0.02, -0.05)), (E_BU, (0.02, -0.05)), (E_BU + 6, (0.08, 0)),
                 (T_CARDS, (0.08, 0)), (T_CARDS + 6, (0.03, 0.08)), (T_INFO + 40, (0.03, 0.08)),
                 (T_INFO + 46, (0, -0.08)), (N_NA, (0, -0.08)), (N_NA + 8, (0.06, -0.04))],
        "head": [(0, 0)] + tap + [(N_BU, 0), (N_BU + 8, -3), (T_ROCKS - 4, -3), (T_ROCKS + 2, 3),
                                  (E_BU + 8, 0), (T_CARDS + 6, 3), (T_INFO + 40, 0)]
                + [(f, 1.5 if i % 2 else -0.5) for i, f in enumerate(range(N_NA - 4, N_NA + 26, 5))]
                + [(T_LAST, 0), (T_LAST + 6, 3), (T_LAST + 14, 0)],
        "sq": [(0, (1, 1)), (T_ROCKS - 4, (1, 1)), (T_ROCKS, (1.05, 0.94)), (T_ROCKS + 5, (0.96, 1.06), "halt"),
               (T_ROCKS + 14, (1, 1))] + breathe(T_ROCKS + 20, END),
        "follow": [(0, 0), (T_ROCKS, 0), (T_ROCKS + 5, 4), (T_ROCKS + 11, -3), (T_ROCKS + 17, 2), (T_ROCKS + 23, 0)],
        "blink": [(0, 1), (48, 1), (50, 0.1), (53, 1), (T_INFO + 10, 1), (T_INFO + 12, 0.1), (T_INFO + 15, 1),
                  (N_NA + 40, 1), (N_NA + 42, 0.1), (N_NA + 45, 1)]},
        ex: {
        "eyes": [(0, (-0.08, -0.03)), (N_EX - 4, (-0.08, -0.03)), (N_EX + 2, (-0.08, 0)),
                 (T_CARDS, (-0.08, 0)), (T_CARDS + 6, (-0.03, 0.08)), (T_INFO + 40, (-0.03, 0.08)),
                 (T_INFO + 46, (-0.08, -0.03))],
        "head": [(0, 0), (N_EX - 4, 0), (N_EX + 4, 4), (T_HELP, 4), (T_HELP + 6, -2), (T_CARDS + 14, -3)],
        "gesture": [(0, 0), (N_EX - 2, 0), (N_EX + 6, 10, "halt"), (T_HELP + 2, 10), (T_HELP + 12, 0)],
        "blink": [(0, 1), (80, 1), (82, 0.1), (85, 1), (E_EX + 20, 1), (E_EX + 22, 0.1), (E_EX + 25, 1)],
        "sq": breathe(0, END)}}
    KG = {
        "eyes": [(0, (0, 0)), (T_TAKE - 2, (0, 0)), (T_TAKE, (0.08, 0)), (T_TAKE + 3, (0.08, 0)),
                 (T_TAKE + 5, (0, 0)), (T_TAKE2 - 1, (0, 0)), (T_TAKE2 + 1, (0.09, 0.01)),
                 (N_GA + 10, (0.06, 0)), (T_DEADPAN - 5, (0.06, 0)), (T_DEADPAN - 1, (0, 0)), (END, (0, 0))],
        "blink": [(0, 1), (T_TAKE2, 1), (T_TAKE2 + 3, 0.55, "halt"), (T_VERIF, 0.55), (T_VERIF + 4, 1),
                  (E_GA + 10, 1), (E_GA + 13, 0.1), (E_GA + 16, 1),
                  (T_DEADPAN, 1), (T_DEADPAN + 5, 0.1, "halt"), (T_DEADPAN + 11, 0.1), (T_DEADPAN + 16, 1)],
        "head": [(0, 0), (T_TAKE2, 0), (T_TAKE2 + 4, 3), (T_VERIF, 3), (T_VERIF + 6, -2), (T_VERIF + 12, 2),
                 (E_GA + 6, 0), (T_TRUST - 2, 0), (T_TRUST + 4, -4), (T_TRUST + 10, 4), (T_TRUST + 16, -4),
                 (T_TRUST + 22, 3), (T_TRUST + 28, 0)],
        "sq": breathe(0, END, period=64)}

    st, Z, SU = P["set"], P["z"], P["scale"]
    # ---- the side scene: the sceptic in the old room (rendered first, shown in the split screen)
    side = SC.Scene(folder / "side", deck="../../../deck/deck.json", figures_dir="../../../figures", end=END,
                    seed=P["seed"], look="none")
    side.narration("guardian", "../" + V["guardian"]["audio"], N_GA, speaker=ga, text=V["guardian"].get("text"))
    side.painted_set("../" + st["old_back"], "../" + st["old_front"])
    gx, gy = P["old_room"]["guardian"]
    side.figure(ga, x=gx, y=gy, z=Z, scale=SU, order=10, keys=KG)
    for px, py in st.get("old_steam", []):
        side.add_steam(*side.set_point(px, py, 0.5), 0.5)
    ey = side.eye_center(ga)[1]
    yy = gy + ey * SU
    side.camera([(0, [gx + 0.2, yy - 0.25, 6.6, gx, yy - 0.55, 0.25]), (END, [gx + 0.2, yy - 0.25, 6.0, gx, yy - 0.55, 0.25])])

    # ---- the main scene: the new room
    S.painted_set(st["back"], st.get("front"))
    for i, n in enumerate((bu, ex)):
        x, y = P["room"][[k for k, v in R.items() if v == n][0]]
        S.figure(n, x=x, y=y, z=Z, scale=SU, order=10 + i, keys=K[n])
    tex = folder / "tex"
    tex.mkdir(exist_ok=True)
    tx = P["texts"]
    a_sign = PR.sign(tx["sign"], tex / "sign.png")
    a_chat = PR.chat_bubble(tex / "chat_a.png")
    PR.chat_bubble(tex / "chat_b.png", left=False, tinted=True)
    a_bot = PR.mini_bot(tex / "bot.png")
    a_info = PR.info_card(tx["info_title"], [tuple(r) for r in tx["info_rows"]], tex / "info.png")
    a_q = PR.question_mark(tex / "question.png")
    a_flash = PR.key_flash(tex / "flash.png")
    cards = tx["cards"]
    a_card = 1.0
    for i, (t, u) in enumerate(cards):
        a_card = PR.project_card(t, u, tex / f"card_{i}.png")
    LX, LY, LZ = P["laptop"]
    TY = P["table_y"]
    S.sprite("sign", "tex/sign.png", a_sign, 0.75, order=5)
    S.sprite("flash", "tex/flash.png", a_flash, 0.32, order=41)
    S.sprite("info", "tex/info.png", a_info, 2.3, order=60)
    chats = [(N_BU + 10 + 8 * i, -0.3 + 0.35 * ((-1) ** i)) for i in range(6)]
    for i in range(len(chats)):
        S.sprite(f"chat{i}", f"tex/chat_{'ab'[i % 2]}.png", a_chat, 0.55, order=42)
    for i in range(3):
        S.sprite(f"bot{i}", "tex/bot.png", a_bot, 0.72, order=43)
    for i in range(len(cards)):
        S.sprite(f"card{i}", f"tex/card_{i}.png", a_card, 1.3, order=45 + i)
    S.sprite("question", "tex/question.png", a_q, 0.75, order=44)

    def hop(t0, start, end, dur=14, height=0.7):
        def at(f):
            if f < t0:
                return None
            u = min(1.0, (f - t0) / dur)
            return [start[0] + (end[0] - start[0]) * u, start[1] + (end[1] - start[1]) * u + 4 * height * u * (1 - u), 0.6]
        return at
    bots = [hop(t, (LX, LY + 0.2), (x, TY + 0.36)) for t, x in zip(BOT_T, (-1.5, -0.7, 0.1))]
    n_c = len(cards)
    per_row = (n_c + 1) // 2
    target = [(-4.8 + (i % per_row) * 2.4 + (0 if i < per_row else 0.6), 2.25 if i < per_row else 0.75,
               ((i % per_row) - 2) * -0.05) for i in range(n_c)]
    wide = [0, 0.1, 15.4, 0, -0.1, 0]
    bx, by = P["room"]["builder"]
    exx, exy = P["room"]["explorer"]
    c_bu = [bx + 0.5, by + 2.6, 9.5, bx + 0.3, by + 2.2, 0.25]
    c_ex = [exx - 0.7, exy + 2.7, 9.8, exx - 0.5, exy + 2.4, 0.25]
    c_cards = [0, 0.35, 15.8, 0, 0.25, 0]
    c_split = [-1.6, -0.2, 10.25, -1.6, -0.6, 0.25]
    cam_keys = [(0, wide), (4, wide), (N_BU + 8, c_bu), (E_BU + 2, c_bu), (N_EX + 6, c_ex), (T_CARDS - 2, c_ex),
                (T_CARDS + 12, c_cards), (SPLIT - 1, c_cards), (SPLIT, c_split), (END, c_split)]

    def stage(f, F):
        c = SC.keyed(cam_keys, f) if f < SPLIT else SC.keyed([(SPLIT, c_split), (END, [-1.5, -0.2, 9.8, -1.5, -0.6, 0.25])], f)
        F["cam"], F["look"] = [round(v, 4) for v in c[:3]], [round(v, 4) for v in c[3:]]
        sp = F["sprites"]
        s, a = SC.pop(f, 4, END, rise=6)
        sp["sign"] = {"p": [-1.0, 2.85, 0.05], "s": s, "a": a}
        sp["flash"] = {"p": [LX + 0.15 * (1 if f % 6 < 3 else -1), LY + 0.22, 0.6],
                       "s": 1.0 if any(0 <= f - t < 2 for t in KEYS) else 0, "a": 1}
        for i, (t0, dx) in enumerate(chats):
            u = (f - t0) / 32
            if 0 <= u <= 1:
                sp[f"chat{i}"] = {"p": [LX + dx + 0.3 * u, LY + 0.4 + 2.2 * u, 0.6],
                                  "s": round(0.6 + 0.4 * SC.smooth(u * 4), 3), "a": round(min(1, (1 - u) * 3), 3)}
        for i, b in enumerate(bots):
            p = b(f)
            if p:
                s, a = SC.pop(f, BOT_T[i], END, rise=6)
                wob = 0.04 * math.sin(f * 0.25 + i) if f > BOT_T[i] + 16 else 0
                sp[f"bot{i}"] = {"p": [p[0], p[1] + wob, p[2]], "s": s, "a": a}
        for i, (zx, zy, rot) in enumerate(target):
            t0, back = T_CARDS + 3 * i, SPLIT - 30 + 2 * i
            if t0 <= f <= back + 12:
                u = SC.smooth((f - t0) / 12)
                v = SC.smooth((f - back) / 12) if f > back else 0
                x0, y0 = LX, LY + 0.3
                sp[f"card{i}"] = {"p": [x0 + (zx - x0) * u + (x0 - zx) * v,
                                        y0 + (zy - y0) * u + 1.2 * u * (1 - u) + (y0 - zy) * v, 0.7 + 0.01 * i],
                                  "s": round(max(0.15, u * (1 - v)), 3), "a": 1.0, "rot": round(rot * u + 0.6 * (1 - u), 3)}
        s, a = SC.pop(f, T_INFO, T_INFO + 38, rise=6)
        sp["info"] = {"p": [0, 0.35, 9.0], "s": s, "a": a}
        s, a = SC.pop(f, T_TRUST, E_NA - 10, rise=6, overshoot=0.3)
        sp["question"] = {"p": [-0.7, -0.15 + 0.05 * math.sin(f * 0.2), 0.62], "s": s, "a": a}
    S.per_frame(stage)

    def split(f, im):
        if f < SPLIT:
            return im
        from PIL import Image
        return SC.split_frame(im, Image.open(side.dir / "frames_3d" / f"mp_{f:04d}.png").convert("RGB"),
                              SC.smooth((f - SPLIT) / 12))
    S.post(split)

    S.sound(4, "ui_pop/wide", level=-20)
    S.sound(6, "mallet/glock", ["--pitch", "C6"], level=-24)
    for f in KEYS:
        S.sound(f, "fit/key/lubed", level=-30, pan=-0.3)
    for i, (f, _) in enumerate(chats):
        S.sound(f + 2, "ui_pop/blip", level=-26 - (i % 2), pan=-0.3)
    for f in BOT_T:
        S.sound(f, "drip/bloop", level=-21, pan=-0.2)
        S.sound(f + 14, "ui_pop/step", level=-24, pan=-0.1)
    for i in range(n_c):
        S.sound(T_CARDS + 3 * i + 6, "swish/flick", level=-27, pan=-0.8 + 0.18 * i)
    for i in range(0, n_c, 3):
        S.sound(SPLIT - 30 + 2 * i + 6, "swish/soft", ["--dur", "0.4", "--apex", "0.2"], level=-28)
    S.sound(T_INFO, "logo_sting/soft_bloom", level=-21, align="start")
    S.sound(SPLIT + 4, "whoosh_fast/heavy", ["--dur", "0.6", "--apex", "0.3"], level=-20, pan=-0.4)
    S.sound(SPLIT + 12, "cut_hit/punch", level=-24, pan=-0.3)
    S.sound(T_TRUST, "ui_pop/boop", level=-22, pan=0.2)
    S.sound(N_EX + 6, "fit/whoosh.short/bamboo_swish", level=-28, pan=0.35)
    S.sound(T_TAKE, "pro_pop/tink", level=-30, pan=-0.4)
    S.sound(T_TAKE2, "swish/zing", ["--dur", "0.25", "--apex", "0.1"], level=-27, pan=-0.4)
    S.sound(T_TAKE2 + 2, "knock/snap", level=-26, pan=-0.4)
    S.sound(T_DEADPAN + 5, "fit/click/floss_lid", level=-24, pan=-0.4)
    S.sound(T_DEADPAN + 15, "fit/click/floss_lid", level=-27, pan=-0.4)
    side.build()
    S.build()
    SC.save_events(folder, {"lines": {"builder": N_BU, "explorer": N_EX, "guardian": N_GA, "narrator": N_NA},
                            "sign": 4, "bots": BOT_T, "rocks": T_ROCKS, "cards": [T_CARDS + 3 * i for i in range(n_c)],
                            "info": [T_INFO, T_INFO + 38], "split": SPLIT, "question": T_TRUST,
                            "take": T_TAKE, "take2": T_TAKE2, "deadpan": T_DEADPAN, "last": T_LAST, "end": END})
    return S, side


if __name__ == "__main__":
    S, side = main(sys.argv[1])
    if "--plan" not in sys.argv:
        side.render(steps=("synfig", "light", "3d"))
        S.render()
