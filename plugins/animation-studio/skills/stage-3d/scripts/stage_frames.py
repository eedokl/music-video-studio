# Runs inside Blender's Python (bpy) - used by stage_film.py.
"""Per-frame fingerprints of a built clip: re-render only the frames that look different.

After a change (an arm that went through the table, shoes in the floor, a later gag, a new line) usually only some
frames of a clip change. `fingerprints(S)` steps through the frames once (no rendering, a fraction of a second per
frame) and hashes for every frame what the picture is made from:
  - every object of the scene: its evaluated world matrix and render visibility, what its shape is made from (the
    mesh / curve / text data, shape key values = faces, modifier and constraint settings, the pose of a rig) - not
    the deformed vertices: multi-threaded modifiers give them a different last bit on every build,
  - lights (type, colour, power, cone, size), cameras (lens, sensor, depth of field, clipping),
  - every node value of the materials, the world, light and node groups (animated glows, haze, colours),
and once for the clip (`static`): the render settings, image files (path + time) and the frame range.
The fingerprints go to out/<clip>/<q>/frames.json. `changed(old, new, blur)` lists the frames whose hash differs
(+ the neighbours when motion blur is on: a blurred frame sees half a frame to each side); a different `static`
means every frame.
"""
import hashlib
import json
import os
from pathlib import Path

import bpy
import numpy as np

DIGITS = 4                           # 0.1 mm / 1e-4 - float noise between two builds must not count as a change
VERSION = 1


def _h():
    return hashlib.blake2b(digest_size=12)


def _num(h, xs):
    h.update(np.round(np.asarray(xs, dtype=np.float64), DIGITS).tobytes())


def _val(h, v):
    """an RNA value (float, int, bool, str, vector, colour, ID) into the hash"""
    if v is None:
        h.update(b"~")
    elif isinstance(v, (bool, int, float)):
        _num(h, [float(v)])
    elif isinstance(v, str):
        h.update(v.encode("utf-8", "replace"))
    elif hasattr(v, "name_full"):
        h.update(v.name_full.encode("utf-8", "replace"))
    else:
        try:
            _num(h, [float(x) for x in v])
        except (TypeError, ValueError):
            h.update(repr(v).encode("utf-8", "replace"))


def _tree(h, nt, seen):
    """every node input default value and the main node settings of a node tree (and its groups)"""
    if nt is None or nt.name_full in seen:
        return
    seen.add(nt.name_full)
    h.update(nt.name_full.encode("utf-8", "replace"))
    for n in nt.nodes:
        h.update(n.bl_idname.encode())
        if n.mute:
            h.update(b"m")
        for s in n.inputs:
            if hasattr(s, "default_value") and not s.is_linked:
                _val(h, s.default_value)
        for k in ("blend_type", "operation", "data_type", "interpolation", "image"):
            if hasattr(n, k):
                _val(h, getattr(n, k))
        if n.bl_idname == "ShaderNodeValToRGB":
            for e in n.color_ramp.elements:
                _num(h, [e.position, *e.color])
        if getattr(n, "node_tree", None) is not None:
            _tree(h, n.node_tree, seen)
    for link in nt.links:
        h.update(f"{link.from_node.name}.{link.from_socket.identifier}>{link.to_node.name}."
                 f"{link.to_socket.identifier}".encode("utf-8", "replace"))


def _props(h, owner):
    """the plain RNA settings of a modifier / constraint (+ its custom properties: geometry node inputs)"""
    for pr in owner.bl_rna.properties:
        if pr.identifier in ("rna_type", "name", "show_viewport", "show_in_editmode", "show_on_cage", "show_expanded",
                             "is_active", "is_override_data_local", "persistent_uid", "execution_time"):
            continue
        if pr.type in ("BOOLEAN", "INT", "FLOAT", "ENUM", "STRING", "POINTER"):
            try:
                v = getattr(owner, pr.identifier)
            except AttributeError:
                continue
            if pr.type == "ENUM" and isinstance(v, set):
                v = ",".join(sorted(v))
            if pr.type == "POINTER" and v is not None and not hasattr(v, "name_full"):
                continue
            _val(h, v)
    try:
        keys = list(owner.keys())                    # geometry node inputs are custom properties of the modifier
    except TypeError:
        keys = []
    for k in keys:
        try:
            _val(h, owner[k])
        except (TypeError, KeyError):
            pass


def _rest(ob, cache):
    """hash of the data block itself (rest vertices, curve points, text) - once per run"""
    d = ob.data
    if d is None or d.name_full in cache:
        return cache.get(getattr(d, "name_full", ""), "")
    h = _h()
    if ob.type == "MESH":
        co = np.empty(len(d.vertices) * 3, dtype=np.float32)
        d.vertices.foreach_get("co", co)
        _num(h, co)
        _num(h, [len(d.polygons), len(d.loops)])
    elif ob.type in ("CURVE", "SURFACE"):
        for sp in d.splines:
            for b in sp.bezier_points:
                _num(h, [*b.co, *b.handle_left, *b.handle_right, b.radius, b.tilt])
            for pt in sp.points:
                _num(h, [*pt.co, pt.radius, pt.tilt])
        _num(h, [d.bevel_depth, d.extrude, d.offset, float(d.bevel_resolution)])
    if ob.type == "FONT":
        h.update(d.body.encode("utf-8", "replace"))
        _num(h, [d.size, d.extrude, d.bevel_depth, d.space_line, d.space_character, d.offset_x, d.offset_y])
    for m in getattr(d, "materials", []):
        _val(h, m)
    cache[d.name_full] = h.hexdigest()
    return cache[d.name_full]


def _geometry(h, ob, e, cache):
    """what the shape of an object is made from - not the deformed vertices (multi-threaded modifiers give them a
    different last bit on every build): the data block, shape key values, modifier and constraint settings and the
    pose of an armature"""
    h.update(_rest(ob, cache).encode())
    keys = getattr(ob.data, "shape_keys", None)
    if keys is not None:
        _num(h, [k.value for k in keys.key_blocks] + [float(k.mute) for k in keys.key_blocks])
    for m in ob.modifiers:
        h.update(m.type.encode())
        _num(h, [float(m.show_render)])
        _props(h, m)
    for c in ob.constraints:
        _props(h, c)
    if ob.type == "ARMATURE" and e.pose is not None:
        for pb in e.pose.bones:
            _num(h, [x for row in pb.matrix for x in row])


def _object(h, ob, dg, seen, cache):
    e = ob.evaluated_get(dg)
    h.update(ob.name_full.encode("utf-8", "replace"))
    _num(h, [float(ob.hide_render)])
    if ob.hide_render:
        return
    _num(h, [x for row in e.matrix_world for x in row])
    _geometry(h, ob, e, cache)
    d = ob.data
    if ob.type == "LIGHT":
        for k in ("type", "color", "energy", "spot_size", "spot_blend", "shadow_soft_size", "size", "size_y",
                  "use_shadow", "angle"):
            if hasattr(d, k):
                _val(h, getattr(d, k))
        if getattr(d, "node_tree", None) is not None:
            _tree(h, d.node_tree, seen)
    elif ob.type == "CAMERA":
        for k in ("type", "lens", "ortho_scale", "sensor_width", "shift_x", "shift_y", "clip_start", "clip_end"):
            _val(h, getattr(d, k))
        f = d.dof
        _val(h, [float(f.use_dof), f.aperture_fstop, f.focus_distance])
        if f.focus_object is not None:
            _num(h, [x for row in f.focus_object.evaluated_get(dg).matrix_world for x in row])
    if ob.instance_type == "COLLECTION" and ob.instance_collection:
        for c in ob.instance_collection.all_objects:
            _object(h, c, dg, seen, cache)


def _frame(sc, dg, cache):
    h, seen = _h(), set()
    _val(h, sc.camera)
    for ob in sorted(sc.objects, key=lambda o: o.name_full):
        _object(h, ob, dg, seen, cache)
    if sc.world is not None:
        _tree(h, sc.world.node_tree, seen)
    for m in sorted((m for m in bpy.data.materials if m.users), key=lambda m: m.name_full):
        _val(h, [*m.diffuse_color])
        _tree(h, m.node_tree, seen)
    return h.hexdigest()


def _static(sc):
    h = _h()
    r = sc.render
    for k in ("engine", "resolution_x", "resolution_y", "resolution_percentage", "film_transparent",
              "use_motion_blur", "motion_blur_shutter", "motion_blur_position", "pixel_aspect_x", "pixel_aspect_y"):
        _val(h, getattr(r, k, None))
    v = sc.view_settings
    _val(h, [v.view_transform, v.look, v.exposure, v.gamma])
    for owner in (getattr(sc, "cycles", None), getattr(sc, "eevee", None)):
        if owner is None:
            continue
        for k in ("samples", "use_denoising", "denoiser", "max_bounces", "volume_bounces", "transparent_max_bounces",
                  "taa_render_samples", "use_shadows", "use_raytracing", "volumetric_samples", "volumetric_tile_size",
                  "use_volumetric_shadows", "seed", "use_animated_seed", "adaptive_threshold"):
            if hasattr(owner, k):
                _val(h, getattr(owner, k))
    for im in sorted(bpy.data.images, key=lambda i: i.name_full):
        if not im.users:
            continue
        p = bpy.path.abspath(im.filepath) if im.filepath else ""
        h.update(f"{im.name_full}|{p}|{os.path.getmtime(p) if p and os.path.exists(p) else 0}".encode("utf-8", "replace"))
    _val(h, [sc.frame_start, sc.frame_end, VERSION])
    return h.hexdigest()


def fingerprints(S, frames):
    """{"static": hash, "frames": {"1": hash, ...}} for frames 1..frames (the scene stays on the frame it had)"""
    sc = S.scene
    keep = sc.frame_current
    out, cache = {"version": VERSION, "static": _static(sc), "frames": {}}, {}
    for f in range(1, frames + 1):
        sc.frame_set(f)
        out["frames"][str(f)] = _frame(sc, bpy.context.evaluated_depsgraph_get(), cache)
    sc.frame_set(keep)
    return out


def changed(old, new, blur, frames):
    """frame numbers whose picture is different (all on a different static part or format)"""
    if not old or old.get("version") != new["version"] or old.get("static") != new["static"]:
        return list(range(1, frames + 1))
    o, n = old.get("frames", {}), new["frames"]
    diff = {int(f) for f, v in n.items() if o.get(f) != v}
    if blur:                                  # a motion-blurred frame sees its neighbours
        diff |= {f + d for f in diff for d in (-1, 1)}
    return sorted(f for f in diff if 1 <= f <= frames)


def runs(frames):
    """[1, 2, 3, 7] -> [(1, 3), (7, 7)]"""
    out = []
    for f in frames:
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return [tuple(r) for r in out]


def load(path):
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def save(path, fp):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".part.json")
    tmp.write_text(json.dumps(fp), encoding="utf-8")
    os.replace(tmp, p)
