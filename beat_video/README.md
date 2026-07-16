# HCM beating-heart video

A **separate visualisation** from the glass-art stills in the repo root: a
professional **beating-heart video** built from the HCM volumetric simulation
time series (`videos_HCM/<case>/HCM*_*.vtu`). Kept in its own directory for
reproducibility.

> **Ground-truth rule.** The user's visual inspection is authoritative. The
> scripts/agent do **not** decide whether the orientation, the anterior face, or
> the look are correct — always render, show the user, and **wait for an explicit
> green light** before moving on.

## The data
- One `.vtu` per timestep, **~300 MB**, **volumetric tetrahedral** (~0.75 M pts,
  ~3.9 M tets). Point `displacement`, cell `elemTags`, cell `fibres`. Units are
  micrometres.
- `elemTags`: `1`=LV, `2`=RV, `3`=LA, `4`=RA, `5`=aorta, `6`=PA; higher tags are
  valves / veins / endocardial surfaces (case-specific — see `identify_tags.py`).
- Source files are usually **OneDrive cloud-only placeholders**. Only a single
  buffered whole-file Python `open().read()` hydrates them reliably; `cp`/`head`
  fail with "permission denied" and chunked/`buffering=0` reads raise `OSError 22`.
  Hydration is the bottleneck (~20 min per file).

## Pipeline
```
# 0. build surface topology ONCE from any one (local) frame
python convert_vtu_surface.py topo  <ref.vtu>  <out>/topo.npz

# 1. hydrate + convert the chosen timesteps to surface npz (overlapped downloads)
python fetch_frames.py  <src_dir> <out> <out>/topo.npz --indices 0,11,23,34,45,57,68,80,91,102 --prefix HCM1_532_

# 2. (re)identify valve / LV-endo tags for this case
python identify_tags.py <out>

# 3. render with Blender 4.5  (turntable to choose the anterior start, then video)
blender --background --factory-startup --python render_beat_video.py -- turntable
blender --background --factory-startup --python render_beat_video.py -- video
```

## Orientation — **no PCA**
PCA was tried and **failed**: with the atria and great vessels attached, the
heart's max-variance axis is not the anatomical apex-base axis. Orientation is
instead anatomical (`render_beat_video.py`):
- valve barycentres (mitral/tricuspid/aortic/pulmonary) define the basal plane;
- the **apex** is the LV-endocardium point farthest from the **mitral** barycentre;
- **up** (apex-down) runs from that apex to the valve-plane centroid;
- the valve plane + pulmonary-valve position set the **anterior**, which is
  pointed at the starting camera. The camera then orbits 360° while it beats.

Defaults are for **case 1** (`mitral=7, tricuspid=8, aortic=9, pulmonary=10,
LV-endo=25`); override per case via the `VALVE_TAGS` / `LV_ENDO_TAG` env vars.
