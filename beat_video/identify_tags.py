"""
Print a per-tag anatomy table for a converted case, to identify which elemTags
are the valves and the LV endocardium (needed by the orientation in
render_beat_video.py). Run after topo.npz + frame_00.npz exist.

    python identify_tags.py <case_dir>

Chambers/vessels are fixed by the simulation convention (also in the repo
README): 1=LV, 2=RV, 3=LA, 4=RA, 5=aorta, 6=PA. The remaining tags are finer
structures (valves, veins, endocardial surfaces); identify valves as the tags
whose barycentre sits at the junction of the relevant chamber pair.

Case 1 (HCM1_532) result, used as the defaults in render_beat_video.py:
    mitral=7 (LV-LA), tricuspid=8 (RV-RA), aortic=9 (aorta root),
    pulmonary=10 (PA root), LV-endocardium=25.
Re-run this per case before rendering — the numbering may differ.
"""
import os
import sys
import numpy as np

CHAMBERS = {1: "LV", 2: "RV", 3: "LA", 4: "RA", 5: "Ao", 6: "PA"}


def main(case_dir):
    P = np.load(os.path.join(case_dir, "frame_00.npz"))["points"].astype(np.float64)
    topo = np.load(os.path.join(case_dir, "topo.npz"))
    F, T = topo["faces"], topo["face_tags"]

    def verts(tg):
        return np.unique(F[T == tg])

    ch = {nm: P[verts(t)].mean(0) for t, nm in CHAMBERS.items() if (T == t).any()}
    print("tag | nface | nvert |     centroid (mm)      | nearest 2 chambers (mm)")
    for tg in sorted(np.unique(T)):
        fv = verts(tg); c = P[fv].mean(0)
        near = sorted((np.linalg.norm(c - cc) / 1000, nm) for nm, cc in ch.items())
        near_s = ", ".join(f"{nm}:{d:.0f}" for d, nm in near[:2])
        print(f"{tg:3d} | {int((T==tg).sum()):5d} | {len(fv):5d} | {np.round(c/1000,1)} | {near_s}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
