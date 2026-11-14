# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==13.0.0", "pymupdf==2.1", "python-pptx==1.0.2"]
# ///
"""Import a presentation: slide images, a clean plate per slide and every picture with its exact place on the slide.

  deck.py <deck.pptx | deck.pdf | slide1.png slide2.png ...> [--out deck] [--slides 5,7] [--width 3840]
          [--hide "Camera *" "Logo*"] [--keep-master]

Output (deck/):
  slide_NN.png    the slide as the audience sees it
  clean_NN.png    the same without master shapes (logo, footer, page number) and without --hide shapes
                  (default "Camera *": PowerPoint Cameo / live-camera shapes)
  plate_NN.png    clean slide WITHOUT its pictures – the figures are pasted back from the originals, so the film's
                  slide is pixel-exact and a figure can leave a hole
  pictures/sNN_<id>.png   every picture at its original resolution (alpha kept)
  deck.json       slide size, per slide its pictures: rect on the exported slide (px), PowerPoint crop, how picture
                  pixels map to slide pixels, and the slide text (title, notes) for the creative brief
pptx: slide images through PowerPoint (Windows, COM via PowerShell; the file is opened read-only and never saved).
Without PowerPoint the slides are composed from their pictures on white (text missing) – export the slides as
images from the presentation program and pass them as page images instead.
pdf:  PyMuPDF renders pages, embedded images keep their soft mask (alpha).
images: one image = one slide; figures are cut from the slide itself (figures.py).
Usage: uv run deck.py ...
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import _studio
_studio.use()

EMU_PT = 12700


def _xfrm(el):
    """(off_x, off_y, ext_x, ext_y, ch_off_x, ch_off_y, ch_ext_x, ch_ext_y) of a group, in EMU."""
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    x = el.find(".//{%s}xfrm" % ns["a"])
    g = lambda tag, a, b: tuple(int(x.find("{%s}%s" % (ns["a"], tag)).get(k)) for k in (a, b))
    return g("off", "x", "y") + g("ext", "cx", "cy") + g("chOff", "x", "y") + g("chExt", "cx", "cy")


def _walk(shapes, tf=lambda x, y: (x, y), sc=(1.0, 1.0)):
    """All shapes incl. those inside groups, with a transform child -> slide coordinates (EMU)."""
    for sh in shapes:
        if sh.shape_type == 6:                                   # group
            ox, oy, ex, ey, cx, cy, cex, cey = _xfrm(sh._element.grpSpPr)
            fx, fy = ex / cex if cex else 1.0, ey / cey if cey else 1.0

            def tf2(x, y, tf=tf, ox=ox, oy=oy, cx=cx, cy=cy, fx=fx, fy=fy):
                return tf(ox + (x - cx) * fx, oy + (y - cy) * fy)
            yield from _walk(sh.shapes, tf2, (sc[0] * fx, sc[1] * fy))
        else:
            yield sh, tf, sc


def powerpoint_export(pptx, jobs, width, height):
    """jobs: [(slide_no, out_png, hide_names, master)] -> slide images through PowerPoint COM (read-only)."""
    q = lambda p: str(Path(p).resolve()).replace("'", "''")     # single-quoted PowerShell string ("Bob's deck")
    lines = ["$ErrorActionPreference = 'Stop'", "$app = New-Object -ComObject PowerPoint.Application",
             f"$p = $app.Presentations.Open('{q(pptx)}', -1, 0, 0)"]
    for n, out, hide, master in jobs:
        names = ",".join("'" + h.replace("'", "''") + "'" for h in hide) or "''"
        lines += [f"$s = $p.Slides.Item({n})", f"$hide = @({names})", "$off = @()",
                  "foreach ($sh in $s.Shapes) {",
                  "  if ($hide -contains $sh.Name -and $sh.Visible) { $sh.Visible = 0; $off += $sh }",
                  "  elseif ($sh.Type -eq 6) { foreach ($g in $sh.GroupItems) {",
                  "    if ($hide -contains $g.Name -and $g.Visible) { $g.Visible = 0; $off += $g } } } }",
                  f"$s.DisplayMasterShapes = {-1 if master else 0}",
                  f"$s.Export('{q(out)}', 'PNG', {width}, {height})",
                  "foreach ($sh in $off) { $sh.Visible = -1 }", "$s.DisplayMasterShapes = -1"]
    lines += ["$p.Close()", "if ($app.Presentations.Count -eq 0) { $app.Quit() }"]
    ps = Path(tempfile.mkdtemp()) / "export.ps1"
    ps.write_text("\n".join(lines), encoding="utf-8-sig")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)],
                       capture_output=True, text=True, errors="replace")
    return r.returncode == 0, r.stderr[-800:]


def import_pptx(src, out, slides, width, hide_pat, keep_master):
    from pptx import Presentation
    from PIL import Image
    P = Presentation(str(src))
    sw, sh_ = P.slide_width, P.slide_height
    height = round(width * sh_ / sw)
    px = width / sw                                              # px per EMU
    deck = {"source": str(Path(src).name), "kind": "pptx", "width": width, "height": height,
            "slide_pt": [sw / EMU_PT, sh_ / EMU_PT], "slides": []}
    (out / "pictures").mkdir(parents=True, exist_ok=True)
    jobs = []
    for n, slide in enumerate(P.slides, 1):
        if slides and n not in slides:
            continue
        pics, texts, all_names, hidden = [], [], [], []
        for shp, tf, sc in _walk(slide.shapes):
            all_names.append(shp.name)
            if any(fnmatch.fnmatch(shp.name, p) for p in hide_pat):
                hidden.append(shp.name)
                continue
            if shp.has_text_frame and shp.text_frame.text.strip():
                texts.append(shp.text_frame.text.strip())
            if shp.shape_type != 13 or shp.left is None:
                continue
            img = shp.image
            x0, y0 = tf(shp.left, shp.top)
            w, h = shp.width * sc[0], shp.height * sc[1]
            f = out / "pictures" / f"s{n:02d}_{shp.shape_id}.png"
            from io import BytesIO
            im = Image.open(BytesIO(img.blob))
            im = im.convert("RGBA")
            im.save(f)
            iw, ih = im.size
            cl, cr, ct, cb = shp.crop_left, shp.crop_right, shp.crop_top, shp.crop_bottom
            a_x = w * px / (iw * (1 - cl - cr))                     # slide px per picture px
            a_y = h * px / (ih * (1 - ct - cb))
            alpha = im.getchannel("A")
            pics.append({"id": shp.shape_id, "name": shp.name, "file": f"pictures/{f.name}", "size": [iw, ih],
                         "rect": [round(x0 * px, 2), round(y0 * px, 2), round(w * px, 2), round(h * px, 2)],
                         "crop": [round(cl, 5), round(cr, 5), round(ct, 5), round(cb, 5)],
                         "map": {"ax": a_x, "ay": a_y, "ox": x0 * px - cl * iw * a_x, "oy": y0 * px - ct * ih * a_y},
                         "visible": [round(cl * iw), round(ct * ih), round((1 - cr) * iw), round((1 - cb) * ih)],
                         "alpha": alpha.getextrema()[0] < 250})
        notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else ""
        top_names = [s.name for s in slide.shapes]
        rec = {"n": n, "image": f"slide_{n:02d}.png", "clean": f"clean_{n:02d}.png", "plate": f"plate_{n:02d}.png",
               "pictures": pics, "text": texts, "notes": notes, "hidden": hidden}
        deck["slides"].append(rec)
        hide_top = [s for s in top_names if any(fnmatch.fnmatch(s, p) for p in hide_pat)]
        jobs += [(n, out / rec["image"], [], True), (n, out / rec["clean"], hide_top, keep_master),
                 (n, out / rec["plate"], hide_top + [p["name"] for p in pics], keep_master)]
    ok, err = (False, "not Windows") if os.name != "nt" else powerpoint_export(src, jobs, width, height)
    if not ok:
        print(f"  PowerPoint export not available ({err.strip()[:200]}) - composing slides from their pictures")
        for rec in deck["slides"]:
            plate = Image.new("RGBA", (width, height), "white")
            plate.convert("RGB").save(out / rec["plate"])
            full = compose(plate, rec["pictures"], out)
            full.convert("RGB").save(out / rec["clean"])
            full.convert("RGB").save(out / rec["image"])
        deck["composed"] = True
    return deck


def compose(plate, pictures, base, skip=()):
    """Plate + pictures at their exact place (PowerPoint crop applied) -> RGBA slide."""
    from PIL import Image
    out = plate.convert("RGBA").copy()
    for p in pictures:
        if p["id"] in skip:
            continue
        im = Image.open(base / p["file"]).convert("RGBA")
        x0, y0, x1, y1 = p["visible"]
        vis = im.crop((x0, y0, x1, y1))
        w, h = round(p["rect"][2]), round(p["rect"][3])
        out.alpha_composite(vis.resize((w, h), Image.LANCZOS), (round(p["rect"][0]), round(p["rect"][1])))
    return out


def import_pdf(src, out, slides, width):
    import fitz
    from PIL import Image
    doc = fitz.open(str(src))
    r0 = doc[0].rect
    height = round(width * r0.height / r0.width)
    deck = {"source": Path(src).name, "kind": "pdf", "width": width, "height": height,
            "slide_pt": [r0.width, r0.height], "slides": []}
    (out / "pictures").mkdir(parents=True, exist_ok=True)
    for n, page in enumerate(doc, 1):
        if slides and n not in slides:
            continue
        z = width / page.rect.width
        page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).save(str(out / f"slide_{n:02d}.png"))
        pics = []
        for info in page.get_image_info(xrefs=True):
            xref = info.get("xref")
            if not xref:
                continue
            pix = fitz.Pixmap(doc, xref)
            smask = doc.extract_image(xref).get("smask") or 0
            if smask:
                pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
            if pix.n - pix.alpha > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            f = out / "pictures" / f"s{n:02d}_{xref}.png"
            pix.save(str(f))
            im = Image.open(f).convert("RGBA")
            im.save(f)
            x0, y0, x1, y1 = info["bbox"]
            iw, ih = im.size
            ax, ay = (x1 - x0) * z / iw, (y1 - y0) * z / ih
            pics.append({"id": xref, "name": f"image {xref}", "file": f"pictures/{f.name}", "size": [iw, ih],
                         "rect": [x0 * z, y0 * z, (x1 - x0) * z, (y1 - y0) * z], "crop": [0, 0, 0, 0],
                         "map": {"ax": ax, "ay": ay, "ox": x0 * z, "oy": y0 * z}, "visible": [0, 0, iw, ih],
                         "alpha": im.getchannel("A").getextrema()[0] < 250})
        plate_doc = fitz.open(str(src))
        pp = plate_doc[n - 1]
        for p in pics:
            try:
                pp.delete_image(p["id"])
            except Exception:
                pass
        pp.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).save(str(out / f"plate_{n:02d}.png"))
        Image.open(out / f"slide_{n:02d}.png").save(out / f"clean_{n:02d}.png")
        deck["slides"].append({"n": n, "image": f"slide_{n:02d}.png", "clean": f"clean_{n:02d}.png",
                               "plate": f"plate_{n:02d}.png", "pictures": pics,
                               "text": [page.get_text().strip()[:2000]], "notes": ""})
    return deck


def import_images(files, out, width):
    from PIL import Image
    deck = {"source": "images", "kind": "images", "slides": []}
    for n, f in enumerate(files, 1):
        im = Image.open(f).convert("RGB")
        h = round(width * im.height / im.width)
        im = im.resize((width, h), Image.LANCZOS)
        for k in ("slide", "clean"):
            im.save(out / f"{k}_{n:02d}.png")
        deck.setdefault("width", width)
        deck.setdefault("height", h)
        deck["slides"].append({"n": n, "image": f"slide_{n:02d}.png", "clean": f"clean_{n:02d}.png", "plate": None,
                               "pictures": [], "text": [], "notes": "", "from": Path(f).name})
    return deck


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="+")
    ap.add_argument("--out", default="deck")
    ap.add_argument("--slides", default="", help="e.g. 5,7 (default: all)")
    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument("--hide", nargs="*", default=["Camera *"], help="shape name patterns left out of clean/plate")
    ap.add_argument("--keep-master", action="store_true", help="keep logo/footer/page number of the slide master")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    slides = {int(s) for s in a.slides.split(",") if s.strip()}
    src = Path(a.src[0])
    if src.suffix.lower() == ".pptx":
        deck = import_pptx(src, out, slides, a.width, a.hide, a.keep_master)
    elif src.suffix.lower() == ".pdf":
        deck = import_pdf(src, out, slides, a.width)
    else:
        deck = import_images([Path(f) for f in a.src], out, a.width)
    (out / "deck.json").write_text(json.dumps(deck, indent=1, ensure_ascii=False), encoding="utf-8")
    for s in deck["slides"]:
        pics = ", ".join(f"{p['id']} {p['name']} {p['size'][0]}x{p['size'][1]}{' alpha' if p['alpha'] else ''}"
                         for p in s["pictures"])
        print(f"  slide {s['n']:2d}: {len(s['pictures'])} pictures {('(' + pics + ')') if pics else ''}")
    print(f"-> {out / 'deck.json'}")


if __name__ == "__main__":
    sys.exit(main())
