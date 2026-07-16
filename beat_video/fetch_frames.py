"""
HCM beating-heart pipeline, stage 0/1 orchestrator: hydrate selected OneDrive
.vtu timesteps and convert them to surface npz frames.

The source .vtu files are OneDrive cloud-only placeholders. Only a single
buffered whole-file `open().read()` triggers hydration reliably (chunked /
`buffering=0` reads raise OSError 22; Git Bash `cp` gets permission denied), so
we read each whole file in a small thread pool (downloads overlap) and write the
surface-vertex subset straight to frame_XX.npz. Topology (topo.npz) must already
exist (build it once with convert_vtu_surface.py topo on any one local frame).

Hydration is the bottleneck (~20 min per 300 MB file at typical OneDrive speed).

Usage:
    python fetch_frames.py <src_dir> <out_dir> <topo.npz> --indices 0,11,23,... [--prefix HCM1_532_] [--workers 2]
"""
import os
import sys
import time
import argparse
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from convert_vtu_surface import read_points


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src_dir")
    ap.add_argument("out_dir")
    ap.add_argument("topo")
    ap.add_argument("--indices", required=True, help="comma-separated timestep indices")
    ap.add_argument("--prefix", default="HCM1_532_")
    ap.add_argument("--digits", type=int, default=4)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()

    indices = [int(x) for x in a.indices.split(",")]
    os.makedirs(a.out_dir, exist_ok=True)
    surf_vidx = np.load(a.topo)["surf_vidx"]

    def do(pos_idx):
        pos, idx = pos_idx
        out = os.path.join(a.out_dir, f"frame_{pos:02d}.npz")
        if os.path.exists(out):
            return pos, idx, 0.0, "skip"
        src = os.path.join(a.src_dir, f"{a.prefix}{idx:0{a.digits}d}.vtu")
        t0 = time.time()
        pts = read_points(src)                       # buffered whole-file read -> hydrates OneDrive
        np.savez_compressed(out, points=pts[surf_vidx].astype(np.float32))
        return pos, idx, time.time() - t0, "ok"

    jobs = list(enumerate(indices))
    print(f"fetching {len(jobs)} frames with {a.workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for fut in as_completed([ex.submit(do, j) for j in jobs]):
            pos, idx, dt, st = fut.result()
            print(f"[{time.strftime('%H:%M:%S')}] frame_{pos:02d} (idx {idx:0{a.digits}d}) {st} {dt:.0f}s", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
