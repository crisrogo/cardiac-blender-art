"""
Compute per-vertex myofiber directions from the openCARP .lon file and sample
them for the outer surface and the cross-section, for use as the `fiber_tan`
anisotropy attribute in the renderer.

The .lon has one row per tetrahedron (header line "2" = fiber + sheet axes,
6 floats/row; we take the first 3 = the fiber direction). Row order matches the
VTU tet order exactly (verified: 3,917,596 rows). We accumulate each tet's fiber
onto its 4 vertices and renormalise to get a smooth per-vertex field, then store
the subsets for topo.surf_vidx and topo_cut.cut_vidx (raw frame; the renderer
rotates them into world space).

    python add_fibres.py <ref.vtu> <lon> <case_dir>
"""
import os
import sys
import time
import numpy as np


def load_lon_fibers(path):
    with open(path) as f:
        naxes = f.readline()                       # "2"
        arr = np.fromstring(f.read(), sep=" ", dtype=np.float32)
    cols = 6 if int(naxes) == 2 else 3
    arr = arr.reshape(-1, cols)
    return arr[:, :3]                              # fiber direction only


def per_vertex_fiber(tets, fib, n_pts):
    flat = tets.ravel()
    rep = np.repeat(fib, 4, axis=0)                # fiber of each tet, once per its 4 verts
    vf = np.empty((n_pts, 3), np.float64)
    for c in range(3):
        vf[:, c] = np.bincount(flat, weights=rep[:, c], minlength=n_pts)
    nrm = np.linalg.norm(vf, axis=1, keepdims=True); nrm[nrm == 0] = 1
    return (vf / nrm).astype(np.float32)


def main(ref, lon, case_dir):
    import meshio
    t0 = time.time()
    m = meshio.read(ref)
    tets = next(c.data.astype(np.int64) for c in m.cells if c.type == "tetra")
    n_pts = len(m.points)
    print(f"[fib] mesh {n_pts} pts {len(tets)} tets ({time.time()-t0:.0f}s)")
    fib = load_lon_fibers(lon)
    print(f"[fib] lon fibers {fib.shape}; tets match: {len(fib) == len(tets)}")
    assert len(fib) == len(tets), "lon rows != tet count"
    vf = per_vertex_fiber(tets, fib, n_pts)        # (n_pts,3) raw-frame fiber per vertex

    topo = np.load(os.path.join(case_dir, "topo.npz"))
    out = {"surf_fiber": vf[topo["surf_vidx"]]}
    cut_path = os.path.join(case_dir, "topo_cut.npz")
    if os.path.exists(cut_path):
        out["cut_fiber"] = vf[np.load(cut_path)["cut_vidx"]]
    np.savez_compressed(os.path.join(case_dir, "fibres.npz"), **out)
    print("[fib] saved fibres.npz:", {k: v.shape for k, v in out.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
