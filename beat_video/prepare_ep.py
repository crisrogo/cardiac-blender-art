"""
EP video, stage 1: map a reaction-eikonal activation-time sample onto a case's
outer surface and store it next to the beat-video data.

    python prepare_ep.py <HCMn_EP dir> <case_dir> <sample id>

<HCMn_EP dir> is one unpacked archive of the Zenodo EP record
(https://zenodo.org/records/21720235): activation_maps/<id>.dat holds one
activation time (ms) per mesh node, in the SAME node order as the mechanics
VTU, so it indexes frame_000_full.npz directly (-1 = never activated: vessels,
valve planes). inputs/json_files/<id>.json holds the sample's parameters and
tags_EP.json the region tags.

Writes <case_dir>/ep_<id>.npz:
    at        (n_surf,) float32  activation time per surface vertex (ms)
    region    (n_faces,) int8    0 = context (ghosted), 1 = atria, 2 = ventricles
    at_range  (2, 2)             [min, max] AT of the atria / ventricles faces
    params    json string        the sample's EP parameters
"""
import json
import os
import sys
import numpy as np


def main(ep_dir, case_dir, sample):
    topo = np.load(os.path.join(case_dir, "topo.npz"))
    faces, ftags, sv = topo["faces"], topo["face_tags"], topo["surf_vidx"]
    at_all = np.loadtxt(os.path.join(ep_dir, "activation_maps", f"{sample}.dat"))
    n_full = len(np.load(os.path.join(case_dir, "frame_000_full.npz"))["points"])
    if len(at_all) != n_full:
        raise SystemExit(f"{len(at_all)} activation times but {n_full} mesh nodes — wrong case?")
    at = at_all[sv].astype(np.float32)

    tags = json.load(open(os.path.join(ep_dir, "inputs", "json_files", "tags_EP.json")))
    atria = list(tags["atria"]) + [tags["BB"]]                         # Bachmann's bundle is atrial
    ventricles = [tags["LV"], tags["RV"]] + list(tags["fast_endo"])
    region = np.zeros(len(faces), np.int8)
    region[np.isin(ftags, atria)] = 1
    region[np.isin(ftags, ventricles)] = 2

    at_range = np.zeros((2, 2))
    for r in (1, 2):
        a = at[np.unique(faces[region == r])]
        a = a[a >= 0]
        at_range[r - 1] = a.min(), a.max()
    params = json.load(open(os.path.join(ep_dir, "inputs", "json_files", f"{sample}.json")))["EP"]

    out = os.path.join(case_dir, f"ep_{sample}.npz")
    np.savez(out, at=at, region=region, at_range=at_range, params=json.dumps(params))
    print(f"[ep] {out}: atria {at_range[0].round(1)} ms, ventricles {at_range[1].round(1)} ms, {params}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
