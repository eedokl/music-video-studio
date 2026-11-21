"""__CLIP__ - __ABOUT__

A clip of a film on a song: every frame comes from the song (stage_song: SG.f / SG.word / SG.beats), never a number
typed in - a corrected word time or a moved cut then moves the acting with it.

Beats (write them here before coding: what happens on which word):
  line ..  "..."   ->  ...
"""
import stage_actor as K
import stage_core as C          # noqa: F401  (primitives, lights, materials for own props)
import stage_props as P         # noqa: F401
import stage_sets as sets
import stage_shots as shots
import stage_song as SG

CLIP = "__CLIP__"
FRAMES = __FRAMES__


def build(S):
    sets.office(S)                                   # the ready-made set; build your own from stage_props / stage_core
    cast = K.cast(S, __CAST__)
    sets.seat(cast)
    a, *rest = cast.values()

    # ---- singing: the lip sync of every lyric line of this clip on its performer(s) (song_plan.json "who")
    said = {ln["n"]: (f0, end) for ln, f0, end in SG.sing(cast, CLIP)}
    # ---- the beat in the bodies - every figure differently (amp, half time), or they look like one puppet
    for i, c in enumerate(cast.values()):
        SG.groove(c, 1, FRAMES, CLIP, 0.5 + 0.4 * i, half=i % 2 == 1)

    # ---- acting on the words: one picture per line, placed on the word that names it
    # hit = SG.word(CLIP, "word") or 40              # None when the word is not sung in this clip
    # a.pose(hit - 3, "present", "out")
    for n, (f0, end) in said.items():
        for c in rest:
            c.look(f0 + 4, a.face_pos(f0))

    # ---- the edit of the clip: every S.shot / shots.* is a cut - cut on downbeats (SG.bars) or on a word
    S.shot(1, (0, -5.4, 1.6), (0, 0.8, 0.8), loc1=(0, -4.8, 1.5), lens=40, fstop=4)
    bars = [b for b in SG.bars(CLIP) if 24 < b < FRAMES - 24]
    if bars:
        shots.medium(S, bars[len(bars) // 2], a)
