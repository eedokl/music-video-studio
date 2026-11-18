# Runs inside Blender's Python (bpy) - started by test_animated_3d_film.py.
"""A minimal realistic actor for the tests: the Rigify human metarig, generated, with a few primitive meshes bound
by automatic weights (body, head, arms with hands, legs with shoes) and the face sliders of the actor contract
(stage_rig.FACE) on the head bone, driving shape keys of the head.

  blender -b --factory-startup --python make_actor.py -- <out folder>/<name>/figur.blend
"""
import sys

import addon_utils
import bpy
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
addon_utils.enable("rigify", default_set=True)
if "rigify" not in bpy.context.preferences.addons:
    for m in addon_utils.modules():
        if m.__name__.endswith("rigify"):
            addon_utils.enable(m.__name__, default_set=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
for m in addon_utils.modules():
    if m.__name__.endswith("rigify"):
        addon_utils.enable(m.__name__, default_set=True)

bpy.ops.object.armature_human_metarig_add()
meta = bpy.context.active_object
meta.name = "metarig"
bpy.ops.pose.rigify_generate()
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE" and o is not meta)
rig.name = "Testy_Rig"
B = rig.data.bones


def part(name, kind, a, b, r):
    """a capsule/box between the heads of two bones (world, rest pose)"""
    p0, p1 = a, b
    mid, d = (p0 + p1) / 2, (p1 - p0)
    if kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=mid, segments=24, ring_count=12)
    else:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=max(d.length, 0.02), location=mid, vertices=16)
        o = bpy.context.active_object
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = d.normalized().to_track_quat("Z", "Y")
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    m = o.modifiers.new("sub", "SUBSURF")
    m.levels = m.render_levels = 1
    return o


H = lambda n: B["ORG-" + n].head_local.copy()      # noqa: E731
T = lambda n: B["ORG-" + n].tail_local.copy()      # noqa: E731
parts = [part("Body", "cyl", H("spine"), H("spine.004"), 0.16),
         part("Head", "sphere", H("spine.006"), T("spine.006"), 0.13)]
for s in "LR":
    parts += [part(f"Arm.{s}", "cyl", H(f"upper_arm.{s}"), H(f"hand.{s}"), 0.045),
              part(f"Hand.{s}", "sphere", H(f"hand.{s}"), T(f"hand.{s}"), 0.05),
              part(f"Leg.{s}", "cyl", H(f"thigh.{s}"), H(f"foot.{s}"), 0.07),
              part(f"Shoe.{s}", "cyl", H(f"foot.{s}") * 1.0, T(f"toe.{s}"), 0.05)]
bpy.ops.object.select_all(action="DESELECT")
for o in parts:
    o.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type="ARMATURE_AUTO")

# face sliders: custom properties on the head bone driving shape keys of the head
head = bpy.data.objects["Head"]
head.shape_key_add(name="Basis")
pb = rig.pose.bones["head"]
for key, move in (("Mund_auf", (0, 0, -0.03)), ("Laecheln", (0.02, 0, 0.01)), ("Lider_zu", (0, 0, -0.01)),
                  ("Braue_L_hoch", (0, 0, 0.02)), ("Braue_R_hoch", (0, 0, 0.02))):
    pb[key] = 1.0 if key in ("Laecheln", "Braue_L_hoch", "Braue_R_hoch") else 0.0
    kb = head.shape_key_add(name=key)
    kb.slider_max = 2.0
    for v, vb in zip(head.data.vertices, kb.data, strict=True):
        if v.co.y < 0:                                           # front half of the head
            vb.co = v.co.copy() + Vector(move)
    fc = kb.driver_add("value")
    var = fc.driver.variables.new()
    var.targets[0].id = rig
    var.targets[0].data_path = f'pose.bones["head"]["{key}"]'
    fc.driver.expression = var.name
bpy.ops.mesh.primitive_plane_add(size=4)
bpy.context.active_object.name = "Boden"                          # left out by the stage (not under the rig)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("ACTOR WRITTEN", out, len(parts), "meshes", flush=True)
