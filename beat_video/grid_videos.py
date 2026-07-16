"""Tile the per-material story frame sequences into one grid video (per-frame montage),
so colleagues can compare all materials side by side.

    python grid_videos.py <case_dir> [cell_w=320]
Writes grid_frames/g_XXXX.png then (encode separately with encode_video.py).
"""
import os
import sys
from PIL import Image, ImageDraw

d = sys.argv[1]
CELL_W = int(sys.argv[2]) if len(sys.argv) > 2 else 320
MATS = ["realistic_fresh", "realistic_fibres", "wax", "glass_ruby",
        "porcelain", "bronze", "steampunk", "hipct"]
mats = [m for m in MATS if os.path.isdir(os.path.join(d, f"story_{m}"))]
cols = 4
rows = (len(mats) + cols - 1) // cols
# frame count = min across materials
nfr = min(len([f for f in os.listdir(os.path.join(d, f"story_{m}")) if f.endswith(".png")]) for m in mats)
# cell size from first frame aspect
f0 = Image.open(os.path.join(d, f"story_{mats[0]}", "f_0000.png"))
ar = f0.height / f0.width
cw, ch = CELL_W, int(CELL_W * ar)
pad = 4
outdir = os.path.join(d, "grid_frames"); os.makedirs(outdir, exist_ok=True)
W = cols * cw + (cols + 1) * pad
H = rows * ch + (rows + 1) * pad
print(f"grid {cols}x{rows}, {len(mats)} mats, {nfr} frames, {W}x{H}")
for i in range(nfr):
    sheet = Image.new("RGB", (W, H), (10, 10, 12))
    dr = ImageDraw.Draw(sheet)
    for k, m in enumerate(mats):
        p = os.path.join(d, f"story_{m}", f"f_{i:04d}.png")
        im = Image.open(p).convert("RGB").resize((cw, ch))
        r, c = divmod(k, cols)
        x = pad + c * (cw + pad); y = pad + r * (ch + pad)
        sheet.paste(im, (x, y)); dr.text((x + 5, y + 4), m, fill=(255, 230, 140))
    sheet.save(os.path.join(outdir, f"f_{i:04d}.png"))
    if i % 60 == 0:
        print(f"grid {i+1}/{nfr}", flush=True)
print("GRID FRAMES DONE ->", outdir)
