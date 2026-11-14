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
NEG_IMAGE = ("illustration, drawing, anime, cartoon, 3d render, painting, teenage, childlike, text, letters, logo, "
             "watermark, brand name, flag, second orange streak, two orange streaks, orange clothing, deformed hands, "
             "extra fingers, blurry, " + MIC_NEG)
NEG_LIPSYNC = ("pc game, console game, video game, cartoon, childish, ugly, static, frozen face, blurry mouth, text, "
               "letters, subtitles, watermark, logo, scene cut, sudden scene change, " + MIC_NEG)
NEG_MOVING = ("text, letters, words, subtitles, captions, title, watermark, logo, typography, scene cut, sudden scene "
              "change, cartoon, ugly, static, face on a screen")
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


def start_image_prompt(s, wardrobe, look_img, version="studio"):
    """Qwen-Image-Edit prompt for a start image of Claudia (two refs for close/medium, one for wide)."""
    wide = is_wide(s.get("framing"))
    place = s.get("set", "")
    if version == "live" and "stage" not in place.lower():
        place = f"{place}, {STAGE}" if place else STAGE
    parts = [QWEN_INTRO_1 if wide else QWEN_INTRO_2, (ID_FAR if wide else ID_FULL) + ".",
             f"Now she wears {wardrobe}.", f"{s.get('framing', 'Medium shot').capitalize()}, {s.get('action', 'she looks at the camera with a deadpan face')},",
             f"{place}." if place else "", READY if s.get("technique") == "lipsync" else "", look_img]
    return " ".join(p for p in parts if p)


def lipsync_prompt(s, wardrobe, look_vid, line):
    """LTX prompt of a singing shot, built like the Europe 2031 night run V1: one action sentence with mood and movement
    ("she sings softly, a slight sway of the head"), then the words in a sentence of their own, then the mouth sentence.
    "manner" = how she sings (an adverb phrase), "action" = what she does / how she moves; "deadpan" belongs to her face
    in the action, never right before the sung words (a mood bound to the words, "deadpan: ...", kept mouths shut)."""
    words = re.sub(r"\s+", " ", (line or "").replace('"', "").replace("„", "").replace("“", "")).strip()
    words = words.rstrip(",;:.")                                 # ?! stay; the sentence ends after the quote
    manner = (s.get("manner") or "into the camera").strip().rstrip(".")
    if manner.lower() in ("deadpan", "deadpanned"):              # the canon face, as a face, not as a way to sing
        manner = "into the camera with a dry, deadpan face"
    action = (s.get("action") or "a slight sway of the head").strip().rstrip(".")
    act = action[4:] if action.lower().startswith("she ") else action
    first = act if act.lower().startswith("sings") else f"sings {manner}, {act}"
    sing = f' She sings the words "{words}".' if words else ""
    place = s.get("set_short") or s.get("set", "")
    return (f"{s.get('framing', 'Medium shot').capitalize()} of {ID_VIDEO}, wearing {wardrobe}, she {first}.{sing} "
            f"{MOUTH}{(' ' + place[0].upper() + place[1:] + '.') if place else ''} "
            f"{s.get('camera', 'Static camera').capitalize()}, cinematic photographic 35mm film look, {look_vid}.")


def sing_mood(look, rng):
    """(manner, action) for a singing shot without its own: picked by the seed from the look's SING_MOODS."""
    opts = SING_MOODS.get(look) or SING_MOODS["studio"]
    return rng.choice(opts)


def moving_prompt(motion, camera, look_vid):
    return f"{motion.rstrip('.')}. Camera: {camera}. {look_vid.rstrip('.')}. {VIDEO_END}"


def broll_still_prompt(subject, look_img):
    return f"{subject.rstrip('.')}, {look_img.rstrip('.')}, {STILL_END}"


def s2v_prompt(s, look_vid):
    return (f"{s.get('framing', 'Close-up').capitalize()} of a woman with a glossy black bob, heavy bangs and one orange "
            f"streak, a small orange star hair clip and a thin beige headset microphone, she sings "
            f"{s.get('manner', 'with emotion')}, clear mouth movements, {s.get('set_short') or s.get('set', '')}, {look_vid}, "
            f"static camera, photographic 35mm film")


def check(prompt, kind):
    """Problems of one prompt -> list of strings (empty = fine). kind: image | lipsync | moving | broll_still | s2v"""
    p = prompt.lower()
    errs = []
    if re.search(r"\byoung\b", p):
        errs.append('contains "young" (she reads teenage) - use "in her late twenties"')
    if kind in ("lipsync", "moving") and re.search(r"\bno (text|letters|logos?|words)\b", p):
        errs.append('LTX positive prompt contains "no text" - move text/letters to the negative prompt')
    if kind in ("image", "lipsync") and ("beige" not in p or "right cheek" not in p):
        errs.append("microphone not pinned (thin beige headset on her right cheek)")
    if kind in ("lipsync", "moving", "s2v") and not any(w in p for w in ("light", "palette", "glow", "spotlight", "beams")):
        errs.append("no light/look sentence - LTX jumps scenes without one")
    rest = p
    for canon_text in (QWEN_INTRO_2, QWEN_INTRO_1, ID_FULL, ID_FAR, ID_VIDEO):
        rest = rest.replace(canon_text.lower(), "")
    if kind in ("image", "lipsync") and "streak" in rest:
        errs.append("the shot text mentions the streak again (risk of two streaks) - the canon text says it once")
    if re.search(r"\blogo\b", p) and "no logo" not in p:
        errs.append("asks for a logo - companies only as neutral text")
    return errs
