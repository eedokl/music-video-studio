# Scene catalog – everything built so far

Use this as a **palette of techniques and a memory of what worked**, not as a menu to copy from.
Every new video should mostly consist of scenes invented for *its* lyrics and story. When a past
scene fits, transform it (new metaphor, new layout, new motion) instead of reusing it verbatim.
The full source of each video is in `assets/examples/<project>/src/` – open the relevant `scenes.ts`
when you want to see exactly how something was built.

## Contents
1. The seven videos and their visual identities
2. Lyric presentation techniques
3. Scene archetypes (by technique) with examples
4. Signature effects (held notes, endings, hits)
5. 3D modes
6. What the user liked / disliked

---

## 1. The videos and their visual identities (don't repeat an identity – invent a new one)

| Project (assets/examples) | Song / context | Identity |
|---|---|---|
| `popup-bubbles` | Pop-rock song about running IT systems (song E) | Retro "pop-up video" look: white rounded speech bubbles with thick coloured outline, bloop-pop, info nuggets explaining jargon, 3D data-center corridor + hero cloud |
| `stage-dodge` | Rock song (song D) | Concert stage: procedural female rock singer (jointed rig) dodging/punching flying lyric words (hazard words = red warning plates), LED wall, moving-head beams, crowd, pyro, beat-cut camera director |
| `office-scenes` | Same song as popup-bubbles, styled after a reference video the user named | Software-UI scenes: dark UI, monospace "FIG." headers, giant typed lyric with green highlight + block caret, line-art 3D (keynote stage, exploded-view vault, tunnel, network, globe), pixel mascot |
| `glass-ui-mascot` | Pop-rock team song about a cloud console (song B) | Sky-blue gradients + drifting light blobs, Sora font, rounded window-title pills, glass panels, diagonal colour wipe, soft vector cloud mascot "PIP", 3D cloud city of beat-bouncing server towers |
| `industrial-riff` | Industrial rock, German/English, slow institutions vs. a fast world (song A) | Industrial: concrete/steel, signal red + steel blue/gold, film grain, Anton + Playfair italic (elegance vs. steel), letters stamped like a press, white flashes + shake on riff hits, 3D storm with a ring of stars |
| `content-cards` | Stadium electro-rock presenting a team's roles page (song C) | Look taken from the source page (its colours, flat white cards, 8 px grid) on a dark navy stadium; one scene per sung role with a stage-chain bar, profile card (recoloured icon, quote, tasks, illustration) and an animated metaphor |
| `stadium-broadcast` | Second recording of song A, as a live-concert version | TV broadcast of a stadium concert (concert.ts): LIVE badge + camera labels, the song's story as LED-wall graphics (wall.ts, canvas texture), side screens with a live close-up (render target), 25 moving heads with shader beams in haze, follow spot, flames on big hits, CO2, spark curtain on held notes, confetti, fireworks, ~5,000 instanced fans jumping on the beat, phone lights forming a ring of stars from the sky camera, matte black band silhouettes (bright/metallic figures looked like mannequins), bloom; scenes are declarative (shot + light look + wall visual + lyric style) |

## 2. Lyric presentation techniques

- **Pop-up speech bubbles** with karaoke word highlight (popup-bubbles, `popups.ts`).
- **Typed giant text** with block caret, current word highlighted (office-scenes `lyric.ts` TypedLine).
- **Letter-synced pop/stamp**: each letter appears at its sung moment, spread over the word's real duration (`SungLine`, modes `pop` / stamp in industrial-riff). Current word tinted (accent or per-scene colour). Lead 0.22 s.
- **Typewriter on a screen** (`mode: 'type'`) – terminal intros, PC-screen ending.
- **Caption bar** with word highlight under a 3D scene (stage-dodge).
- **Flying 3D words** that arrive exactly when sung and get punched/dodged (stage-dodge `words.ts`).
- **Full-screen word slams** for chants ("HEY! RISE UP, PEOPLE") – one word at a time, huge, rotated, flash (industrial-riff `heyScene`).
- **Beat bump**: lyric block scales 1 + 0.065–0.085 × pulse while singing.
- **Replace mode** (only current line) for choruses; **stacked mode** for two-line verses.

## 3. Scene archetypes (with examples)

**Software / office UI as stage** (great for work/tech songs): team chat feed with typed hero message; cloud-console access table with a "too broad" warning row; firewall request log scrolling on a tilted 3D plane; PR diff (firewall rule changed, "Author: unknown"); ticket board + incoming call toast; app dialog "Approved by: —"; calendar flooding with audit meetings; timesheet filling with "compliance"; spreadsheet filling; terminal (nslookup → "it was DNS" sticky note; ssh "Permission denied" + chat bubble "not again"); CI/CD pipeline turning green + terraform output; release checklist + deploy bar; windows piling up on a repeated line; expired-secret stamp; robot-account ID card with RETIRED ribbon; video-call grid; roadmap with a pin dropping on Q3.

**Bureaucracy / politics** (industrial-riff): identical-meeting calendar; slide deck flipping on beats ("a roadmap for the roadmap"); split screen fast-town progress bar vs. old-town form stamped "PENDING" with endless spinner; five committees → one report slamming down; minutes whose date runs backwards; four-course "menu of delay" restaurant card; airport split-flap departure board of founders; an empty chair in a timeline of industrial revolutions; rulebook with blank author line; MAYBE/LATER stamped and struck through; breaking-news banner + ticker; gala curtain opening on "Ladies and Gentlemen".

**Data / charts as metaphor**: exponential curve going vertical with glitch ("the future racing ahead"); gauges for speed vs. risk; health dashboard tiles all green; EKG heartbeat for a "still alive?" line; year odometer 2026 → 2030; tokens/s counter racing.

**Process metaphors** (content-cards, one per role): noisy signal → filtered sine; waveform squeezed into a chip with shrinking RAM/CPU/latency gauges; packets through a collect → clean → store pipeline (dirty packets red); neural net lighting inside a chip; code + falling loss curve; blueprint boxes drawn with stroke-dash; architecture layers stacking; idea bulb branching to "tomorrow"; prototype sketch → conveyor belt with ✓ boxes; test pyramid; nightly test grid catching one red failure; anvil + hammer sparking on the beat; blinking server rack + licenses; backlog re-ordering under a product vision; Kanban with blocker removed.

**People & places (2D silhouettes / SVG)**: clerk at a rainy window looking at the town hall; city skyline in rain with a flip clock ticking to 08:00; a suspension bridge at sunset; hands holding cardboard letter signs (user later found this too close to a reference – use sparingly); conference table top view with "BUBBLE!" speech bubbles; seedling growing into a circuit tree; stone tablet of "certainties" cracking into shards; name tags with job titles falling off.

**Counting / assembling**: tiles/icons appearing 1 → 3 → 7 → 10 → 15 with a huge gradient number, then orbiting as a ring; mosaic of all items lighting in a beat pattern; 15 icons lighting one by one around a ring while wires draw between them.

**Intros**: metal-press title letters stamped on the beat with a ring of stars lighting; notification toasts piling up while the title lands on the beat grid; robotic terminal ("Systems… waking…") over a glitchy oscilloscope; chain of stages connecting with a gradient wire + big title.

## 4. Signature effects

- **Held-note stretch** (`HeldWord` in lyric.ts): when the singer holds a word ("aaaall?", "riiight", "breeeathe", "gooo", "glooow", "waaait"), the vowel multiplies while held (max ~8 copies), copies wave/glow with the measured vocal loudness, a ribbon traces the pitch underneath, the ending letters land on the release with a punch + burst ring. Options: `held`, `heldWord`, `heldVowel`. Pair with a scene reaction via `heldFx()` (dialog trembling + "?" stream; 3D network nodes swelling and flashing on release).
- **Riff-hit flashes**: `hits.json` (song-analysis hits.py) → white flash, screen shake, RGB split on lyrics, lightning bolt in the storm. Big hits stronger.
- **Endings the user loved**: PC monitor typing the last line in sync, then **CRT switch-off** (squash to a glowing line → dot → fade, power LED off) – glass-ui-mascot. **Steel roller shutter slamming down** with stencil title – industrial-riff, with a beat-driven finale for the long outro (impact sparks + dust, stencil spray-painted on with a nozzle cloud, rotating red beacon sweep, a ring of stars burning through the steel one per beat, golden glow when complete, stars outlast the fade to black). **Stage chain completes ✓ → final card with gradient band** – content-cards. Invent a new ending each time that fits the song's last line.
- **Scene cuts**: diagonal colour wipe (glass-ui-mascot), black dip + hit flash (industrial-riff, content-cards), hard cut with 0.16 s scale-in (office-scenes).
- **Instrumental breaks**: give them their own scene (deployment progress over the 3D city; breaking news; title build with riser brightness ramp).

## 5. 3D modes (world3d.ts in the template)

`storm` (rain, rushing grid, lightning on hits, ring of 12 stars: `scatter` blows them apart, `light` = golden dawn), `city` (instanced towers bouncing on the beat under a floating cloud), `network` (hub→spokes nodes lighting up; reacts to `vocal`/`release` opts), `globe` (wireframe globe with arcs drawing between sites), `vault` (exploded-view object with labels; `cage` = private network box), `tunnel` (laptop→proxy→SASE→IDE packet; `success`). Older one-off 3D: data-center corridor with firewall wall and packets, hero cloud with orbit rings (popup-bubbles/world.ts); full concert stage with singer rig (stage-dodge); stadium concert broadcast with LED-wall storytelling (stadium-broadcast/concert.ts – keep beams dim in shots that must read the wall, keep the follow-spot haze out of close-ups). Add a new mode when the song needs a new world.

## 6. What the user liked / disliked (carry this forward)

- Liked: one scene per lyric idea, text that is precisely synced, beat bumps, held-note effects that follow the voice, special endings (CRT off), clean readable cards, per-section colour changes, a fresh look per song.
- Disliked: anything that looks like a copy of a reference video (asked to make it "less like a copy"); coloured marker boxes behind the sung word ("looks better without"); text lagging behind the voice; huge files.
- Liked (content-cards): source illustrations dealt in like cards, drifting inside a family-coloured frame, bumping on the beat with a light glint; asked to tone down bright white page screenshots on the dark stage.
- Asked for: German/English mixed songs handled; a version under 30 MB and one small enough for mail (~12 MB); full-quality file kept plus `_compressed` copy; everything copied to a folder of the user's choice.
