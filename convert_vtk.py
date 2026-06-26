import os
import numpy as np

SRC = (os.environ.get("VTK_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "meshes", "pacemaker"))
OUT = (os.environ.get("NPZ_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "beat_npz"))
os.makedirs(OUT, exist_ok=True)
TIMES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]   # full cardiac cycle (0-10)


def read_polydata(path):
    toks = open(path).read().split()
    i = toks.index("POINTS"); n = int(toks[i + 1])
    pts = np.array(toks[i + 3: i + 3 + 3 * n], dtype=np.float32).reshape(n, 3)
    j = toks.index("POLYGONS"); m = int(toks[j + 1]); total = int(toks[j + 2])
    poly = np.array(toks[j + 3: j + 3 + total], dtype=np.int64).reshape(m, 4)[:, 1:4].astype(np.int32)
    k = toks.index("elemTag")            # "SCALARS elemTag int" then "LOOKUP_TABLE default"
    tags = np.array(toks[k + 4: k + 4 + m], dtype=np.int32)
    return pts, poly, tags


topo_saved = False
print(f"{'t':>3} {'npts':>8} {' npolys':>8}  centroid (x,y,z)            bbox-diag")
for idx, t in enumerate(TIMES):
    p = os.path.join(SRC, f"transformed-{t}.vtk")
    if not os.path.exists(p):
        print(t, "MISSING"); continue
    pts, poly, tags = read_polydata(p)
    np.savez_compressed(os.path.join(OUT, f"frame_{idx:02d}.npz"), points=pts)
    if not topo_saved:
        np.savez_compressed(os.path.join(OUT, "topo.npz"), faces=poly, tags=tags)
        topo_saved = True
        u, c = np.unique(tags, return_counts=True)
        tag_info = "  ".join(f"{int(a)}:{int(b)}" for a, b in zip(u, c))
    cen = pts.mean(0)
    diag = float(np.linalg.norm(pts.max(0) - pts.min(0)))
    print(f"{t:>3} {len(pts):>8} {len(poly):>8}  ({cen[0]:7.2f},{cen[1]:7.2f},{cen[2]:7.2f})   {diag:7.2f}")

print("\nelemTag (value:cellcount):", tag_info)
print("saved npz ->", OUT)
