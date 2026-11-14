# Characters from existing raster art (cut-out rigs)

When characters must look *exactly* like given drawings (a presentation, a client's mascot), do not redraw them –
cut the original into parts:

- Upscale the source 4x (Real-ESRGAN; colour on white and alpha separately – the ncnn build has no alpha).
- Separate ink from fill; each fill region goes to the rough part polygon it mostly lies in, shared ink lines go to
  the *front* part, soft edges to the nearest part. The rest pose must be pixel-identical to the original.
- Hidden pieces under joints: grow the part under its occluder, fill it and draw an ink contour at the new edge (only
  deeper than ~10 px under the occluder). Every back part runs ~6 px under the front parts – otherwise a
  semi-transparent seam appears that light shading turns into scribbles.
- Cut joints only where the drawing has a real line (sleeve cuff, wing outline). Safe angles are small (head ±5°,
  tail ±8°); bigger gestures need extra drawings.
- Mouths from the original: open grins are squashed column-wise below the upper-lip line (8 levels, Rhubarb shapes
  map onto them); a closed smile gets a dark opening under its line; a beak hinges at its base.
- Rig the PNG parts in Synfig with `sif.image` layers inside pivot groups; add procedural idle motion (weight shift,
  head/tail follow-through, breathing, irregular blinks) in separate groups so characters never freeze.
- "Line boil" (noise UV wobble every 2 frames) in a three.js figure shader makes cut-out edges feel hand-drawn.
- AI sets for such scenes: ask FLUX for "seen straight from the front at table height, long straight table runs
  horizontally across the full width, parallel to the viewer" – then the table can be cut as a foreground layer.
  Never put hex colours in the prompt (FLUX writes them as text); paint logos/fake text out.
