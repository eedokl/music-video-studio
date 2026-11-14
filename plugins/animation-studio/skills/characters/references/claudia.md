# Claudia - canon (photographic AI singer)

Claudia is an open character: **"Claudia by anabology"** (claudia.gallery). Anyone may make images, videos and songs
with her, commercial or not; the credit is appreciated - put it in the film's AI label / end title. She is an adult
woman in her late twenties; nothing that reads under-age, nothing explicit. Her clothes change with every world; her
head never does.

## The constants (check every image)

| what | canon |
|---|---|
| hair | glossy **black blunt bob** to the jaw, **heavy straight bangs** to the brows |
| streak | **ONE clay-orange streak (#D97757)** through the bangs, on **her right** side = the **image left** in a front view. Never two, no other orange on her |
| clip | small flat **clay-orange eight-pointed star** hair clip on **her left**, above the ear (= image right) |
| microphone | exactly **ONE thin beige (skin-coloured) headset microphone**, its boom along **her right cheek** (image left, the streak side). No second mic, no handheld mic, no stand, no black mic |
| face | pale skin, **light freckles** across the nose, calm eyes, small defined mouth, angular adult face, defined cheekbones, strong jaw |
| age | **late twenties** ("a 28-year-old ..."). Never write **"young"** - image models drift her toward a teenage face; reject any image where she reads under ~25 |
| manner | **deadpan**, curious; when she sings her mouth opens wide |
| medium | **photographic**: 35mm film stills, grain, cinematic light. Never illustrated |

Seen from **behind**, her right side is the image **right**: the streak (and the mic) must be there.
In a profile toward the image left we see her left cheek: no microphone visible there.

## Identity text (paste unchanged; the claudia-music-video scripts do this)

Close and medium shots:
> a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale
> skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak
> through the bangs, a small flat clay-orange eight-pointed star hair clip, a single thin beige skin-coloured headset
> microphone whose boom runs along her right cheek (left side of the image)

Wide and full-length shots (the full text makes image models crop in to her face):
> a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight
> bangs and one clay-orange streak, a single thin beige headset microphone on her right cheek

Video prompts (LTX/S2V; the start image carries the details):
> a woman in her late twenties with a glossy black bob with heavy bangs, one single clay-orange streak in her hair, a
> small orange star hair clip and a single thin beige headset microphone along her right cheek

Negative prompt (images): illustration, drawing, anime, cartoon, 3d render, painting, teenage, childlike, text, letters,
logo, watermark, brand name, flag, second orange streak, two orange streaks, orange clothing, deformed hands, extra
fingers, blurry, second microphone, two microphones, handheld microphone, microphone stand, black microphone, dark
microphone, microphone on her left cheek, microphone boom on both sides.

## Method that holds her (local models)

- Start images with **Qwen-Image-Edit** from **two references**: image 1 = her face with mic and clip, image 2 = a
  close-up showing the ONE streak and the clip ("use it only for her face, streak and clip, not for the framing").
  One reference for wide shots. The references are the user's images (claudia.gallery sheets or earlier film stills),
  stored outside the plugin: project `character_refs` or config `claudia_refs`.
- Mention the streak **once** (in the identity text). Repeating it produces two streaks.
- Name the microphone's **colour and side** in every prompt - "thin headset microphone" alone gave changing mics
  (count, colour, side). LTX copies the mic from the start image, so check start images first.
- Pick start images by measurement (ai-video `canon.py`: clay pixels in a vertical band on the image left of the face)
  and by eye on the contact sheet (mic, age, hands).
- Wardrobe per film: describe garments, never designers or celebrities; name everything that comes into view.
- Other people stay anonymous: e.g. "Christian" only from behind or as a silhouette; no real politicians; companies only
  as neutral text, never logos.
- Label the film as AI-generated, credit "Claudia by anabology".

## Looks used so far (examples, not templates)

- Europe 2031 (studio): charcoal-grey oversized tailored blazer over a plain white high-neck top; Brussels offices,
  rooftops in storm, server halls; cold blue-grey / deep blue night / storm light.
- Europe 2031 - Live: same blazer with pushed-up sleeves, on a dark concert stage with band silhouettes, haze, beams.
- The gallery's films (ESCAPE VELOCITY, CLODYSSEY, BLISS, ...) each invented a new look - see claudia.gallery.
