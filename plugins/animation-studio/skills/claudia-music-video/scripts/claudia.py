"""Claudia's canon as prompt text, the looks of the two versions, and the prompt builders + checks.

The canon itself is documented in characters/references/claudia.md (Claudia by anabology, open character). This module
only turns it into prompt pieces; change the canon THERE first, then here.
Prompt rules (measured lessons, Europe 2031 and Europe 2031 Live):
  - identity text pasted unchanged into every image and video prompt of her; never the word "young"
  - exactly ONE thin beige headset microphone whose boom runs along her RIGHT cheek (image left); negatives list every
    other microphone; one clay-orange streak on her right (image left), the star clip on her left (image right)
  - LTX positive prompts never say "no text" (garbled lettering) - text/letters/logos only in the negative prompt
  - every video prompt carries ONE light/look sentence matching its start image, or LTX jumps to another scene
  - companies only as neutral text, no logos; no real politicians; other people (e.g. Christian) anonymous, from behind
"""
import re

ID_FULL = ("a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, "
           "pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange "
           "streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a single thin beige "
           "skin-coloured headset microphone whose boom runs along her right cheek (left side of the image)")
ID_FAR = ("a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight "
          "bangs and one clay-orange streak, a single thin beige headset microphone on her right cheek")
ID_VIDEO = ("a woman in her late twenties with a glossy black bob with heavy bangs, one single clay-orange streak in her "
            "hair, a small orange star hair clip and a single thin beige headset microphone along her right cheek")
QWEN_INTRO_2 = ("Keep the exact face, hair, single orange streak, star clip and headset microphone of the woman in image 1 "
                "(image 2 shows the same woman in close-up, use it only for her face, streak and clip, not for the framing):")
QWEN_INTRO_1 = "Keep the exact face, hair, orange streak, star clip and headset microphone of the woman in image 1:"
READY = ("Her lips are slightly parted as if she is about to sing the next word, her face is clearly visible and lit, "
         "eyes open, and the thin beige headset microphone is clearly visible on her right cheek, no other microphone.")
MOUTH = ("Her lips clearly form every word, the mouth opens wide on the vowels and the lips close fully on m, b and p, "
         "natural small head movements and breathing.")
MIC_NEG = ("second microphone, two microphones, handheld microphone, microphone stand, black microphone, dark microphone, "
           "microphone on her left cheek, microphone boom on both sides")
# mic repair (ai-video mic_repair.py, qwen method): the Europe 2031 Live V5 recipe, edit ONLY the microphone
MIC_EDIT = ("Keep image 1 exactly: same person, face, expression, hair, single orange streak, star clip, outfit, pose, "
            "framing, light and colours. Change only the microphone: she wears exactly one thin beige, skin-coloured "
            "headset microphone; its thin boom runs from her right ear along her right cheek (on the left side of the "
            "image) to the corner of her mouth. Remove every other microphone, boom or cable, especially any on her left "
            "cheek (right side of the image) and any black microphone. If her right cheek is turned away from the camera, "
            "no microphone is visible. Photographic, film grain.")
MIC_EDIT_NEG = ("second microphone, two microphones, black microphone, dark microphone, microphone on her left cheek, "
                "microphone boom on both sides, handheld microphone, microphone stand, changed face, changed hair, text, logo")
# "mic": "added" (project.json, or one shot) - the headset in two steps: a start image WITHOUT any microphone (from
# reference images whose headset was edited away), then an edit that adds only the headset, limited to her FACE
# (ai-video face_edit.py: a square around the head is edited, the face area pasted back). Measured on El-Ge-Te-Em
# (2026-11-22): painted in one step the boom sat on the wrong cheek in 19 of 38 shots, came with a cable or twice.
# Added by an edit of the whole picture, with the side named ONLY as a side of the picture, it was on the right
# side in 9 of 10 (big) / about 17 of 24 (small) - "her right cheek (left side of the image)" was wrong in 20 of
# 20 - but about 10 of 24 pictures got a second microphone somewhere in the scene. Added on the face only: 24 of 24
# with one small headset on the right side and nothing else changed (6 shots, also a turned head). Still: the
# start images are looked at before the clips (capsule colour varies: beige, sometimes dark or orange).
# Only pictures of her alone with a face found; from behind and with other people the painted path stays.
MIC_BARE = [(" and headset microphone of the woman", " of the woman"),
            (", a single thin beige skin-coloured headset microphone whose boom runs along her right cheek "
             "(left side of the image)", ""),
            (", a single thin beige headset microphone on her right cheek", ""),
            (", and the thin beige headset microphone is clearly visible on her right cheek, no other microphone.", ".")]
MIC_NONE = "She wears no microphone and no headset, both cheeks and ears are bare."
MIC_REF_BARE = ("Keep image 1 exactly: same woman, face, expression, hair, single orange streak, star clip, outfit, pose, "
                "framing, light and colours. Remove her headset microphone completely: no boom, no capsule, no earpiece, "
                "no cable, her cheeks are bare skin. Photographic, film grain.")
MIC_ADD = ("Keep image 1 exactly: same woman, face, expression, hair, single orange streak, star clip, outfit, pose, "
           "framing, light and colours. Add only one thing: a tiny, discreet theatre headset microphone on the LEFT side "
           "of the picture: one hair-thin skin-coloured wire, as thin as a strand of hair, comes out of her hair at the "
           "left edge of her face and lies flat on the skin of the cheek on the left side of the picture, ending beside "
           "the corner of her mouth in a very small skin-coloured capsule no bigger than a grain of rice. It is barely "
           "noticeable. The cheek on the right side of the picture, next to the star clip, stays completely bare. "
           "Photographic, film grain.")
MIC_ADD_NEG = ("second microphone, two microphones, black microphone, dark microphone, microphone on her left cheek, "
               "microphone boom on both sides, handheld microphone, microphone stand, changed face, changed hair, text, "
               "logo, microphone on the right side of the picture, microphone below the star clip, thick boom, thick "
               "cable, cable hanging down, large foam ball, big windscreen, big microphone, call-centre headset, gaming "
               "headset, headband, earcup")
MIC_GAIN = 0.004        # canon.mic_lines share on her cheek, added picture minus bare picture: a microphone is there
NEG_IMAGE = ("illustration, drawing, anime, cartoon, 3d render, painting, teenage, childlike, text, letters, logo, "
             "watermark, brand name, flag, second orange streak, two orange streaks, orange clothing, deformed hands, "
             "extra fingers, blurry, " + MIC_NEG)
NEG_LIPSYNC = ("pc game, console game, video game, cartoon, childish, ugly, static, frozen face, blurry mouth, text, "
               "letters, subtitles, watermark, logo, scene cut, sudden scene change, " + MIC_NEG)
NEG_MOVING = ("text, letters, words, subtitles, captions, title, watermark, logo, typography, scene cut, sudden scene "
              "change, cartoon, ugly, static, face on a screen")
NEG_BARE = "microphone, headset, microphone boom, earpiece, cable, " + NEG_IMAGE
STILL_END = "cinematic 35mm film still, film grain, no text, no letters, no logos, no flags"
VIDEO_END = "Cinematic photographic 35mm film look, film grain, realistic motion. Continuous single shot."
STREAK = "#D97757"
WIDE = ("wide", "full", "long", "total", "establishing")

# looks: name -> (sentence for still images, short sentence for video prompts). A brief may add its own.
LOOKS = {
    "studio": {
        "grey_morning": ("Photographic 35mm film still, cold overcast blue-grey morning light, muted teal palette with "
                         "one small warm clay-orange accent, low-key, fine film grain, shallow depth of field.",
                         "cold blue-grey morning light, muted teal palette"),
        "night": ("Photographic 35mm film still, low-key cinematic lighting, muted desaturated deep blue night palette "
                  "with teal shadows and small warm clay-orange accents, fine film grain, shallow depth of field.",
                  "low-key, muted desaturated deep blue night palette with teal shadows and small clay-orange accents"),
        "studio": ("Photographic 35mm film still, deep blue and teal studio light with one warm clay-orange accent "
                   "light, fine film grain, shallow depth of field.", "deep blue and teal with a warm clay-orange accent"),
        "storm": ("Photographic 35mm film still, stormy teal and slate light, wind, dramatic clouds, fine film grain.",
                  "stormy teal and slate light"),
        "golden": ("Photographic 35mm film still, warm golden morning light, amber and teal, fine film grain, shallow "
                   "depth of field.", "warm golden morning light, amber and teal"),
        "quiet": ("Photographic 35mm film still, quiet low-key light, cool teal shadows, fine film grain.",
                  "quiet low-key light, cool teal shadows"),
    },
    "live": {
        "intro": ("Photographic 35mm concert film still, dark concert hall, deep blue haze, thin teal light beams, one "
                  "warm clay-orange rim light, low-key, fine film grain, shallow depth of field.",
                  "dark deep blue haze, thin teal beams, one warm clay-orange rim light"),
        "verse": ("Photographic 35mm concert film still, deep blue and teal stage light, haze, a warm clay-orange "
                  "spotlight from the side, low-key, fine film grain, shallow depth of field.",
                  "deep blue and teal stage light with a warm clay-orange side spot"),
        "chorus": ("Photographic 35mm concert film still, bright teal and white light beams cutting through haze, deep "
                   "blue shadows, small clay-orange accents, high energy, fine film grain, shallow depth of field.",
                   "bright teal and white beams through haze, deep blue shadows, small clay-orange accents"),
        "spoken": ("Photographic 35mm concert film still, one hard cool white spotlight, the hall around her in deep "
                   "blue darkness, fine film grain, shallow depth of field.", "one hard cool white spotlight, deep blue darkness"),
        "bridge": ("Photographic 35mm concert film still, almost dark, one soft pale spotlight from above, deep blue "
                   "darkness, tiny out-of-focus lights in the crowd, quiet and intimate, fine film grain.",
                   "almost dark, one soft pale spotlight, deep blue darkness"),
        "finale": ("Photographic 35mm concert film still, warm golden amber stage light mixed with teal beams, clay-orange "
                   "and golden confetti in the air, euphoric, fine film grain, shallow depth of field.",
                   "warm golden amber light mixed with teal beams, confetti in the air"),
    },
}
WARDROBE = {   # defaults per version; the brief should invent one that fits the song
    "studio": ["a charcoal-grey oversized tailored blazer over a plain white high-neck top",
               "a long camel wool coat over a black turtleneck", "a slate-blue boiler suit with rolled-up sleeves"],
    "live": ["a charcoal-grey oversized tailored blazer with the sleeves pushed up over a plain white high-neck top",
             "a black sleeveless jumpsuit with a wide belt", "a cropped white leather jacket over a black slip dress"],
}
# how she sings + a small movement, per look (pairs for "manner" and "action"). The Europe 2031 night run (V1) put
# mood and motion into the action and the words into a sentence of their own - that version was chosen for 11 of 17
# singing shots of V3 for its natural movement; "sings deadpan: <words>" (V2 / the 0.4 plugin) could shut the mouth.
SING_MOODS = {
    "grey_morning": [("tiredly into the camera", "a slight sway of the head"),
                     ("quietly and dryly", "she shifts her weight, small head movements")],
    "night": [("softly close to the camera", "the city lights flicker behind her, small head movements"),
              ("calmly into the lens", "a slow turn of the head toward the camera")],
    "studio": [("with energy", "a small nod on the beat, her bangs move"),
               ("directly into the lens", "she leans in slightly, small head movements")],
    "storm": [("with energy", "the wind blows her hair and her clothes"),
              ("against the wind", "she turns her face into the wind, her bangs fly")],
    "golden": [("with growing confidence", "the wind in her bangs, warm light moves over her face"),
               ("calmly and certainly", "a slight sway of the head, she breathes in the morning air")],
    "quiet": [("softly", "she looks slightly to the side, then back into the lens"),
              ("quietly", "small head movements, dust drifts in the light")],
    "intro": [("calmly into the lens", "she steps into the light, small head movements")],
    "verse": [("with conviction", "a small nod on the beat, the light sweeps over her")],
    "chorus": [("with energy and full voice", "she moves with the beat, her hair swings")],
    "spoken": [("dryly, almost speaking", "very small head movements")],
    "bridge": [("softly", "she closes her eyes for a moment, then looks into the lens")],
    "finale": [("with passion and full voice", "she raises one hand, confetti drifts past her")],
}
STAGE = ("on a large dark concert stage, the band behind her only as dark silhouettes, haze in the air, beams of stage light")
FRAMINGS = {"lipsync": ["close-up", "medium close-up", "medium shot", "low-angle medium shot", "three-quarter close-up"],
            "claudia_moving": ["wide shot", "medium shot from the side", "full shot from behind", "medium shot"]}
CAMERAS = {"lipsync": ["static camera", "very slow push-in", "slow lateral drift", "slow push-in"],
           "broll": ["slow push-in", "slow drift to the right", "slow drift to the left", "slow upward tilt",
                     "static camera", "slow orbit to the right"],
           "claudia_moving": ["slow push-in", "slow orbit", "static camera", "slow pull-back"]}


def look(brief, name, version="studio"):
    """(image sentence, video sentence) of a look: the brief's own looks first, then the version's defaults."""
    own = ((brief or {}).get("looks") or {}).get(name)
    if own:
        return tuple(own)
    base = LOOKS.get(version, LOOKS["studio"])
    return base.get(name) or next(iter(base.values()))


def is_wide(framing):
    return any(w in (framing or "").lower() for w in WIDE)


def start_image_prompt(s, wardrobe, look_img, version="studio", bare=False):
    """Qwen-Image-Edit prompt for a start image of Claudia (two refs for close/medium, one for wide); a shot of other
    characters (project.json "characters", shot "who") gets the generic prompt of its cast.
    bare=True: the same picture without any microphone ("mic": "added" - the headset is added by a second edit)."""
    if bare:
        p = start_image_prompt(s, wardrobe, look_img, version)
        for a, b in MIC_BARE:
            p = p.replace(a, b)
        if "microphone" in p or "headset" in p:
            raise SystemExit(f'shot {s.get("name", "?")}: "mic": "added" - the shot text names a microphone or headset '
                             "itself; take it out (the headset is added after the picture)")
        return p.replace(look_img, f"{MIC_NONE} {look_img}") if look_img and look_img in p else f"{p} {MIC_NONE}"
    cast = cast_of(s)
    if cast is not None:
        return _start_generic(cast, s, wardrobe, look_img)
    wardrobe = s.get("wardrobe") or wardrobe          # a shot may change her clothes (bridge, night scene)
    wide = is_wide(s.get("framing"))
    place = s.get("set", "")
    if version == "live" and "stage" not in place.lower():
        place = f"{place}, {STAGE}" if place else STAGE
    parts = [QWEN_INTRO_1 if wide else QWEN_INTRO_2, (ID_FAR if wide else ID_FULL) + ".",
             f"Now she wears {wardrobe}.", f"{s.get('framing', 'Medium shot').capitalize()}, {s.get('action', 'she looks at the camera with a deadpan face')},",
             f"{place}." if place else "", READY if s.get("technique") == "lipsync" else "", look_img]
    return " ".join(p for p in parts if p)


def lipsync_prompt(s, wardrobe, look_vid, line, style=None):
    """LTX prompt of a singing shot, built like the Europe 2031 night run V1: one action sentence with mood and movement
    ("she sings softly, a slight sway of the head"), then the words in a sentence of their own, then the mouth sentence.
    "manner" = how she sings (an adverb phrase), "action" = what she does / how she moves; "deadpan" belongs to her face
    in the action, never right before the sung words (a mood bound to the words, "deadpan: ...", kept mouths shut)."""
    words = re.sub(r"\s+", " ", (line or "").replace('"', "").replace("„", "").replace("“", "")).strip()
    words = words.rstrip(",;:.")                                 # ?! stay; the sentence ends after the quote
    cast = cast_of(s)
    if cast is not None:
        return _lipsync_generic(cast, s, wardrobe, look_vid, words)
    wardrobe = s.get("wardrobe") or wardrobe          # a shot may change her clothes (bridge, night scene)
    if s.get("timeline") and (style or "timeline") == "timeline":   # style "plain" = the A prompt of a timeline shot
        return timeline_prompt(s, wardrobe, look_vid, words)
    manner = (s.get("manner") or "into the camera").strip().rstrip(".")
    if manner.lower() in ("deadpan", "deadpanned"):              # the canon face, as a face, not as a way to sing
        manner = "into the camera with a dry, deadpan face"
    action = (s.get("action") or timeline_action(s.get("timeline")) or "a slight sway of the head").strip().rstrip(".")
    act = action[4:] if action.lower().startswith("she ") else action
    first = act if act.lower().startswith("sings") else f"sings {manner}, {act}"
    sing = f' She sings the words "{words}".' if words else ""
    place = s.get("set_short") or s.get("set", "")
    return (f"{s.get('framing', 'Medium shot').capitalize()} of {ID_VIDEO}, wearing {wardrobe}, she {first}.{sing} "
            f"{MOUTH}{(' ' + place[0].upper() + place[1:] + '.') if place else ''} "
            f"{s.get('camera', 'Static camera').capitalize()}, cinematic photographic 35mm film look, {look_vid}.")


HOLD_WORDS = re.compile(r"\b(small head movements?|upright|static camera|faces the camera|stands still|"
                        r"motionless)\b", re.I)


def timeline_action(timeline):
    """The timeline as one plain action ("she counts on her fingers, then she shrugs") for the A prompt of a mixed shot."""
    return ", then ".join(HOLD_WORDS.sub("", str(a)).strip(" ,.") for _, _, a in (timeline or []))


def timeline_text(timeline):
    """[[0, 1.2, "she punches her fist up"], [1.2, 2.5, "she walks ... on the downbeat"]] -> "0-1.2s: ... 1.2-2.5s: ..." """
    return " ".join(f"{float(t0):g}-{float(t1):g}s: {HOLD_WORDS.sub('', str(a)).strip(' ,.')}." for t0, t1, a in timeline)


def timeline_prompt(s, wardrobe, look_vid, words):
    """Timeline style (B) for shots with several actions on the beat (A/B test 2026-11-15: B won gesture lists, chorus
    and "Hey" shots, A won close-ups, spoken and quiet shots), after the Claudia wiki rules / live film V2 / motion test
    B: no posture or hold words ("small head movements", "static camera" froze her), one concrete action per time span,
    one camera move bound to the beat, short; "static, frozen" stay in the negative prompt (NEG_LIPSYNC)."""
    sing = f' She sings "{words}", her lips forming each word exactly when it sounds.' if words else ""
    place = s.get("set_short") or s.get("set", "")
    cam = HOLD_WORDS.sub("", s.get("camera") or "").strip(" ,.") or "slow push-in on the downbeat"
    return (f"{s.get('framing', 'Medium shot').capitalize()} of {ID_VIDEO}, wearing {wardrobe}. "
            f"{timeline_text(s['timeline'])}{sing}"
            f"{(' ' + place[0].upper() + place[1:] + '.') if place else ''} Camera: {cam}. "
            f"Cinematic photographic 35mm film look, {look_vid}.")


SING_MOODS_ANY = [("into the camera", "a slight sway of the head"), ("softly", "she tilts her head, small movements"),
                  ("with conviction", "a small nod on the beat"), ("calmly into the lens", "she breathes in, her bangs move"),
                  ("with energy", "she leans forward slightly, her hair swings"),
                  ("quietly", "she looks down, then up into the lens")]


def sing_mood(look, rng, used=()):
    """(manner, action) for a singing shot without its own: the look's SING_MOODS first, then SING_MOODS_ANY, never a
    movement already used in this film while there are others (user test: three shots got the same movement).
    Another lead (project.json "lead") gets the neutral list in his / her own pronouns."""
    if LEAD in CAST:
        c = CAST[LEAD]
        opts = [(m, a.format(subj=c["subj"], poss=c["poss"])) for m, a in SING_MOODS_NEUTRAL]
        return rng.choice([o for o in opts if o[1] not in used] or opts)
    opts = list(SING_MOODS.get(look, [])) + SING_MOODS_ANY
    fresh = [o for o in opts if o[1] not in used] or opts
    own = [o for o in fresh if o in SING_MOODS.get(look, [])]
    return rng.choice(own or fresh)


def moving_prompt(motion, camera, look_vid):
    return f"{motion.rstrip('.')}. Camera: {camera}. {look_vid.rstrip('.')}. {VIDEO_END}"


def broll_still_prompt(subject, look_img):
    return f"{subject.rstrip('.')}, {look_img.rstrip('.')}, {STILL_END}"


def multishot_who(s, wardrobe):
    """The singer's identifiers as they are repeated after a cut (word for word the text of shot 1)."""
    cast = cast_of(s)
    if cast is not None:
        a = cast[0]
        return f"{a['video']}{_opts(a, s)}, wearing {_wardrobe(a, s, wardrobe)}"
    return f"{ID_VIDEO}, wearing {wardrobe}"


def multishot_prompt(s, wardrobe, look_vid, line):
    """LTX-2.5 prompt of a sung shot with a cut inside (engine "ltx25", ai-video ltx25.py): the plain lip-sync prompt
    as shot 1, then one sentence per entry of the shot's "cuts": [{"framing": "frontal medium shot from the waist up",
    "action": "she shouts the last words and raises her fist", "place": "in the same room"}] with the identifiers
    repeated, and the look once more for the whole clip."""
    import ltx25
    # static camera in every shot: LTX-2.5 pushes in by itself, and a camera move fights the cut
    opening = lipsync_prompt(dict({k: v for k, v in s.items() if k != "timeline"}, camera="static camera"), wardrobe,
                             look_vid, line, style="plain")
    who = multishot_who(s, wardrobe)
    place = s.get("set_short") or s.get("set", "")
    cuts = [{"framing": c.get("framing", ""), "who": who, "transition": c.get("transition", ltx25.TRANSITION),
             "action": c.get("action") or "the singing goes on, the lips clearly form every word",
             "place": c.get("place") or (f"in the same place, {place}" if place else "in the same place")}
            for c in (s.get("cuts") or [])]
    return ltx25.multishot_prompt(opening, cuts, f"The same light in every shot: {look_vid}. Static camera in each shot.")


def neg_multishot(s):
    """The lip-sync negatives without the ban on scene cuts (the cut is wanted here)."""
    return re.sub(r"\s{2,}", " ", re.sub(r"(sudden scene change|scene cut),?\s*", "", neg_lipsync(s))).strip().rstrip(",")


def s2v_prompt(s, look_vid):
    cast = cast_of(s)
    if cast is not None:
        c = cast[0]
        return (f"{s.get('framing', 'Close-up').capitalize()} of {c['video']}{_opts(c, s)}, {c['subj']} sings "
                f"{s.get('manner', 'with emotion')}, clear mouth movements, {s.get('set_short') or s.get('set', '')}, "
                f"{look_vid}, static camera, photographic 35mm film")
    return (f"{s.get('framing', 'Close-up').capitalize()} of a woman with a glossy black bob, heavy bangs and one orange "
            f"streak, a small orange star hair clip and a thin beige headset microphone, she sings "
            f"{s.get('manner', 'with emotion')}, clear mouth movements, {s.get('set_short') or s.get('set', '')}, {look_vid}, "
            f"static camera, photographic 35mm film")


def check(prompt, kind, s=None):
    """Problems of one prompt -> list of strings (empty = fine). kind: image | lipsync | moving | broll_still | s2v
    s = the shot: the canon rules (microphone, streak, "young") are Claudia's and only apply to her shots."""
    p = prompt.lower()
    errs = []
    if s is not None and cast_of(s) is not None:
        if kind in ("lipsync", "moving") and re.search(r"\bno (text|letters|logos?|words)\b", p):
            errs.append('LTX positive prompt contains "no text" - move text/letters to the negative prompt')
        if kind in ("lipsync", "moving", "s2v") and not any(w in p for w in LIGHT_WORDS):
            errs.append("no light/look sentence - LTX jumps scenes without one")
        if re.search(r"\blogo\b", p) and "no logo" not in p:
            errs.append("asks for a logo - companies only as neutral text")
        return errs
    if re.search(r"\byoung\b", p):
        errs.append('contains "young" (she reads teenage) - use "in her late twenties"')
    if kind in ("lipsync", "moving") and re.search(r"\bno (text|letters|logos?|words)\b", p):
        errs.append('LTX positive prompt contains "no text" - move text/letters to the negative prompt')
    if kind in ("image", "lipsync") and ("beige" not in p or "right cheek" not in p):
        errs.append("microphone not pinned (thin beige headset on her right cheek)")
    if kind == "image_bare" and MIC_NONE.lower() not in p:
        errs.append('bare start image ("mic": "added") without the "no microphone" sentence')
    if kind in ("lipsync", "moving", "s2v") and not any(w in p for w in LIGHT_WORDS):
        errs.append("no light/look sentence - LTX jumps scenes without one")
    rest = p
    for canon_text in (QWEN_INTRO_2, QWEN_INTRO_1, ID_FULL, ID_FAR, ID_VIDEO):
        rest = rest.replace(canon_text.lower(), "")
    for a, b in MIC_BARE:                                # the same canon texts without the microphone
        rest = rest.replace(QWEN_INTRO_2.replace(a, b).lower(), "").replace(QWEN_INTRO_1.replace(a, b).lower(), "")
        rest = rest.replace(ID_FULL.replace(a, b).lower(), "").replace(ID_FAR.replace(a, b).lower(), "")
    if kind in ("image", "image_bare", "lipsync") and "streak" in rest:
        errs.append("the shot text mentions the streak again (risk of two streaks) - the canon text says it once")
    if re.search(r"\blogo\b", p) and "no logo" not in p:
        errs.append("asks for a logo - companies only as neutral text")
    return errs


# ------------------------------------------------------------------ other characters ---------------------------------
# project.json "characters": {"oliver": {"pronoun": "he", "full": "a 55-year-old ... man ...", "far": "...", "video":
#   "...", "refs": ["refs/front.jpg", "refs/threequarter.jpg"], "keep": "face, head shape, skin and hair",
#   "options": {"headband": "a black running headband around his forehead"}, "wardrobe": "a black softshell jacket",
#   "negative": "beard, bald head, glasses"}}, "lead": "oliver".  A shot says "who": "oliver" | "claudia" |
#   ["oliver", "claudia"] (default: the lead) and switches an option on with its key ("headband": true).
# Claudia stays the built-in default with her microphone canon; {"claudia": {"base": "claudia", "mic": false}} (or
# naming her in another lead's film) is Claudia as a guest without the stage microphone.
# Measured (Das Warum, 2026-11-20): Claudia's canon check and mic repair run on another character painted her headset
# and streak onto him - every canon rule below is bound to the shot's cast.
LIGHT_WORDS = ("light", "palette", "glow", "spotlight", "beams", "sun", "dusk", "dawn")
PRONOUNS = {"she": ("she", "her", "her", "woman"), "he": ("he", "his", "him", "man")}
CLAUDIA_PLAIN = {
    "pronoun": "she", "keep": "face, hair, single orange streak and star clip",
    "full": ("a 28-year-old woman with a grown-up angular face, defined cheekbones, pale skin and light freckles, a glossy "
             "black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small "
             "flat clay-orange eight-pointed star hair clip, no microphone and no headset"),
    "far": ("a woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one "
            "clay-orange streak"),
    "video": ("a woman in her late twenties with a glossy black bob with heavy bangs, one single clay-orange streak in "
              "her hair and a small orange star hair clip"),
    "ref_fix": "Remove her headset microphone completely, her cheeks are bare", "wardrobe": "a soft grey knitted jumper",
    "negative": "second orange streak, two orange streaks"}
SING_MOODS_NEUTRAL = [("into the camera", "a slight sway of the head"), ("softly", "{subj} tilts {poss} head a little"),
                      ("with conviction", "a small nod on the beat"),
                      ("calmly into the lens", "{subj} breathes in and looks into the lens"),
                      ("with energy", "{subj} leans forward slightly"),
                      ("quietly", "{subj} looks down, then up into the lens"),
                      ("warmly, telling a story", "{subj} opens one hand toward the camera"),
                      ("thoughtfully", "{subj} looks to the side for a moment, then back into the lens")]
GEN_NEG_IMAGE = ("illustration, drawing, anime, cartoon, 3d render, painting, text, letters, logo, watermark, brand name, "
                 "flag, deformed hands, extra fingers, blurry")
GEN_NEG_LIPSYNC = ("pc game, console game, video game, cartoon, childish, ugly, static, frozen face, blurry mouth, text, "
                   "letters, subtitles, watermark, logo, scene cut, sudden scene change")
NO_PEOPLE_NEG = ", people, a person walking into the frame, passers-by"
PEOPLE = re.compile(r"\b(man|men|woman|women|people|person|persons|colleagues?|crowd|farmers?|workers?|child|children|"
                    r"girl|boy|couple|audience|hands?|someone)\b", re.I)
CAST = {}
LEAD = "claudia"
MIC_MODE = "painted"        # project.json "mic": "added" = the headset is added to a start image made without one


def _norm(name, spec):
    c = dict(spec)
    if c.pop("base", name) == "claudia":
        c = dict(CLAUDIA_PLAIN, **c)
    if not c.get("full"):
        raise SystemExit(f'project.json characters.{name}: "full" (the identity text pasted into every prompt) is missing')
    subj, poss, obj, noun = PRONOUNS.get(str(c.get("pronoun", "she")).lower(), PRONOUNS["she"])
    c.update(name=name, subj=subj, poss=poss, obj=obj, noun=c.get("noun") or noun)
    c.setdefault("far", c["full"])
    c.setdefault("video", c["far"])
    c.setdefault("keep", "face and hair")
    return c


def setup(P):
    """Register the project's characters and lead (call once after loading the project; no "characters" = Claudia)."""
    global LEAD, MIC_MODE
    mode = str(P.get("mic") or "painted").lower()
    if mode not in ("painted", "added"):
        raise SystemExit(f'project.json "mic": "{mode}" - use "added" (headset added to a start image without one) or '
                         'leave it out (painted with the picture)')
    MIC_MODE = mode
    CAST.clear()
    for name, spec in (P.get("characters") or {}).items():
        if name.lower() == "claudia" and spec.get("mic", True) and "full" not in spec:
            continue                                  # {"claudia": {"refs": [...]}}: the built-in Claudia with her mic
        CAST[name.lower()] = _norm(name.lower(), spec)
    LEAD = str(P.get("lead") or "claudia").lower()
    if LEAD != "claudia" and LEAD not in CAST:
        raise SystemExit(f'project.json "lead": "{LEAD}" is not in "characters" ({", ".join(CAST) or "none"})')


def cast_of(s):
    """The shot's characters as specs, or None = Claudia alone with her microphone (the built-in canon path)."""
    who = (s or {}).get("who") or LEAD
    names = [str(w).strip().lower() for w in (who if isinstance(who, list) else str(who).replace(",", "+").split("+"))]
    if names == ["claudia"] and "claudia" not in CAST and LEAD == "claudia":
        return None
    out = []
    for n in names:
        if n in CAST:
            out.append(CAST[n])
        elif n == "claudia":                          # a guest in another lead's film: without the stage microphone
            out.append(_norm("claudia", {"base": "claudia"}))
        else:
            raise SystemExit(f'shot {(s or {}).get("name", "?")}: "who": "{n}" is not in project.json "characters" '
                             f'({", ".join(CAST) or "none"})')
    if len(out) > 2:
        raise SystemExit(f'shot {(s or {}).get("name", "?")}: at most two characters in one start image (two reference images)')
    return out


def mic_added(s):
    """True = this shot's headset is added by a second edit: project.json "mic": "added" (a shot may say "mic":
    "painted" / "added" itself), Claudia alone with her canon, not seen from behind, no given start image."""
    mode = str((s or {}).get("mic") or MIC_MODE).lower()
    return (mode == "added" and cast_of(s) is None and not (s or {}).get("start_image")
            and "behind" not in ((s or {}).get("framing") or "").lower())


def has_canon(s):
    """True = Claudia's measured canon (streak side, one headset boom) and the mic repair apply to this shot."""
    return cast_of(s) is None


def shot_refs(s, default_refs, path=lambda r: r):
    """Reference images of the shot's cast: one character -> one (wide) or two refs, two characters -> one each.
    default_refs: a callable returning Claudia's project / config refs (only asked when she is in the shot)."""
    cast = cast_of(s)
    if cast is None:
        refs = default_refs()
        return refs[:1] if is_wide(s.get("framing")) else refs[:2]
    per = []
    for c in cast:
        r = [str(path(x)) for x in c.get("refs") or []] or (list(default_refs()) if c["name"] == "claudia" else [])
        if not r:
            raise SystemExit(f'project.json characters.{c["name"]}: "refs" missing (one or two reference images)')
        per.append(r)
    if len(cast) == 2:
        return [per[0][0], per[1][0]]
    return per[0][:1] if is_wide(s.get("framing")) else per[0][:2]


def _opts(c, s):
    return "".join(f", {text}" for key, text in (c.get("options") or {}).items() if s.get(key))


def _wardrobe(c, s, wardrobe, key="wardrobe"):
    return s.get(key) or c.get("wardrobe") or (wardrobe if key == "wardrobe" else "plain everyday clothes")


def _start_generic(cast, s, wardrobe, look_img):
    wide = is_wide(s.get("framing"))
    place = s.get("set", "")
    fr = s.get("framing", "Medium shot").capitalize()
    a = cast[0]
    ready = (f"{a['poss'].capitalize()} lips are slightly parted as if {a['subj']} is about to sing the next word, "
             f"{a['poss']} face is clearly visible and lit, turned to the camera, eyes open."
             if s.get("technique") == "lipsync" else "")
    if len(cast) == 1:
        two = not wide and len(a.get("refs") or [0, 0]) > 1
        intro = (f"Keep the exact {a['keep']} of the {a['noun']} in image 1"
                 + (f" (image 2 shows the same {a['noun']} from another angle, use it only for {a['poss']} face and hair, "
                    "not for the framing, the clothes or the background)" if two
                    else f", but not {a['poss']} clothes or the background")
                 + (f". {a['ref_fix']}" if a.get("ref_fix") else "") + ":")
        parts = [intro, (a["far"] if wide else a["full"]) + _opts(a, s) + ".",
                 f"Now {a['subj']} wears {_wardrobe(a, s, wardrobe)}.",
                 f"{fr}, {s.get('action') or a['subj'] + ' looks at the camera'},", f"{place}." if place else "", ready, look_img]
    else:
        b = cast[1]
        la, lb = (a["noun"], b["noun"]) if a["noun"] != b["noun"] else (f"first {a['noun']}", f"second {b['noun']}")
        fix = "".join(f" {c['ref_fix']}." for c in cast if c.get("ref_fix"))
        parts = [f"Two people in one picture: the {la} keeps the exact {a['keep']} of the {a['noun']} in image 1; the {lb} "
                 f"keeps the exact {b['keep']} of the {b['noun']} in image 2.{fix}",
                 f"The {la} is {a['far'] if wide else a['full']}{_opts(a, s)}, wearing {_wardrobe(a, s, wardrobe)}.",
                 f"The {lb} is {b['far'] if wide else b['full']}{_opts(b, s)}, wearing {_wardrobe(b, s, wardrobe, 'wardrobe2')}.",
                 f"{fr}, {s.get('action') or 'they stand side by side'},", f"{place}." if place else "", ready, look_img]
    return " ".join(p for p in parts if p)


def _lipsync_generic(cast, s, wardrobe, look_vid, words):
    a = cast[0]
    manner = (s.get("manner") or "into the camera").strip().rstrip(".")
    action = (s.get("action") or timeline_action(s.get("timeline")) or "a slight sway of the head").strip().rstrip(".")
    act = action[len(a["subj"]) + 1:] if action.lower().startswith(a["subj"] + " ") else action
    first = act if act.lower().startswith("sings") else f"sings {manner}, {act}"
    sing = f' {a["subj"].capitalize()} sings the words "{words}".' if words else ""
    mouth = (f"{a['poss'].capitalize()} lips clearly form every word, the mouth opens wide on the vowels and the lips close "
             "fully on m, b and p, natural small head movements and breathing.")
    other = "".join(f" The {b['noun']} next to {a['obj']} stays silent with {b['poss']} mouth closed and listens."
                    for b in cast[1:])
    place = s.get("set_short") or s.get("set", "")
    return (f"{s.get('framing', 'Medium shot').capitalize()} of {a['video']}{_opts(a, s)}, wearing "
            f"{_wardrobe(a, s, wardrobe)}, {a['subj']} {first}.{sing} {mouth}{other}"
            f"{(' ' + place[0].upper() + place[1:] + '.') if place else ''} "
            f"{s.get('camera', 'Static camera').capitalize()}, cinematic photographic 35mm film look, {look_vid}.")


def _neg(cast, base):
    extra = [c["negative"] for c in cast if c.get("negative")]
    return ", ".join([base, "microphone, headset"] + extra)


def neg_image(s):
    cast = cast_of(s)
    return NEG_IMAGE if cast is None else _neg(cast, GEN_NEG_IMAGE)


def neg_lipsync(s):
    cast = cast_of(s)
    return NEG_LIPSYNC if cast is None else _neg(cast, GEN_NEG_LIPSYNC + (", second person singing" if len(cast) > 1 else ""))


def neg_moving(s):
    """B-roll without people in its subject: keep LTX from walking a stranger into the picture (Das Warum s02)."""
    subject = (s.get("subject") or "").lower()
    if s.get("technique") == "broll" and (not PEOPLE.search(subject) or "no people" in subject):
        return NEG_MOVING + NO_PEOPLE_NEG
    return NEG_MOVING


def default_motion(s):
    cast = cast_of(s)
    return "She moves slowly, her hair moves slightly" if cast is None else f"{cast[0]['subj'].capitalize()} moves slowly"


HANDLING = re.compile(r"\b(hands? (him|her|it|over)|passes? (him|her|it|the)|gives? (him|her)|reach(es)? for|picks? up|"
                      r"puts? down|turns? (a|the) pages?|leafs? through|flips? through|(closes?|opens?|shuts?) the "
                      r"(laptop|book|lid))\b")


def hints(shots):
    """Direction advice that is not an error (printed by jobs.py). Lessons of Das Warum (2026-11-20):
    a hand named in the hair text became a hand in the hair in a third of the shots; "raises his eyebrows" gave a
    frozen stare; laptops grew brand logos; a "man" in B-roll is a stranger, never the film's character.
    Lessons of "Ein Haus, eine Nacht" (2026-11-21): a wide framing made another lead a stranger in every start image;
    handing over / page turning / closing a lid failed in the clips; "crumpled" shirts got holes."""
    out = []
    acted = [s for s in shots if s.get("technique") in ("lipsync", "claudia_moving")]
    nouns = sorted({c["noun"] for c in CAST.values()})
    for s in shots:
        n, text = s.get("name", "?"), " ".join(str(s.get(k) or "") for k in ("action", "set", "subject", "motion")).lower()
        if re.search(r"\b(by hand|hand (in|through) (his|her) hair|pushes? (his|her) hair|pushed back by)\b", text):
            out.append(f"{n}: a hand at the hair in the text - Qwen draws the hand there in every variant; describe the hair itself")
        if "eyebrow" in text:
            out.append(f"{n}: raised eyebrows read as a frozen stare in the start image - describe a relaxed face instead")
        if re.search(r"\b(laptops?|notebook computers?|monitors?|smartphones?)\b", text) and "unbranded" not in text:
            out.append(f"{n}: laptops / phones grow brand logos - write \"plain unbranded\" or use paper, folders, tools")
        if s.get("technique") == "broll" and nouns and "no people" not in text and re.search(
                r"\b(" + "|".join(nouns + sorted(CAST)) + r")\b", s.get("subject") or "", re.I):
            out.append(f"{n}: B-roll shows a {'/'.join(nouns)} - without a reference image that is a stranger; use "
                       "technique \"claudia_moving\" with \"who\" if it is the film's character")
        if s.get("technique") in ("lipsync", "claudia_moving") and not has_canon(s) and re.search(
                r"\b(medium wide|wide|long|full)[ -]shot\b", (s.get("framing") or "").lower()):
            out.append(f"{n}: \"{s['framing']}\" of a character without a measured canon - the face gets too small for the "
                       "reference and comes out as a stranger; use \"medium shot from the waist up\" or closer")
        if s.get("technique") != "typo" and HANDLING.search((s.get("motion") or "").lower()):
            out.append(f"{n}: the motion asks for handling a thing - the video model doubles or drops it; show the state "
                       "in the start image and let the clip only look")
        if re.search(r"\b(creased|crumpled|wrinkled)\b", text + " " + " ".join(str(s.get(k) or "") for k in ("wardrobe", "wardrobe2")).lower()):
            out.append(f"{n}: \"creased\" / \"crumpled\" clothes get holes - describe the wear another way (collar open, sleeves pushed up)")
    count = {}
    for s in acted:
        if s.get("action"):
            count.setdefault(s["action"].strip().lower(), []).append(s.get("name", "?"))
    for act, names in count.items():
        if len(names) > max(3, len(acted) // 8):
            out.append(f"{len(names)} shots share the action \"{act[:60]}\" ({', '.join(names[:6])} ...) - vary the start poses")
    hands = [s.get("name", "?") for s in acted if re.search(r"\bhands?\b", (s.get("action") or "").lower())]
    if len(hands) > max(4, len(acted) // 3):
        out.append(f"{len(hands)} of {len(acted)} acted shots name a hand in the action - the same gesture will repeat")
    return out
