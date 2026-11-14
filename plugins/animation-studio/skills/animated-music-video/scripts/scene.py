# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "svgelements==1.9.6"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Build (and render) one section of the song as a Synfig scene: a set plus figures that sing, listen, dance and act.

Reads project.json (section, figures, gestures, screen events, actions, lights ...), analysis/song_sheet.json (beats,
words, lines) and analysis/assignment.json (which mouth each figure has when). Everything runs on the song timeline.

Behaviour per beat and figure (first match wins):
  action    an "actions" span runs (typing on a keyboard / air guitar) -> own arms IN FRONT of the body, rig arm off
  gesture   a word from "gestures" is sung now -> scare / cheer / point / scratch / nod / sad
  freeze    the song is quiet (9 dB under its average) -> everybody holds still
  dance     chorus (markers chorus/refrain/hook/drop, or repeated lyric lines) or "dance": "always"; the style per
            figure (arms / bounce / step / twist) comes from the creative seed unless "dance_style" fixes it
  sing      own mouth open -> open gesture, nod on the one
  listen    somebody else sings -> look at them, sway
  idle      otherwise: light sway
Every mode leans the whole body a little (dance 5°, sing 3°, listen 2° toward the singer, idle 1.5°); parts hanging
from the head (haare_hinten, hair, ponytail, antenna ...) turn with the head and swing behind it on a spring.
Figures with "entrance": "flicker" appear like a hologram the first time they sing.
The Computer ("kind": "screen") is a face inside the set's screen rectangle (eyes, cheeks, lip sync); "screen" events
in project.json replace the face for a moment with big text on the screen (a terminal line, a price, a warning);
"screen_badges" keep a label in the corner, "screen_meter" draws a usage bar that fills / turns red on words.

Scene features (project.json keys, documented in SKILL.md; defaults vary with the creative seed):
  "actions"      typing (keyboard prop, alternating key strikes on the beats, keys light up, clicks for sounds.py) and
                 guitar (air guitar, strum arm swings around the elbow on every beat or half beat)
  section "light"  spotlight (dark stage, cones; a figure appears only in its own light while it sings), disco
                 (coloured cones alternating on the beat + seeded confetti), night (room dark from a time/word/silence,
                 the screen keeps glowing, light again on a word)
  "silhouettes"  a dark figure between two set layers (inside the room window) or as a big shadow, on words
  section "inset"  round narrator inset in a corner (lip sync), hidden while that figure is on screen, when another
                 figure sings or after a pause longer than "hold" (2 s)
  section "kind": "panels"   comic page; hard cuts on every lyric line between panels (images or figures)
  section "shot": "screen"   close-up of the Computer's screen (room behind darkened, slow push-in)
  section "camera_move": true   marks camera moves for film-finish fps48.py (panels count as camera moves);
                 "shots": [] / [song s] = the known hard cuts (fps48 then skips its pixel-difference cut detection)
  section "kind": "external" + "inset"   frames from another renderer (multiplane, comic flight): only the inset is
                 rendered (transparent, scenes/<section>_inset/) and laid over scenes/<section>/ by captions.apply
  section "panel_aspect": "16:9"   panels shaped like the screen, the camera covers them (no neighbours visible)
  section "pulse"  heartbeat camera {"every": 0.85, "at": "silence" | "from" | "word", "to" | "until_word", "amount", "push"}
  section "show"   {"lia": {"line": .. | "line_index" | "word" | "from", "while": "singing" | "always"}} figure appears
                 only from then on (flicker), optionally only while it sings
  "screen" events  "tint": "#6b1a1a" (+ "tint_until": word) colours the whole screen; "sections"/"not_sections"
                 "window": "Context Window" pops an app window out over the screen instead of text on it
  "steam"        puffs rise from a figure's head from a word's line until a word (brain melting, overheating)

Rig convention of the SVG figures (see assets/figures/tim.svg): groups arm_l, arm_r, kopf (head), auge_l/r (eyes),
pupille_l/r (pupils), brauen (brows); pivots pivot_<part>; pivot_mund marks the mouth (drawn by lip sync); feet at
SVG point (200, 590). The German part ids are the convention of the bundled figures - keep them for new figures.

Usage: uv run scene.py <section> [--project .] [--render] [--jobs 8]
Output: scenes/<section>.sif (editable in Synfig Studio), with --render scenes/<section>/f.0000.png ...,
        analysis/actions_<section>.json (gesture times, key clicks for sounds.py)
"""
import argparse
import json
import subprocess
import sys

import _studio  # noqa: E402
_studio.use('song-analysis', 'toon-2d', 'characters')
import creative  # noqa: E402
from song_project import Project
from sif import canvas
from scene_context import SceneContext, VIEW
from scene_inset import inset_layer
from scene_panels import panels_section
from scene_stage import stage_scene

# The layer builders live in modules next to this script; each takes the SceneContext built once per run:
#   scene_context  SceneContext (project, section times, beats / words / lines, who sings when, places, action
#                  spans, lights, screen events) + timing helpers, constants, box / as_list / load_set
#   scene_figures  figure(): per-beat behaviour, lip sync, hair spring, aura, steam, typing / air guitar
#   scene_screen   the Computer's face, text screens, tints, badges, meter, app windows
#   scene_props    props and silhouettes          scene_lights   spotlight / disco / night
#   scene_stage    a regular section: set, screen, figures, lights, camera
#   scene_panels   "kind": "panels" comic page    scene_inset    the round narrator inset
#   scene_fx       drawing helpers (arms, keyboard, guitar, cones, confetti, silhouette, inset frame)


def render(sif, frames, jobs):
    subprocess.run([sys.executable, str(_studio.skill_dir("toon-2d") / "scripts" / "synfig_parallel.py"), str(sif),
                    str(frames), "--jobs", str(jobs)], check=True)


def external_section(c, a, out_dir):
    """Frames come from another renderer: only the inset (transparent track) and the caption are done here."""
    import captions
    P, N = c.P, c.N
    top = inset_layer(c) if c.A.get("inset") else []
    if top:                                           # the inset as a transparent track -> scenes/<section>_inset/
        sif = out_dir / f"{a.section}_inset.sif"
        sif.write_text(canvas(top, w=P.size[0], h=P.size[1], end=N, name=f"{P['name']} - {a.section} inset", view=VIEW), encoding="utf-8")
        print(f"-> {sif.relative_to(P.dir)}: narrator inset over the external frames ({N} frames)")
        if a.render:
            ins = out_dir / f"{a.section}_inset"
            if ins.exists():
                for p_ in ins.glob("*.png"):
                    p_.unlink()
            render(sif, ins, a.jobs)
    elif c.A.get("inset"):
        print("   inset: nobody of the inset figures sings in this section - no inset")
    if a.render and (c.A.get("caption") or top):
        captions.apply(P, a.section)
    elif not a.render:
        print("   external section: run with --render to lay the inset/caption over scenes/%s/" % a.section)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("section")
    ap.add_argument("--project", default=".")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    P = Project(a.project)
    P.check("animated-music-video")                 # project.json validated before any long step
    c = SceneContext.build(P, a.section)
    A, N, kind, beats, act = c.A, c.N, c.kind, c.beats, c.act

    # ---------- compose ----------
    out_dir = P.dir / "scenes"
    out_dir.mkdir(exist_ok=True)
    if kind == "external":                                # frames come from another renderer: only post passes here
        external_section(c, a, out_dir)
        return
    if kind == "panels":
        scene, hidden_at, info = panels_section(c)
        top = inset_layer(c, hidden_at)
    else:
        scene = stage_scene(c)
        top = inset_layer(c)
        info = ""
    sif = out_dir / f"{a.section}.sif"
    sif.write_text(canvas([scene] + top, w=P.size[0], h=P.size[1], end=N, name=f"{P['name']} - {a.section}", view=c.SET.get("view", VIEW) if kind != "panels" else VIEW),
                   encoding="utf-8")
    (P.analysis / f"actions_{a.section}.json").write_text(
        json.dumps([{"t": round(t0 + 0.1, 3), "figure": k, "gesture": g} for t0, t1, k, g in c.gest] + c.action_log,
                   ensure_ascii=False), encoding="utf-8")
    sung = {k: sum(1 for b in beats if act(k, b["t"])) for k in c.names}
    extra = []
    for k, sp in c.act_spans.items():
        for t0, t1, what, speed in sp:
            extra.append(f"{k} {what} {t0:.1f}-{t1:.1f}")
    feats = [x for x in (f"actions [{', '.join(extra)}]" if extra else "", f"lights {sorted(c.lights)}" if c.lights else "",
                         "inset" if A.get("inset") else "", info) if x]
    print(f"-> {sif.relative_to(P.dir)}: {N} frames, set {A.get('set', 'stage') if kind != 'panels' else 'panels'}, beats sung per figure {sung}, "
          f"dance beats {sum(1 for b in beats if c.in_dance(b['t']))}, gestures {len(c.gest)}, screen events {len(c.screen_ev)}, dance styles {c.styles_used} (seed {creative.seed(P)})"
          + ("\n   " + "; ".join(feats) if feats else ""))
    if a.render:
        frames = out_dir / a.section
        import shutil
        shutil.rmtree(out_dir / f"{a.section}_raw", ignore_errors=True)      # frames without captions (captions.py)
        if frames.exists():
            for p in frames.glob("*.png"):
                p.unlink()
        render(sif, frames, a.jobs)
        print(f"-> {frames.relative_to(P.dir)}/f.%04d.png ({len(list(frames.glob('*.png')))} images)")
        if A.get("caption"):                              # comic caption box typing the sung line
            import captions
            captions.apply(P, a.section)


if __name__ == "__main__":
    main()
