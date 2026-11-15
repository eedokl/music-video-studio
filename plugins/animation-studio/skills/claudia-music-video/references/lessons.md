# Lessons from Europe 2031 (studio, V1 -> V2) and Europe 2031 - Live

| rule | why (what happened) |
|---|---|
| Never "young" in a prompt; write "28-year-old" / "late twenties" | image models drift her teenage |
| Identity text unchanged in every prompt; streak mentioned once | rewording or repeating gave two streaks |
| Mic: "single thin beige headset microphone, boom along her right cheek"; mic negatives always | "thin headset microphone" alone changed mic count, colour and side between clips; one S2V clip gave her a handheld mic (rejected) |
| Check start images for TWO microphones (canon.py mic test) | Qwen-Edit drew a boom on both cheeks in half of the variants despite the negatives (Europe 2031 V2 start images 4/7/27/40, plugin test 2 of 4) |
| Repair a two-mic start image by retouching the WRONG boom only (mask + OpenCV fill + FLUX refine on the mask), Qwen-Edit only as second try | the reference V5 repair (Qwen-Edit "change only the microphone" on the whole image) still left two mics on live start 17; the retouch changes only the masked pixels (face, streak, correct mic stay identical); clean when the boom lies on skin (2/6 test images), a visible patch where it crossed the hair edge or a 3/4 jaw - so every repair is checked by eye (mic_repair test 2026-11-14) |
| Two references for close/medium start images (face + streak close-up), one for wide | single reference produced the double streak; the close-up fixed it |
| LTX positive prompt never "no text"; text/letters/logos only in the negative prompt | V1 moving clips 01/06/11 painted garbled letters; re-rendered clean with text only negative |
| Every video prompt has ONE light sentence matching its start image | clip 21 jumped to another scene without one |
| Screens and projections: "no person / no face on the screen" in the negative | live clip 28 turned a projection into a face - Christian would no longer be anonymous |
| LTX seeds vary a lot: 2 seeds per sung shot, 4 for weak ones; pick by measured lip score | same shot ranged from r 0.10 to 0.58 across seeds |
| Reject clips whose mouth stays closed (range < 0.1) | shot 34 V1: mouth practically shut (range 0.005) |
| Apply the measured lag: lag > 0 = mouth late, show dt = +lag/24 later (only when it gains >= 0.08) | V2 shots 35/52/57 gained 0.15-0.5 with +3 frames |
| LTX clips start 0.25 s before the shot; the picture is placed 1 frame later | LTX starts sluggishly from the still; decoded picture ~50 ms early |
| S2V only for single expressive moments < 4.7 s | S2V clips 7 and 49 were expressive but off the words (r ~ 0); long runs drift to profile |
| Moving stills (LTX on the instrumental) instead of Ken Burns | V1 was 48 % stills with parallax - too static; V2 had 1 still left |
| Instrumental from Demucs (or a stem mix), not song minus vocal stems | mastered song != sum of stems: subtraction keeps vocal residue -> LTX makes people sing |
| Loud choruses: measure against Rhubarb AND loudness (`--curve mix`) | separated vocals carry choir/bleed; Rhubarb alone gave negative r for good lips |
| From behind, the streak is on the image right | live start images 36/66 had it on the wrong side |
| Label the film as AI-generated; credit "Claudia by anabology" | LTX licence; plugin rule; Claudia's licence asks for it |
| ComfyUI that ran for days: flush (`/free`) before every phase, retry once | 38 GB private memory -> `HostBuffer.read_file_slice failed` |
| B-roll FLUX stills: check for invented lettering on screens/boards | FLUX ignores "no text" now and then |
| Crowds: LTX img_compression 42 + "A cinematic scene of a rowdy, packed concert audience going wild." (`"recipe": "crowd"`) | plain prompts froze the crowd (motion 0.1-0.9, 2 of 3 frozen); the recipe x11 motion |
| Reject clips with a hidden scene cut or a frozen stretch (pick.py, motion_check) | live V2/V4: LTX jumped to another scene or stopped moving in several takes that measured fine on lips |
| Level every vocal input (-16 dBFS sung RMS, peaks -1 dBFS, ramps); start the window in a silence | live V2 onwards; quiet inputs gave tame mouths |
| Long sung passages: one chained InfiniteTalk take instead of several cuts | live V3 bridge 12.7 s, no seams; lip score like the reference |
| Typography only in code (typo.py), never by a model | models garble letters; stamps must land on the sung word |
| S2V re-adds a second mic between frames even from a one-mic start image; check the whole clip by eye | Europe 2031 re-shoot shot 46 |
| Real-ESRGAN smooths freckles | upscale test on an S2V close-up |
| Profile shots are not measurable (no face found) | live shot 14 - judge by eye |

Weak spots that stayed (no model solved them): lips closing on short p/b/m; fast spoken lines with plosives
(LTX r ~ 0 there; HuMo 1.7B / MiniMax were better but rejected for other reasons).

- **Plain vs timeline prompt (A/B test 2026-11-15, Europe 2031 live, 8 shots x 2 seeds, same seeds/images/audio):**
  metrics equal (lip 0.198 vs 0.206, motion 4.39 vs 4.24). By eye the timeline prompt won the multi-action shots
  (gesture list, chorus head bob + arms, "Hey" fist + walk); the plain prompt won close-ups, spoken lines, the quiet
  bridge and the run + jump (weak in all takes). Hence: plain by default, `timeline` only for multi-action shots,
  rendered mixed (A on odd, B on even seeds).
