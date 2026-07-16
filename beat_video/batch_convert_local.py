"""
Batch-convert all locally-hydrated VTU timesteps to full-points npz frames.

Use after OneDrive has bulk-downloaded the case folder ("Always keep on this
device"). Reads only files that are fully hydrated (skips cloud-only placeholders
so it never blocks on a recall), and writes frame_<idx>_full.npz. The renderer
derives both the outer surface and the cross-section from these full arrays.

    python batch_convert_local.py <src_dir> <out_dir> [--prefix HCM1_532_] [--first 0 --last 101 --step 1]

Re-run as more frames finish downloading; it skips ones already converted.
"""
import os
import sys
import time
import ctypes
import argparse
import numpy as np

from convert_vtu_surface import read_points

RECALL = 0x400000  # FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS (cloud-only placeholder)
_GetAttr = ctypes.windll.kernel32.GetFileAttributesW


def is_local(path):
    a = _GetAttr(ctypes.c_wchar_p(path))
    return a != 0xFFFFFFFF and not (a & RECALL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src_dir"); ap.add_argument("out_dir")
    ap.add_argument("--prefix", default="HCM1_532_")
    ap.add_argument("--digits", type=int, default=4)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--last", type=int, default=101)
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    done = skipped = missing = 0
    for idx in range(a.first, a.last + 1, a.step):
        src = os.path.join(a.src_dir, f"{a.prefix}{idx:0{a.digits}d}.vtu")
        out = os.path.join(a.out_dir, f"frame_{idx:03d}_full.npz")
        if os.path.exists(out):
            done += 1; continue
        if not os.path.exists(src):
            missing += 1; continue
        if not is_local(src):
            skipped += 1; continue
        t0 = time.time()
        np.savez_compressed(out, points=read_points(src).astype(np.float32))
        done += 1
        print(f"[conv] frame_{idx:03d} <- {os.path.basename(src)}  ({time.time()-t0:.1f}s)", flush=True)
    n_local = sum(1 for idx in range(a.first, a.last + 1, a.step)
                  if os.path.exists(os.path.join(a.out_dir, f"frame_{idx:03d}_full.npz")))
    print(f"[conv] converted/present={n_local}  cloud-only-skipped={skipped}  missing={missing}", flush=True)


if __name__ == "__main__":
    main()
