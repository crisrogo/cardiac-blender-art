"""Prepare a cover render for JMCC submission.

The guidelines ask for 19.7 x 19.7 cm at a minimum of 300 dpi. A 4096 px square
tagged at 300 dpi would *declare* 34.7 cm, so this tags the dpi that makes the
declared physical size exactly 19.7 cm while leaving the resolution well above
the minimum (4096 px -> 528 dpi).

    python finalize_cover.py "output/cover/4k/cover - arc - femesh.png"
"""
import os
import sys
from PIL import Image

SIDE_CM = 19.7
CM_PER_IN = 2.54
SIDE_IN = SIDE_CM / CM_PER_IN          # 7.7559 in
MIN_PX = 2327                          # 19.7 cm at 300 dpi

for f in sys.argv[1:]:
    im = Image.open(f)
    if im.mode != "RGB":
        im = im.convert("RGB")          # flatten alpha -> guaranteed opaque black
    w, h = im.size
    dpi = round(w / SIDE_IN, 1)
    out = os.path.splitext(f)[0] + " [print].png"
    im.save(out, dpi=(dpi, dpi))
    mb = os.path.getsize(out) / 1e6
    notes = []
    if w != h:
        notes.append(f"NOT SQUARE ({w}x{h})")
    if w < MIN_PX:
        notes.append(f"UNDER 300 dpi at 19.7 cm (needs >= {MIN_PX} px)")
    if mb > 20:
        notes.append("over 20 MB - may need a JPEG for upload limits")
    status = "; ".join(notes) if notes else "OK"
    print(f"{os.path.basename(out):46s} {w}x{h}  {dpi} dpi  "
          f"= {w / dpi * CM_PER_IN:.1f} x {h / dpi * CM_PER_IN:.1f} cm  {mb:5.1f} MB  [{status}]")
