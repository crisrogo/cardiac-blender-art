import re
import sys

path = sys.argv[1]
kw = re.compile(r"^(DATASET|POINTS|POLYGONS|CELLS|CELL_TYPES|VERTICES|LINES|POINT_DATA|CELL_DATA|SCALARS|VECTORS|NORMALS|TENSORS|FIELD|LOOKUP_TABLE|COLOR_SCALARS)\b", re.I)
print("== structural lines in", path, "==")
shown = 0
with open(path, errors="ignore") as fh:
    for i, line in enumerate(fh):
        s = line.strip()
        if kw.match(s):
            print(f"{i:>9}: {s[:90]}")
            shown += 1
        if i > 4000000 or shown > 60:
            break
