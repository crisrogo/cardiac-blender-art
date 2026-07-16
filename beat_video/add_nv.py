"""Add a 'nv' field (nearest deformed-frame-0 heart vertex per streamline point) to
each streamlines_*.npz, so the renderer can deform the fibre tracts with the beat
(each tract point rides its nearest heart vertex). Fast: uses frame_000_full points."""
import os
import sys
import numpy as np
from scipy.spatial import cKDTree

d = sys.argv[1]
full0 = np.load(os.path.join(d, "frame_000_full.npz"))["points"].astype(np.float64)
tree = cKDTree(full0)
for cov in ["ventricles", "atria", "all"]:
    p = os.path.join(d, f"streamlines_{cov}.npz")
    if not os.path.exists(p):
        continue
    z = np.load(p)
    _, nv = tree.query(z["points"].astype(np.float64))
    np.savez_compressed(p, points=z["points"], offsets=z["offsets"], nv=nv.astype(np.int32))
    print(cov, "nv added", z["points"].shape)
print("DONE")
