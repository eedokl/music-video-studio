# A cut inside one sung clip (LTX-2.5 multi-shot) - experimental

`skills/ai-video/scripts/ltx25.py` of this plugin renders ONE clip of 6-8 s in which the picture cuts once (e.g. a
close-up, then a frontal medium shot) while the person keeps singing the given vocals. LTX-2.3 (`ltx.py`, the default
for every sung shot) cannot cut. Nothing chooses this engine automatically: a person sets it on a single shot
(claudia-music-video: `"engine": "ltx25"` + `"cuts"`). Evidence so far: two passages of one song, 16 renders
(2026-11-20) - **one take was good enough for a film**. Tell the user that before spending a night on it.

## When it is worth it

- A sung passage of 6-8 s that wants a change of framing in the middle and must stay lip-synced across it, with a
  point in the middle where the song changes (a new line, a shout): that is where the model cuts.
- Not for single shots (LTX-2.3 is faster and holds the frame), not for shots under 6 s, not for wide shots.

## Setup (once per machine)

| what | where |
|---|---|
| transformer `LTX-2.5-Distilled-Q4_K_M.gguf` (14.6 GB) | Hugging Face `Abiray/LTX-2.5-Distilled-GGUF` -> `models/diffusion_models/` |
| text encoder `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` (14.3 GB) | `Lightricks/LTX-2.5` (gated) -> `models/text_encoders/` |
| `ltx-2.5-video-vae-bf16.safetensors`, `ltx-2.5-audio-vae-bf16.safetensors` | `Lightricks/LTX-2.5` (gated) -> `models/vae/` |
| node pack ComfyUI-GGUF (`UnetLoaderGGUF`) + Python package `gguf` in ComfyUI's environment | `custom_nodes/`, restart ComfyUI |

The gated repository needs the user's own Hugging Face account: they accept the terms on the model page and log in on
the machine. Never fetch those files from a mirror. The official transformers need 24-32 GB VRAM; the community GGUF
quant is what fits 16 GB. `preflight.py --kinds ltx25` lists what is missing. ComfyUI 0.43 has every other node.

## Prompt

One chronological paragraph. `ltx25.multishot_prompt(opening, cuts, ending)` writes it:

1. **Shot 1** - the usual lip-sync prompt (who, what is sung in quotes, the mouth sentence, place, light).
2. **The cut as a sentence** - "A hard cut transitions to a frontal medium shot from the waist up in the same room:".
   Shot lists, numbered beats and sluglines do not cut.
3. **The person again, word for word** - hair, clip, microphone, clothes. Never "she" after a cut.
4. **What happens**, then "The song continues unchanged across the cut."
5. **The light once more** for the whole clip.

`ltx25.check_cuts()` refuses what failed in the trial:

| framing after the cut | what happened |
|---|---|
| wide / full / long shot | face ~70 px wide: smeared mouth, the headset melted into the lips, another person |
| "slightly from the side", profile, from behind | became a full profile: mouth and canon cannot be checked |
| frontal medium shot from the waist up | clean, sharp, recognisable face - use this or closer |

## Settings (fixed in the script)

| setting | value | why |
|---|---|---|
| stages | one, 1280x704 | two stages (half size + spatial upscaler) dissolved instead of cutting and peaked at 47 GB RAM |
| sampler | euler, 8 distilled steps, video cfg 1 / audio cfg 1 | euler_ancestral and modality guidance hurt lip-sync (LTX-2.5 model card discussion 44) |
| vocals | `LTXVFreezeLatent` on the encoded audio | the given song stays fixed, the model only makes the picture |
| start image strength | 0.7 | as the LTX-2.3 tests |
| length | 8n+1 frames, at most 193 (8 s) | longer is untested with 48 GB RAM |
| memory | ComfyUI is flushed before every clip | a second 8 s job in a row failed with `hostbuf_file_reader_read` at 47 GB |

Cost on the reference machine (RTX 5060 Ti 16 GB, 48 GB RAM): ~295 s per 8 s clip, 12.4 s per step, peak ~39 GB RAM.

## Seeds and picking

Render three seeds or more (`"ltx25_seeds"`, default 3, at most 6). Typical faults: a second star clip on the other
side of the head, the streak gone after the cut, a second cut a second later. `pick.py clips` therefore treats these clips differently
(`multishot_faults`):

- the wanted cut is not a "hidden cut"; a missing cut (dissolve) or an extra one rejects the take
  (`mouth.motion_check()` -> `cut_events`, `cut_frames`);
- three frames of every shot go through `canon.measure_frames()`: no face, no streak, a second microphone or
  `clips >= 2` (hair clips counted in the hair beside the face) reject the take.

The clip counter found the duplicate in 2 of 3 faulty seeds; a dim, blue-lit second clip escaped it. In the 8 s
plugin test it also named a second clip or microphone on takes whose real fault was the missing streak - the
rejection was right, the reason not always. Look at the takes page - measurements do not replace the eye here.
When every take of a shot is rejected, pick.py still names the best-rated one (as for the other engines): read the
reasons in `picks.log` and set the shot back to `"engine": "ltx"` if none is good.

## Test results

| test | clips | cut | usable | what went wrong |
|---|---|---|---|---|
| trial by hand, conference room, 8 s, close-up -> wide | 2 | 2 of 2 (one a dissolve) | 0 | face ~70 px wide after the cut, broken |
| trial, close-up -> medium shot "slightly from the side" | 2 | 2 of 2 (one a dissolve) | 0 | full profile, the microphone looked like a stick in her mouth |
| trial, close-up -> frontal medium shot, 4 seeds | 4 | 4 of 4 | 1 | 3 takes with a second star clip |
| plugin (jobs.py -> night_run -> pick.py), ferry deck, 4.4 s, one unbroken line, 2 cut wordings x 3 seeds | 6 | 0 of 6 (one soft change of framing) | 0 | too short, no point in the line to cut at; pick.py: "cut missing" on all six |
| plugin, ferry deck at dawn, 7.7 s ("... still alive? Hey! Hey! ..."), close-up -> frontal medium shot, 3 seeds | 3 | 3 of 3, at "Hey!" | 0 | every take cut a second time about a second later and lost the streak after the cut; pick.py: "unwanted cut" on all three |

So: long enough passages cut, and they cut on the music, but holding the canon across the cut is the weak point.
`MIN_SECONDS` is 6 because of the fourth row; nothing between 4.4 and 7.7 s has been rendered.

## Not tested

Three shots in one clip, two singers, spoken lines with the model's own voice inside the plugin (the trial did one
by hand: both lines landed in their shots), other languages, the official int8 / NVFP4 transformers on a bigger card.
