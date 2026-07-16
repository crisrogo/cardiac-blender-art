"""
HCM beating-heart pipeline, stage 1: VTU (volumetric tet mesh) -> compact surface npz.

Lives in its own `beat_video/` directory (separate from the glass-art contest
scripts) because it is a different kind of visualisation — a beating-heart video
rather than a still art render — and keeping it apart improves reproducibility.

The HCM simulation exports one ~300 MB .vtu per timestep (≈0.75 M points,
≈3.9 M tetrahedra; point `displacement`, cell `elemTags`, cell `fibres`). For an
external beating-heart render we only need the *outer surface* of the mesh, and
because the node connectivity is constant across timesteps we extract the
boundary triangulation (and its per-face region tag) exactly once, then store
only the moving surface-point coordinates per frame.

NOTE on the source files: they are typically OneDrive cloud-only placeholders.
A single buffered whole-file Python `open().read()` triggers OneDrive hydration;
Git Bash `cp`/`head` get "permission denied" and chunked / `buffering=0` reads
raise `OSError 22`. `fetch_frames.py` handles hydration robustly.

Usage (system Python + meshio):
    python convert_vtu_surface.py topo   <ref.vtu> <topo.npz>
    python convert_vtu_surface.py points <frame.vtu> <out.npz> <topo.npz>
"""
import os
import re
import sys
import time
import base64
import numpy as np


# ---------- fast points-only reader (uncompressed binary VTU, UInt64 header) ----------
def _binary_array(data, name):
    # attribute order varies (Points has Name before format; displacement after) -> match the
    # whole opening tag by Name regardless of order, then decode the base64 body after it.
    m = re.search(rb'<DataArray[^>]*\bName="' + name + rb'"[^>]*>', data)
    if not m or b'format="binary"' not in m.group(0):
        raise RuntimeError(f'no binary "{name.decode()}" array')
    start = m.end()
    end = data.find(b"</DataArray>", start)
    b = base64.b64decode(re.sub(rb"\s", b"", data[start:end]))
    nbytes = int(np.frombuffer(b[:8], dtype="<u8")[0])
    return np.frombuffer(b[8:8 + nbytes], dtype="<f4").reshape(-1, 3)


def read_points(path):
    """Deformed node positions = reference Points + displacement (the motion is
    stored in `displacement`; Points alone is the static reference for every frame)."""
    with open(path, "rb") as f:                      # buffered whole-file read (hydrates OneDrive)
        data = f.read()
    pts = _binary_array(data, b"Points")
    disp = _binary_array(data, b"displacement")
    return (pts + disp).copy()


# ---------- boundary-surface extraction from a tetrahedral mesh ----------
def extract_surface(points, tets, tags):
    """Return (faces, face_tags) for the boundary of the tet mesh.
    A triangular face is on the boundary iff it belongs to exactly one tet.
    Memory-light: faces are packed into one int64 key instead of np.unique(axis=0)."""
    T = len(tets)
    N = len(points)
    f0 = tets[:, [1, 2, 3]]; f1 = tets[:, [0, 2, 3]]
    f2 = tets[:, [0, 1, 3]]; f3 = tets[:, [0, 1, 2]]
    faces = np.concatenate([f0, f1, f2, f3], axis=0).astype(np.int64)   # (4T,3), row r -> tet r%T
    del f0, f1, f2, f3
    sf = np.sort(faces, axis=1)
    keys = (sf[:, 0] * N + sf[:, 1]) * N + sf[:, 2]
    del sf
    uk, ui, uc = np.unique(keys, return_index=True, return_counts=True)
    bidx = ui[uc == 1]
    surf_faces = faces[bidx].astype(np.int32)
    surf_tags = tags[(bidx % T)].astype(np.int32)
    return surf_faces, surf_tags


def build_topo(ref_path, out_npz):
    import meshio
    t0 = time.time()
    print(f"[topo] reading {os.path.basename(ref_path)} ...", flush=True)
    m = meshio.read(ref_path)
    pts = m.points.astype(np.float32)
    tets = next(c.data.astype(np.int64) for c in m.cells if c.type == "tetra")
    tags = np.asarray(m.cell_data["elemTags"][0]).reshape(-1).astype(np.int32)
    print(f"[topo] {len(pts)} pts, {len(tets)} tets, read {time.time()-t0:.0f}s", flush=True)
    faces_full, face_tags = extract_surface(pts, tets, tags)
    surf_vidx = np.unique(faces_full)
    remap = np.full(len(pts), -1, dtype=np.int64); remap[surf_vidx] = np.arange(len(surf_vidx))
    faces = remap[faces_full].astype(np.int32)
    os.makedirs(os.path.dirname(os.path.abspath(out_npz)), exist_ok=True)
    np.savez_compressed(out_npz, faces=faces, surf_vidx=surf_vidx.astype(np.int32), face_tags=face_tags)
    u, c = np.unique(face_tags, return_counts=True)
    print(f"[topo] {len(surf_vidx)} surf verts, {len(faces)} faces -> {out_npz}")
    print("[topo] face elemTags:", "  ".join(f"{int(a)}:{int(b)}" for a, b in zip(u, c)))


def write_frame(frame_path, out_npz, topo_npz):
    surf_vidx = np.load(topo_npz)["surf_vidx"]
    pts = read_points(frame_path)
    np.savez_compressed(out_npz, points=pts[surf_vidx].astype(np.float32))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "topo":
        build_topo(sys.argv[2], sys.argv[3])
    elif cmd == "points":
        write_frame(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
