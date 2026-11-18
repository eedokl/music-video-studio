"""__CLIP__ - outtake for the end credits: __ABOUT__

A take "from the shoot": the clapperboard (frames 1-30), a shot of the film is played straight, then something goes
wrong and the actors fall out of their parts (laugh, look into the lens, wave it off), a stagehand may walk in.
Keep the actions big and clear: the credits show the take in a window beside the text, not full screen.
SFX = [(frame, "earshot id or file", level)] - sound effects of the take (the credits mix them in).
"""
import stage_actor as K
import stage_outtake as O
import stage_sets as sets

FRAMES = __FRAMES__
SFX = [(14, "fit/hit/bamboo_tok", 0.7)]               # the clap of the clapperboard


def build(S):
    sets.office(S)
    cast = K.cast(S, __CAST__)
    sets.seat(cast)
    a, *rest = cast.values()
    O.take(S, (0.0, -3.6, 1.0), a.face_pos(1), scene="12", take="37")      # camera + clapperboard

    # ---- the shot, played straight
    a.mood(30, "focus")
    a.pose(34, "present")
    # ---- it goes wrong (a prop falls, a line is fluffed, a figure bumps into the set) ...
    a.take(56)
    # ---- ... and they break up
    O.crack_up(a, 64, min(FRAMES - 6, 104))
    for i, c in enumerate(rest):
        O.crack_up(c, 68 + 4 * i, min(FRAMES - 6, 104))
    if rest:
        O.to_camera(rest[0], 100, S)
