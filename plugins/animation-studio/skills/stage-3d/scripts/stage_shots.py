# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""Camera helpers: character close-ups, two-shots, orbit points. All return the Cam (see core.Stage.shot)."""
import math

from stage_core import V


def _dir(heading_deg, yaw_deg):
    a = math.radians(heading_deg + yaw_deg)
    return V((math.sin(a), -math.cos(a), 0))


def closeup(S, f0, c, dist=1.9, yaw=14, up=0.03, lens=65, fstop=2.0, push=0.08, f1=None, dz=-0.04, shake=0.003,
            fref=None, ease="io", aim_dx=0.0):
    """close-up on a character's face. yaw: camera angle around the character (0 = straight in front, + = from
    the character's left/screen right). push: fraction of the distance the camera creeps in during the shot.
    fref: frame used to read the character's position (default f0)."""
    f = fref or f0
    p = c.face_pos(f) + V((aim_dx, 0, dz * c.size))
    d = _dir(c.heading.eval(f), yaw)
    loc0 = p + d * dist * (0.55 + 0.45 * c.eye_z * c.size) + V((0, 0, up))
    loc1 = p + d * dist * (1 - push) * (0.55 + 0.45 * c.eye_z * c.size) + V((0, 0, up))
    return S.shot(f0, loc0, p, loc1=loc1 if push else None, f1=f1, lens=lens, fstop=fstop, shake=shake, ease=ease,
                  focus=c.face_pos(f, 0.12 * c.size))


def medium(S, f0, c, dist=3.0, yaw=10, up=0.1, lens=50, fstop=2.4, push=0.06, f1=None, shake=0.003, fref=None,
           dz=-0.15, aim_dx=0.0):
    """waist-up shot"""
    return closeup(S, f0, c, dist, yaw, up, lens, fstop, push, f1, dz, shake, fref, aim_dx=aim_dx)


def two_shot(S, f0, a, b, dist=3.0, yaw=0, up=0.15, lens=50, fstop=2.8, push=0.05, f1=None, shake=0.003, dz=-0.1):
    """frame two characters; camera in front of their midpoint (assumes both roughly face -Y)"""
    pa, pb = a.face_pos(f0), b.face_pos(f0)
    p = (pa + pb) / 2 + V((0, 0, dz))
    d = _dir(0, yaw)
    spread = (pa - pb).length
    loc0 = p + d * (dist + spread * 0.6) + V((0, 0, up))
    loc1 = p + d * (dist + spread * 0.6) * (1 - push) + V((0, 0, up))
    return S.shot(f0, loc0, p, loc1=loc1 if push else None, f1=f1, lens=lens, fstop=fstop, shake=shake, focus=p)


def ots(S, f0, speaker, listener, lens=70, fstop=2.0, side=1, back=0.9, up=0.12, push=0.04, f1=None):
    """over-the-shoulder: camera behind the listener looking at the speaker"""
    ps, pl = speaker.face_pos(f0), listener.face_pos(f0)
    d = (pl - ps)
    d.z = 0
    d.normalize()
    sidev = V((-d.y, d.x, 0)) * side
    loc0 = pl + d * back + sidev * 0.32 * listener.size + V((0, 0, up))
    return S.shot(f0, loc0, ps, loc1=loc0 - d * push, f1=f1, lens=lens, fstop=fstop, focus=ps, shake=0.003)
