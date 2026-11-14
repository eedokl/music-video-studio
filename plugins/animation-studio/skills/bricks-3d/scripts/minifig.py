"""Minifigure rig from LDraw parts, joints as in LeoCAD's minifig wizard (common/minifig.cpp), in LDraw coordinates.

Origin of a figure = top of the torso (neck); the feet are 72 LDU lower. Front = -z (LDraw).
+x (LDraw) is the figure's LEFT side (it looks towards -z) - remember this for props in a hand.
Pose angles in degrees:
  head            turn about the vertical axis (+ = to the figure's left)
  arm_r / arm_l   swing forward/up (+ = forward; 90 = pointing ahead, 170 = straight up)
  hand_r / hand_l turn in the wrist
  leg_r / leg_l   swing (+ = forward; 90 = sitting)
The figure matrix F (place, turn, lean) is built by the caller (brickfilm.Film.figure_matrix).
"""
import numpy as np

import ldraw as L

PARTS = dict(torso="973", hips="3815", leg_r="3816", leg_l="3817", arm_r="3818", arm_l="3819",
             hand_r="3820", hand_l="3820", head="3626c", hair="3901")

# signs found with a test render: positive = arm/leg forward
ARM_TILT = 9.791
ARM_SIGN = -1.0
LEG_SIGN = -1.0
HEIGHT = 72                       # neck above the feet (LDU)
POSE_KEYS = ("head", "arm_r", "arm_l", "hand_r", "hand_l", "leg_r", "leg_l")


def pose(F, w=None):
    """Joint matrices {part: 4x4 LDraw} for figure matrix F and pose angles w."""
    w = w or {}
    g = lambda k: float(w.get(k, 0.0))
    m = {"torso": F}
    m["head"] = F @ L.T(0, -24, 0) @ L.RY(g("head"))
    m["hair"] = m["head"]
    m["headgear"] = m["head"]
    m["arm_l"] = F @ L.T(15.552, 8.88, 0) @ L.RZ(-ARM_TILT) @ L.RX(ARM_SIGN * g("arm_l"))
    m["arm_r"] = F @ L.T(-15.552, 8.88, 0) @ L.RZ(ARM_TILT) @ L.RX(ARM_SIGN * g("arm_r"))
    m["hand_l"] = m["arm_l"] @ L.T(5, 19, -10) @ L.RX(45) @ L.RZ(g("hand_l"))
    m["hand_r"] = m["arm_r"] @ L.T(-5, 19, -10) @ L.RX(45) @ L.RZ(g("hand_r"))
    m["hips"] = F @ L.T(0, 32, 0)
    m["leg_r"] = F @ L.T(0, 44, 0) @ L.RX(LEG_SIGN * g("leg_r"))
    m["leg_l"] = F @ L.T(0, 44, 0) @ L.RX(LEG_SIGN * g("leg_l"))
    return m


def build(name, colours, F, collection=None, parts=None):
    """colours: {part: LDraw colour code} (parts without a colour are left out, e.g. no hair for a robot);
    parts: other part numbers (e.g. hair="62711", headgear="14045"). -> {part: Blender object}"""
    obs = {}
    for k, ld in dict(PARTS, **(parts or {})).items():
        if k not in colours or ld in (None, ""):
            continue
        obs[k] = L.part(ld, colours[k], None, f"{name}_{k}", collection)
    place(obs, F)
    return obs


def place(obs, F, w=None):
    for k, mm in pose(F, w).items():
        if k in obs:
            obs[k].matrix_world = L.to_blender(mm)


def head_point(x, z, y_floor=0.0, hop=0.0):
    """LDraw point of the face centre of a standing figure at (x, z)."""
    return np.array([x, y_floor - HEIGHT - 12 - hop, z])
