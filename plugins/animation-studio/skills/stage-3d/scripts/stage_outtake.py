# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""Outtakes "from the shoot" for the end credits (the blooper reel of an animated feature): every take starts with a
clapperboard held into the lens, then a shot of the film goes wrong and the actors fall out of their parts.

    import stage_outtake as O
    O.take(S, (0.4, -3.2, 1.0), mo.face_pos(1), scene="12", take="37")   # camera + clapperboard, frames 1..24
    ... the shot, then what goes wrong ...
    O.crack_up(mo, 70, 110)              # laughs: head back, shoulders shake, babbling mouth, a happy face
    O.to_camera(kit, 64, S)              # looks into the lens (caught)

A clip is an outtake by its entry in project.json: {"name": "outtake_01", "frames": 120, "part": "credits",
"credits": "outtake"} (animated-3d-film: film3d.py clip <folder> outtake_01 --frames 120 --credits outtake). Its
module may list sound effects for the credits: SFX = [(frame, "earshot id or file", level), ...].
"""
import math

import bpy
import stage_core as _C
from mathutils import Vector
from stage_core import Node, box, capsule, empty, mat, text

V = Vector
SLATE = {"title": None, "director": "", "camera": ""}   # texts on the board; title default: project.json "title"


def _title():
    if SLATE["title"]:
        return SLATE["title"]
    import json
    pj = _C.PROJECT / "project.json"
    try:
        return str(json.loads(pj.read_text(encoding="utf-8")).get("title", "TAKE")).upper()[:22]
    except (OSError, ValueError):
        return "TAKE"


def clapperboard(S, cam, aim, scene="1", take="1", f_in=1, f_clap=14, f_out=24, dist=1.1, size=1.8, name="slate",
                 title=None, director=None, camera=None):
    """a clapperboard on a black sleeve: comes up from below into the middle of the picture `dist` m in front of
    the camera (cam -> aim), claps at f_clap and goes down again after f_out. Keep the camera still meanwhile.
    -> the root Node"""
    k, z = V(cam), V(aim)
    d = (z - k).normalized()
    p = k + d * dist
    yaw = math.degrees(math.atan2(-d.x, d.y))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, d.z))))
    black = mat("slate_black", "#111114", rough=0.55)
    white = mat("slate_white", "#F2EEE6", rough=0.6)
    sleeve = mat("slate_sleeve", "#0C0C10", rough=0.8)
    g = Node(S, empty(name, tuple(p), rot=(pitch, 0, yaw)))
    g.obj.scale = (size,) * 3
    ld = bpy.data.lights.new(name + "_light", "AREA")
    ld.energy, ld.size = 25.0, 0.6
    lo = bpy.data.objects.new(name + "_light", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.parent = g.obj
    lo.location = (0.25, -0.45, 0.25)
    lo.rotation_euler = (math.radians(60), 0, math.radians(30))
    lo.visible_camera = False
    board = Node(S, empty(name + "_board", (0, 0, 0), g))
    box(name + "_slab", (0.30, 0.012, 0.21), (0, 0, 0), black, board, bevel=0.004)
    lines = ((title or _title(), 0.040, 0.055), (f"SCENE {scene}    TAKE {take}", 0.026, -0.005),
             (f"DIR: {director if director is not None else SLATE['director']}    "
              f"CAM: {camera if camera is not None else SLATE['camera']}".strip(), 0.016, -0.055))
    for i, (txt, h, zz) in enumerate(lines):
        if txt.replace("DIR:", "").replace("CAM:", "").strip():
            text(f"{name}_t{i}", txt, h, white, (0, -0.008, zz), board, extrude=0.0005)
    box(name + "_rule", (0.27, 0.002, 0.003), (0, -0.007, 0.028), white, board, bevel=0.0)
    hinge = Node(S, empty(name + "_hinge", (-0.15, 0, 0.115), board))           # the clapstick, open = 28 degrees
    box(name + "_stick", (0.30, 0.014, 0.035), (0.15, 0, 0.0175), black, hinge, bevel=0.003)
    for i in range(5):
        box(f"{name}_stripe{i}", (0.025, 0.002, 0.035), (0.03 + 0.06 * i, -0.008, 0.0175), white, hinge, bevel=0.0,
            rot=(0, -35, 0))
    capsule(name + "_arm", (0.02, 0.03, -0.10), (0.05, 0.10, -0.42), 0.035, 0.04, sleeve, board)
    hinge.rot(1, 0, -28, 0, "hold")
    hinge.rot(max(1, f_clap - 3), 0, -28, 0, "hold")
    hinge.rot(f_clap, 0, 0, 0, "in")
    board.loc(1, 0, 0, -0.45, "hold")
    board.loc(f_in, 0, 0, -0.45, "hold")
    board.loc(f_in + 6, 0, 0, 0, "out")
    board.loc(f_out, 0, 0, 0, "hold")
    board.loc(f_out + 6, 0, 0, -0.50, "in")
    return g


def take(S, cam, aim, scene="1", take="1", lens=40, fstop=4.0, f_clap=14, f_out=24, **kw):
    """the opening of an outtake: a still camera (cut at frame 1) and the clapperboard in front of it.
    More shots of the take: S.shot(...) as usual. -> the clapperboard Node"""
    S.shot(1, tuple(cam), tuple(aim), lens=lens, fstop=fstop, focus=tuple(aim))
    return clapperboard(S, cam, aim, scene, take, 1, f_clap, f_out, **kw)


def crack_up(c, f0, f1, amp=1.0):
    """an actor breaks up laughing from f0 to f1: a happy face, the head thrown back, shoulders and body shaking,
    a babbling open mouth, a little bounce - and back to calm at the end"""
    c.mood(f0, "excited")
    c.head_to(f0, pitch=-14 * amp, roll=6 * amp)
    c.head_to(min(f1, f0 + 14), pitch=8 * amp, roll=-4 * amp)
    c.head_to(f1, 0, 0, 0)
    c.babble(f0 + 2, f1 - 4, speed=1.4)
    c.tremble(f0, f1, amp=2.2 * amp)
    c.bounce(f0, f1, per=6, h=0.025 * amp)
    c.mood(f1 + 6, "smile")
    return c


def to_camera(c, f, S):
    """the actor looks straight into the lens (the camera of the shot at frame f)"""
    shots = [(f0, cm) for f0, cm in S.shots if f0 <= f]
    if not shots:
        return c
    cam = max(shots, key=lambda s: s[0])[1]
    p = V(cam.pending[0]) if getattr(cam, "pending", None) else cam.obj.location
    c.look(f, tuple(p))
    return c
