import os
import numpy as np

OUT = (os.environ.get("NPZ_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "beat_npz"))
topo = np.load(os.path.join(OUT, "topo.npz"))
faces, tags = topo["faces"], topo["tags"]
p0 = np.load(os.path.join(OUT, "frame_00.npz"))["points"]

c_all = p0.mean(0)
print("overall centroid", c_all.round(1), "bbox", p0.min(0).round(1), "->", p0.max(0).round(1))
print(f"\n{'tag':>4} {'cells':>7} {'verts':>7}   centroid (x,y,z)        size (x,y,z)")
for t in np.unique(tags):
    fm = tags == t
    vi = np.unique(faces[fm])
    v = p0[vi]
    cen = v.mean(0); sz = v.max(0) - v.min(0)
    print(f"{int(t):>4} {int(fm.sum()):>7} {len(vi):>7}   ({cen[0]:6.1f},{cen[1]:6.1f},{cen[2]:6.1f})   ({sz[0]:5.1f},{sz[1]:5.1f},{sz[2]:5.1f})")

# PCA long axis of whole mesh
X = p0 - c_all
w, V = np.linalg.eigh(X.T @ X / len(X))
print("\nPCA eigenvalues (asc):", w.round(0))
print("PCA axes (columns, smallest->largest):\n", V.round(3))

# motion magnitude per vertex across frames (max displacement)
import glob
frames = sorted(glob.glob(os.path.join(OUT, "frame_*.npz")))
pts = np.stack([np.load(f)["points"] for f in frames])  # (T, N, 3)
disp = np.linalg.norm(pts - pts[0], axis=2)             # (T, N)
print("\nframes:", len(frames))
print("max per-vertex displacement over cycle (mm): %.1f" % disp.max())
print("mean displacement at most-contracted frame: %.1f" % disp.mean(1).max())
