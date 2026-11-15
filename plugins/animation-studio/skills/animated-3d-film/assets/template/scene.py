"""__CLIP__ - __ABOUT__

Beats (frames at 24 fps, 1..FRAMES):
  1-36     establish: the room, everybody at the table
  36-...   the action (write the beats here before coding; mark the frames of the sounds and of the spoken lines)
"""
import stage_actor as K
import stage_core as C          # noqa: F401  (primitives, lights, materials for own props)
import stage_props as P         # noqa: F401
import stage_sets as sets
import stage_shots as shots

FRAMES = __FRAMES__


def build(S):
    sets.office(S)                                   # the ready-made set; build your own from stage_props / stage_core
    cast = K.cast(S, __CAST__)
    sets.seat(cast)
    a, *rest = cast.values()

    # ---- acting: anticipation before every big move, somebody always reacts, eyes and brows on every beat
    a.mood(1, "smile")
    a.pose(14, "wave")
    a.pose(34, "rest")
    for i, c in enumerate(rest):
        c.look(16 + 3 * i, a.face_pos(1))
        c.mood(20 + 3 * i, "happy")
    # a spoken line: lip sync + head accents; returns the frame the line ends on
    # end = a.say("l01", 40)

    # ---- the edit of the clip: every S.shot / shots.* is a cut
    S.shot(1, (0, -5.4, 1.6), (0, 0.8, 0.8), loc1=(0, -4.8, 1.5), lens=40, fstop=4)        # establishing, slow push-in
    shots.medium(S, 40, a)
    shots.closeup(S, min(FRAMES - 24, 70), a)
