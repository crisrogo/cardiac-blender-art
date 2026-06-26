import sys
import os
from PIL import Image

src = sys.argv[1]
im = Image.open(src).convert("RGB")
print(f"source: {im.size[0]}x{im.size[1]}  {os.path.getsize(src)/1e6:.2f} MB")
for q in [int(x) for x in sys.argv[2:]]:
    out = os.path.splitext(src)[0] + f"_q{q}.jpg"
    im.save(out, "JPEG", quality=q, subsampling=0, optimize=True, dpi=(300, 300))
    print(f"q{q:>2}: {os.path.getsize(out)/1e6:5.2f} MB   {out}")
