import os
import sys
from PIL import Image, ImageDraw, ImageFont

KIND = sys.argv[1] if len(sys.argv) > 1 else "yaw"   # "yaw" or "roll"
OUTDIR = (os.environ.get("OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
YAWS = list(range(-100, 101, 20))
CELL = 380           # thumbnail size
PAD = 14
LABEL_H = 34
COLS = 4
ROWS = (len(YAWS) + COLS - 1) // COLS

cell_w = CELL + PAD
cell_h = CELL + LABEL_H + PAD
sheet_w = COLS * cell_w + PAD
sheet_h = ROWS * cell_h + PAD
sheet = Image.new("RGB", (sheet_w, sheet_h), (12, 12, 14))
draw = ImageDraw.Draw(sheet)

try:
    font = ImageFont.truetype("arialbd.ttf", 26)
except Exception:
    font = ImageFont.load_default()

for idx, y in enumerate(YAWS):
    path = os.path.join(OUTDIR, f"composition - rap hero {KIND} {y}.png")
    r, c = divmod(idx, COLS)
    x0 = PAD + c * cell_w
    y0 = PAD + r * cell_h
    label = f"{KIND} {y:+d}Â°"
    tw = draw.textlength(label, font=font)
    draw.text((x0 + (CELL - tw) / 2, y0 + 4), label, fill=(235, 235, 240), font=font)
    if os.path.exists(path):
        im = Image.open(path).convert("RGB").resize((CELL, CELL), Image.LANCZOS)
        sheet.paste(im, (x0, y0 + LABEL_H))
    else:
        draw.rectangle([x0, y0 + LABEL_H, x0 + CELL, y0 + LABEL_H + CELL], outline=(80, 80, 80))
        draw.text((x0 + 20, y0 + LABEL_H + 20), "missing", fill=(180, 80, 80), font=font)

out = os.path.join(OUTDIR, f"{KIND} contact sheet.png")
sheet.save(out)
print("CONTACT SHEET ->", out)
