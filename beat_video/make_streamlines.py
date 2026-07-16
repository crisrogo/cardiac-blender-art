"""
Generate myofiber STREAMLINES (tracts) from the real .lon field, for rendering as
tubes. Seeds are downsampled to an even spacing (one per grid cell) inside the
chosen myocardial regions; each seed is integrated bidirectionally along the fiber
field (nearest-vertex lookup via a KD-tree, with sign continuity). Tracts are
stored in RAW coordinates (the renderer applies the shared orientation).

    python make_streamlines.py <ref.vtu> <lon> <out_dir> [spacing_um=3000] [tags=1,2]

Output: streamlines.npz {points (N,3), offsets (L+1,)}  (polyline l = points[offsets[l]:offsets[l+1]])
"""
import os
import sys
import time
import numpy as np
from scipy.spatial import cKDTree

STEP = 600.0        # integration step (micrometres)
MAX_STEPS = 55      # per direction
MIN_PTS = 10        # drop stubby tracts


def load_lon(path):
    with open(path) as f:
        naxes = int(f.readline())
        arr = np.fromstring(f.read(), sep=" ", dtype=np.float32)
    return arr.reshape(-1, 6 if naxes == 2 else 3)[:, :3]


# coverage sets to generate in one mesh-read: name -> myocardial tags
SETS = [("ventricles", (1, 2)), ("atria", (3, 4)), ("all", (1, 2, 3, 4))]


def main(ref, lon, out_dir, spacing=3000.0):
    import meshio
    t0 = time.time()
    m = meshio.read(ref)
    pts = (m.points + np.asarray(m.point_data["displacement"])).astype(np.float64)   # deformed frame 0
    tets = next(c.data for c in m.cells if c.type == "tetra").astype(np.int64)
    etags = np.asarray(m.cell_data["elemTags"][0]).reshape(-1).astype(np.int32)
    fib = load_lon(lon)
    print(f"[str] {len(pts)} pts {len(tets)} tets, read {time.time()-t0:.0f}s", flush=True)

    flat = tets.ravel(); rep = np.repeat(fib, 4, axis=0).astype(np.float64)
    vf = np.stack([np.bincount(flat, weights=rep[:, c], minlength=len(pts)) for c in range(3)], axis=1)
    nrm = np.linalg.norm(vf, axis=1, keepdims=True); nrm[nrm == 0] = 1; vf /= nrm
    tree = cKDTree(pts)
    maxd = spacing * 1.5
    os.makedirs(out_dir, exist_ok=True)

    def gen_set(name, tags):
        myo_vid = np.unique(tets[np.isin(etags, tags)])
        is_myo = np.zeros(len(pts), bool); is_myo[myo_vid] = True
        keys = np.floor(pts[myo_vid] / spacing).astype(np.int64)
        _, uidx = np.unique(keys, axis=0, return_index=True)
        seeds = myo_vid[uidx]

        def half(p0, sign):
            out = []; prev = None; p = p0.copy()
            for _ in range(MAX_STEPS):
                d, i = tree.query(p)
                if d > maxd or not is_myo[i]:
                    break
                f = vf[i].copy()
                f = f * sign if prev is None else (-f if np.dot(f, prev) < 0 else f)
                prev = f; p = p + STEP * f; out.append(p.copy())
            return out

        lines = []
        for s in seeds:
            p0 = pts[s]
            line = half(p0, -1)[::-1] + [p0] + half(p0, +1)
            if len(line) >= MIN_PTS:
                lines.append(np.array(line))
        allpts = np.concatenate(lines, axis=0)
        offsets = np.concatenate([[0], np.cumsum([len(l) for l in lines])]).astype(np.int64)
        np.savez_compressed(os.path.join(out_dir, f"streamlines_{name}.npz"),
                            points=allpts.astype(np.float32), offsets=offsets)
        print(f"[str] {name}: {len(seeds)} seeds -> {len(lines)} tracts ({time.time()-t0:.0f}s)", flush=True)

    for name, tags in SETS:
        gen_set(name, tags)
    print("[str] ALL SETS DONE")


if __name__ == "__main__":
    ref, lon, out = sys.argv[1], sys.argv[2], sys.argv[3]
    sp = float(sys.argv[4]) if len(sys.argv) > 4 else 3000.0
    main(ref, lon, out, sp)
