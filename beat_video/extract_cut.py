"""
HCM beat-video pipeline: build the "cut-in-half" cross-section geometry.

The orbit shows the whole outer surface; after the orbit the heart is cut on the
anterior plane to reveal the four chambers, then beats. The cut is a TRUE solid
cross-section: we keep the posterior half of the tetrahedral *volume* (relative
to the anterior camera) and re-extract its boundary, so the cut plane is a filled
myocardium section and the chamber cavities appear as concavities. Per-face tags
are preserved so chambers/myocardium can be coloured.

Because the cut exposes interior vertices, the renderer needs the FULL per-frame
point arrays (not just the outer-surface subset), so this script also writes
frame_XX_full.npz.

Run with system Python + meshio. The orientation (and thus the cut plane) is the
shared anatomical one in orient.py — NO PCA.

    python extract_cut.py cut  <ref.vtu> <topo.npz> <out_cut.npz> [offset_frac=0.5]
    python extract_cut.py full <frame.vtu> <out_full.npz>
"""
import os
import sys
import numpy as np

from convert_vtu_surface import read_points, extract_surface
import orient as orientmod


def build_cut(ref_path, topo_npz, out_cut, offset_frac=0.5,
              valve_tags=(7, 8, 9, 10), lv_endo_tag=25):
    import meshio
    m = meshio.read(ref_path)
    pts = (m.points + np.asarray(m.point_data["displacement"])).astype(np.float64)   # deformed frame 0
    tets = next(c.data.astype(np.int64) for c in m.cells if c.type == "tetra")
    tags = np.asarray(m.cell_data["elemTags"][0]).reshape(-1).astype(np.int32)

    topo = np.load(topo_npz)
    P_surf = pts[topo["surf_vidx"]]
    o = orientmod.compute_orientation(P_surf, topo["faces"], topo["face_tags"],
                                      valve_tags, lv_endo_tag)
    R, gc = o["R"], o["gc"]
    W = (pts - gc) @ R.T                                   # world coords; +Y = anterior
    cy = W[tets].mean(axis=1)[:, 1]                        # tet-centroid anterior coord
    ylo, yhi = W[:, 1].min(), W[:, 1].max()
    cut_level = ylo + offset_frac * (yhi - ylo)
    keep = cy <= cut_level                                 # drop the anterior (camera-side) half
    kept_tets, kept_tags = tets[keep], tags[keep]
    print(f"[cut] keep {keep.sum()}/{len(tets)} tets (offset_frac={offset_frac}, "
          f"cut_level={cut_level:.0f})")

    faces_full, face_tags = extract_surface(pts, kept_tets, kept_tags)
    cut_vidx = np.unique(faces_full)
    remap = np.full(len(pts), -1, dtype=np.int64); remap[cut_vidx] = np.arange(len(cut_vidx))
    faces = remap[faces_full].astype(np.int32)
    os.makedirs(os.path.dirname(os.path.abspath(out_cut)), exist_ok=True)
    np.savez_compressed(out_cut, faces=faces, cut_vidx=cut_vidx.astype(np.int32),
                        face_tags=face_tags)
    u, c = np.unique(face_tags, return_counts=True)
    print(f"[cut] {len(cut_vidx)} verts, {len(faces)} faces -> {out_cut}")
    print("[cut] tags:", "  ".join(f"{int(a)}:{int(b)}" for a, b in zip(u, c)))


def write_full(frame_path, out_full):
    pts = read_points(frame_path)
    np.savez_compressed(out_full, points=pts.astype(np.float32))


def build_series(ref_path, topo_npz, out_dir, n=12, lo=0.5, hi=0.96):
    """A series of cut depths (shallow hi -> half lo) for the progressive cut:
    writes topo_cut_00.npz (shallowest) .. topo_cut_{n-1}.npz (half)."""
    import meshio
    m = meshio.read(ref_path)
    pts = (m.points + np.asarray(m.point_data["displacement"])).astype(np.float64)   # deformed frame 0
    tets = next(c.data.astype(np.int64) for c in m.cells if c.type == "tetra")
    tags = np.asarray(m.cell_data["elemTags"][0]).reshape(-1).astype(np.int32)
    topo = np.load(topo_npz)
    o = orientmod.compute_orientation(pts[topo["surf_vidx"]], topo["faces"], topo["face_tags"])
    R, gc = o["R"], o["gc"]
    W = (pts - gc) @ R.T
    cy = W[tets].mean(axis=1)[:, 1]
    ylo, yhi = W[:, 1].min(), W[:, 1].max()
    os.makedirs(out_dir, exist_ok=True)
    fracs = np.linspace(hi, lo, n)                     # shallow -> half
    for i, frac in enumerate(fracs):
        keep = cy <= (ylo + frac * (yhi - ylo))
        faces_full, ftags = extract_surface(pts, tets[keep], tags[keep])
        vidx = np.unique(faces_full)
        remap = np.full(len(pts), -1, dtype=np.int64); remap[vidx] = np.arange(len(vidx))
        np.savez_compressed(os.path.join(out_dir, f"topo_cut_{i:02d}.npz"),
                            faces=remap[faces_full].astype(np.int32),
                            cut_vidx=vidx.astype(np.int32), face_tags=ftags)
        print(f"[series] {i:02d} frac={frac:.3f} keep={keep.sum()} verts={len(vidx)}", flush=True)
    print(f"[series] {n} depths -> {out_dir}")


def build_series_fast(ref_path, topo_npz, out_dir, n=96, lo=0.5, hi=0.96):
    """Same as build_series but shares the (expensive) face structure across all depths,
    so many depths are cheap (each depth is one numpy pass). Sorted-triple winding is
    fine (the renderer recalculates normals)."""
    import meshio
    m = meshio.read(ref_path)
    pts = (m.points + np.asarray(m.point_data["displacement"])).astype(np.float64)
    tets = next(c.data.astype(np.int64) for c in m.cells if c.type == "tetra")
    tags = np.asarray(m.cell_data["elemTags"][0]).reshape(-1).astype(np.int32)
    T = len(tets); N = len(pts)
    topo = np.load(topo_npz)
    o = orientmod.compute_orientation(pts[topo["surf_vidx"]], topo["faces"], topo["face_tags"])
    R, gc = o["R"], o["gc"]
    W = (pts - gc) @ R.T
    cy = W[tets].mean(axis=1)[:, 1]
    ylo, yhi = W[:, 1].min(), W[:, 1].max()
    # face structure (once): sorted vertex triples, packed keys, per-row tet index
    faces = np.concatenate([tets[:, [1, 2, 3]], tets[:, [0, 2, 3]],
                            tets[:, [0, 1, 3]], tets[:, [0, 1, 2]]], axis=0)
    sf = np.sort(faces, axis=1); del faces
    keys = (sf[:, 0] * N + sf[:, 1]) * N + sf[:, 2]
    tet_row = np.tile(np.arange(T), 4)
    order = np.argsort(keys, kind="stable")
    skeys = keys[order]; sf = sf[order]; tet_row = tet_row[order]; del keys
    newg = np.empty(len(skeys), bool); newg[0] = True; newg[1:] = skeys[1:] != skeys[:-1]
    gid = np.cumsum(newg) - 1
    rep_face = sf[newg]                      # representative vertex triple per unique face
    tags_row = tags[tet_row]
    os.makedirs(out_dir, exist_ok=True)
    for i, frac in enumerate(np.linspace(hi, lo, n)):
        kept = (cy <= (ylo + frac * (yhi - ylo)))
        kf = kept[tet_row]
        ksum = np.bincount(gid, weights=kf.astype(np.float64), minlength=gid[-1] + 1)
        bmask = np.isclose(ksum, 1.0)        # boundary: exactly one adjacent tet kept
        bfaces = rep_face[bmask]
        tagsum = np.bincount(gid, weights=(kf * tags_row).astype(np.float64), minlength=gid[-1] + 1)
        ftags = np.rint(tagsum[bmask]).astype(np.int32)
        vidx = np.unique(bfaces)
        remap = np.full(N, -1, dtype=np.int64); remap[vidx] = np.arange(len(vidx))
        np.savez_compressed(os.path.join(out_dir, f"topo_cut_{i:02d}.npz"),
                            faces=remap[bfaces].astype(np.int32), cut_vidx=vidx.astype(np.int32), face_tags=ftags)
    print(f"[fastseries] {n} depths -> {out_dir}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "cut":
        off = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
        build_cut(sys.argv[2], sys.argv[3], sys.argv[4], off)
    elif cmd == "full":
        write_full(sys.argv[2], sys.argv[3])
    elif cmd == "series":
        n = int(sys.argv[5]) if len(sys.argv) > 5 else 12
        build_series(sys.argv[2], sys.argv[3], sys.argv[4], n)
    elif cmd == "fastseries":
        n = int(sys.argv[5]) if len(sys.argv) > 5 else 96
        build_series_fast(sys.argv[2], sys.argv[3], sys.argv[4], n)
    else:
        print(__doc__)
