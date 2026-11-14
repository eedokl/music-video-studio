# LDraw parts library – getting it and pointing the plugin at it

The plugin does not ship the library (≈150 MB, ~25 000 part files). It is free (CC BY 2.0 / CC BY 4.0, see
`CAreadme.txt` in the library).

1. Download `complete.zip` from the LDraw website: https://library.ldraw.org/updates?latest (“complete.zip” – the
   whole official library). Optional later: the monthly update zips unpack over it.
2. Unpack it to any folder, e.g. `D:/tools/ldraw`. The folder must contain `LDConfig.ldr`, `parts/` and `p/`
   (`p/48/` holds the high-resolution primitives the importer prefers for round studs).
3. Tell the plugin where it is (machine config, outside the plugin):
   ```
   python "<plugin>/skills/studio-core/scripts/check_tools.py" --set ldraw_dir=D:/tools/ldraw
   ```
   or set the environment variable `LDRAW_DIR`.
4. Check: `python "<plugin>/skills/bricks-3d/scripts/blender_run.py" --check` (`<plugin>` = the plugin folder, as in the SKILL.md commands; or just ask Claude to run the check)

Parts used by the bundled sets and looks (all in the official library): baseplate 3811, bricks 3001/3003/3004/3005/
3010/3622, round 1×1 3062b, round 2×2 brick 3941, tiles 3068b/3069b/3070b/14769 (coins), plates 3020/3034/3795/
3710, window 57894, minifig 973/3815–3820/3626c, hair 3901/62711.

Colours come from `LDConfig.ldr` (codes like 4 = red, 14 = yellow, 72 = dark bluish grey, 379 = sand blue).
