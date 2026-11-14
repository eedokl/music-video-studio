# Blender Grease Pencil (headless) – hand-drawn look, real 3D multiplane

Run: `uv run --no-project python scripts/blender_run.py <script.py> -- [args]` (= `blender -b --factory-startup
--python script.py -- args`, Blender from the config key `blender`).
Working example: `assets/blender_gp_example.py -- --layers <dir> --out <dir> [--still 36] [--nobg]` – Pip drawn frame
by frame on twos with pressure and line boil, painted layers (names of `paint_clearing.py`) as image planes at depth,
camera dolly; 96 frames in ~25 s with EEVEE; saves `pip_gp.blend` the artist can open and draw over with a tablet.

Choose Blender over Synfig when the look should be hand-drawn (variable line weight, boil, frame-by-frame) or when
an artist will continue in Blender; Synfig stays better for tweened vector rigs.

Pitfalls (Grease Pencil v3 via Python, Blender 5.x):
1. **Fills only render if `stroke.fill_id` is non-zero** (undocumented; set a unique id per filled stroke).
2. `show_stroke`/`show_fill` are deprecated no-ops – hide stroke or fill via alpha 0 of `color`/`fill_color`.
3. Material colours are linear – convert hex/sRGB (`srgb()` helper in the example) or they look washed out.
4. Draw in the object's XZ plane (Blender's "front"); call `drawing.tag_positions_changed()` after setting points.
5. `scene.view_settings.view_transform = "Standard"` so painted backgrounds keep their colours; camera
   `sensor_fit = "VERTICAL"` + `angle = fov` matches the three.js multiplane math; raise `clip_end` for far planes.
