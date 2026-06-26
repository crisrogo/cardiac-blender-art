import sys
import os
from PIL import Image

# Finalize contest 4K PNGs: flatten to opaque RGB, embed 300 dpi, report size/limits.
for f in sys.argv[1:]:
    im = Image.open(f)
    if im.mode != "RGB":
        im = im.convert("RGB")
    im.save(f, dpi=(300, 300))
    mb = os.path.getsize(f) / 1e6
    sq = "square" if im.size[0] == im.size[1] else f"NOT square {im.size}"
    size_ok = "OK" if mb <= 20 else "OVER 20MB -> needs JPG export"
    print(f"{os.path.basename(f):34s} {im.size[0]}x{im.size[1]} {sq} RGB dpi=300  {mb:5.1f} MB  [{size_ok}]")
