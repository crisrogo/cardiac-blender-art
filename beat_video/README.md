# HCM beating-heart video

A **separate visualisation** from the glass-art stills in the repo root: a
**beating-heart video** built from the HCM volumetric simulation time series
(`videos_HCM/<case>/HCM*_*.vtu`). Kept in its own directory for reproducibility.

The finished piece (the `story` mode) is a 20-second choreographed shot: the
heart appears, its myofibre tracts light up, the camera orbits 360°, the fibres
fade as the heart starts beating, then the heart is progressively cut open on the
anterior plane and the beating cross-section is held. Eight material looks are
available; low-res examples of all of them are in
[`../examples/beat-video/`](../examples/beat-video/).

> **Ground-truth rule.** The user's visual inspection is authoritative. The
> scripts/agent do **not** decide whether the orientation, the anterior face, or
> the look are correct — always render, show the user, and **wait for an explicit
> green light** before moving on.

## The data

**The time series this pipeline consumes is not published** — ~300 MB per
timestep and ~100 timesteps per case is too large to archive, and it is not part
of the repo's Zenodo record (which covers the still-figure meshes only; see
[`../meshes/README.md`](../meshes/README.md)). Nothing here is specific to those
files, though: any tetrahedral time series with the structure below runs through
the pipeline unchanged, and the tag numbers it depends on are discovered per case
by `identify_tags.py` rather than hard-coded.

- One `.vtu` per timestep, **~300 MB**, **volumetric tetrahedral** (~0.75 M pts,
  ~3.9 M tets). Point `displacement`, cell `elemTags`, cell `fibres`. Units are
  micrometres.
- One `.lon` per case: the openCARP fibre file, one row per tetrahedron in the
  same order as the VTU (used for the fibre anisotropy and the fibre tracts).
- `elemTags`: `1`=LV, `2`=RV, `3`=LA, `4`=RA, `5`=aorta, `6`=PA; higher tags are
  valves / veins / endocardial surfaces (case-specific — see `identify_tags.py`).
- If the source files are **OneDrive cloud-only placeholders**, only a single
  buffered whole-file Python `open().read()` hydrates them reliably; `cp`/`head`
  fail with "permission denied" and chunked/`buffering=0` reads raise `OSError 22`.
  Hydration is the bottleneck (~20 min per file), which is why `fetch_frames.py`
  overlaps the downloads.

Everything the renderer reads lives in one **case directory** (default
`../output/beat_video/case1`, override with `BEAT_DIR`):

| File | Written by | What it is |
|------|-----------|------------|
| `topo.npz` | `convert_vtu_surface.py topo` | outer-surface triangulation + per-face tags + `surf_vidx` (constant across time) |
| `frame_NNN_full.npz` | `batch_convert_local.py` / `extract_cut.py full` | **full** deformed point array per timestep — what the renderer loads |
| `frame_NN.npz` | `fetch_frames.py` | surface-subset points only (lighter; enough for `identify_tags.py`, **not** read by the renderer) |
| `topo_cut_NN.npz` | `extract_cut.py fastseries` | progressive cross-section depths, shallowest → half |
| `topo_cut.npz` | `extract_cut.py cut` | the single half-depth cross-section |
| `fibres.npz` | `add_fibres.py` | per-vertex myofibre direction, sampled for the surface and the cut |
| `streamlines_{ventricles,atria,all}.npz` | `make_streamlines.py` + `add_nv.py` | fibre tracts as polylines, plus the nearest-heart-vertex index that makes them beat |

## Pipeline

```bash
# 0. build the surface topology ONCE from any one (local) frame
python convert_vtu_surface.py topo <ref.vtu> <case>/topo.npz

# 1a. frames — sources already downloaded locally (writes frame_NNN_full.npz)
python batch_convert_local.py <src_dir> <case> --prefix HCM1_532_ --first 0 --last 101

# 1b. frames — sources are OneDrive placeholders (hydrates + writes surface frame_NN.npz)
python fetch_frames.py <src_dir> <case> <case>/topo.npz --indices 0,11,23,34,45,57,68,80,91,102 --prefix HCM1_532_

# 2. (re)identify this case's valve / LV-endo tags -> VALVE_TAGS, LV_ENDO_TAG
python identify_tags.py <case>

# 3. progressive cross-section depths for the cut (12 is plenty for a 3.5 s cut)
python extract_cut.py fastseries <ref.vtu> <case>/topo.npz <case> 12

# 4. fibres: per-vertex direction (anisotropy) + tracts (tubes), then make them beat
python add_fibres.py <ref.vtu> <lon> <case>
python make_streamlines.py <ref.vtu> <lon> <case> 3000
python add_nv.py <case>

# 5. render with Blender 4.5 — check the anterior start, then the 20 s story
blender --background --factory-startup --python render_beat_video.py -- turntable
blender --background --factory-startup --python render_beat_video.py -- story

# 6. encode the frames to MP4
blender --background --factory-startup --python encode_video.py -- <case>/story_realistic_fresh <case>/story_realistic_fresh.mp4 30
```

`batch_convert_local.py` is the route the finished videos used: the renderer only
reads `frame_*_full.npz`, so a case converted with `fetch_frames.py` alone has to
be topped up with `extract_cut.py full` per frame before it will render.

The `story` mode needs steps 3 and 4 — it will fail without the cut depths, and
renders without the fibre tracts if `streamlines_all.npz` is missing. A plain
orbit (`video` mode) needs nothing beyond steps 0–2.

## Render modes

```
blender --background --factory-startup --python render_beat_video.py -- <mode> [args]
```

| Mode | Output | What it does |
|------|--------|--------------|
| `turntable` | `turntable_KK_azNNN.png` | 8 views 45° apart — use it to confirm the anatomical anterior start |
| `still [az] [frame]` | `still_azNNN_fNN.png` | one frame at one azimuth |
| `materials` | `material_<key>.png` | the same frame in every material in the library |
| `cut_still` | `cut_still_<material>.png` | one frame of the cross-section (needs `topo_cut.npz`) |
| `story` | `story_<material>/f_NNNN.png` | the 20 s choreographed sequence (600 frames @ 30 fps) |
| `video` | `frames_video/f_NNNN.png` | plain 360° orbit while beating (`ORBIT_SECONDS` × `FPS` frames) |

The `story` timeline, in seconds: appear 0.6 → fibres in 1.4 → orbit 6.0 →
fibres out 2.0 (the beat starts here) → beat 2.5 → progressive cut 3.5 → hold 4.0.
The beat continues through the cut, so the cross-section keeps beating to the end.

## Materials

`MATERIAL=` one of `realistic_fresh` (default), `realistic_fibres`, `wax`,
`glass_ruby`, `porcelain`, `bronze`, `steampunk`, `steampunk_flesh`, `hipct`,
`fibres_debug`. Four extra keys re-tag the mesh instead of just re-shading it:
`anatomy` (left heart red / right heart blue / rest ghosted), `anatomy_jewel`
(ruby + sapphire glass), `chamber_porcelain` (one chamber in porcelain, set by
`HIGHLIGHT_TAG`), and `wire_red_nolv` / `wire_gold_red_nolv` (LV solid removed,
leaving a glowing LV wireframe).

`glass_ruby` needs Cycles for real transmission, and `STYLE=hipct` forces Cycles
because the HiP-CT look depends on subsurface scattering.

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `BEAT_DIR` | `../output/beat_video/case1` | case directory (topo + frames + cuts + fibres) |
| `OUT_DIR` | `= BEAT_DIR` | where renders are written |
| `MATERIAL` | `realistic_fresh` | material key (see above) |
| `ENGINE` | `EEVEE` | `EEVEE` or `CYCLES` |
| `STYLE` | `studio` | `studio` softboxes, or `hipct` chiaroscuro + telephoto/DoF (forces Cycles) |
| `START_AZ` | `180` | starting azimuth; 180 = anatomical anterior toward the camera |
| `VALVE_TAGS` | `7,8,9,10` | mitral, tricuspid, aortic, pulmonary tags for this case |
| `LV_ENDO_TAG` | `25` | LV-endocardium tag for this case |
| `RES` / `SAMPLES` | `1080` / `64` | resolution and samples (`TEST=1` → 720 / 16) |
| `FPS` | `30` | frame rate of the rendered sequence |
| `ORBIT_SECONDS` / `BEATS` | `12` / `10` | `video` mode length and number of beats |
| `BEAT_PERIOD` | `0.9` | `story` mode seconds per beat |
| `TRANSPARENT` | `0` | `1` → alpha background (RGBA PNGs, needed for the alpha deliverables) |
| `CUT_DEPTH` | — | pick `topo_cut_NN.npz` instead of the half cut, for `cut_still` |
| `MAX_FRAMES` | `0` | cap frames loaded (still modes only need one) |
| `LIGHT_SCALE` | `1.0` | multiplies every light |
| `HIGHLIGHT_TAG` | `1` | chamber highlighted by `MATERIAL=chamber_porcelain` |
| `CYCLES_GPU` | `0` | `1` force-tries a GPU backend (this install falls back to CPU) |

## Delivery encodes

`encode_video.py` only makes the opaque MP4 — Blender's FFMPEG output has no
RGBA mode. The transparent deliverables are made with ffmpeg from an
alpha-rendered sequence (`TRANSPARENT=1`, so the PNGs are RGBA):

```bash
# alpha master: ProRes 4444 .mov (keep this one, it is the master)
ffmpeg -framerate 30 -i story_realistic_fresh/f_%04d.png \
       -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le story_realistic_fresh_alpha.mov

# web/PowerPoint delivery: VP9 WebM WITH alpha
ffmpeg -i story_realistic_fresh_alpha.mov -c:v libvpx-vp9 -pix_fmt yuva420p \
       -b:v 0 -crf 30 -row-mt 1 -auto-alt-ref 0 story_realistic_fresh_alpha.webm

# fallback for players that ignore alpha: flattened onto white
ffmpeg -i story_realistic_fresh_alpha.mov \
       -filter_complex "color=white:s=1080x1080:r=30[bg];[bg][0:v]overlay=shortest=1,format=yuv420p" \
       -c:v libx264 -crf 18 -preset medium story_realistic_fresh_white_1080.mp4
```

The side-by-side material comparison is a montage of the story frame sequences,
encoded like any other frame directory:

```bash
python grid_videos.py <case> 320
blender --background --factory-startup --python encode_video.py -- <case>/grid_frames <case>/grid_materials.mp4 30
```

## Orientation — **no PCA**

PCA was tried and **failed**: with the atria and great vessels attached, the
heart's max-variance axis is not the anatomical apex-base axis. Orientation is
instead anatomical (`orient.py`, shared by the renderer and the cross-section
extractor so their world frames agree exactly):

- valve barycentres (mitral/tricuspid/aortic/pulmonary) define the basal plane;
- the **apex** is the LV-endocardium point farthest from the **mitral** barycentre;
- **up** (apex-down) runs from that apex to the valve-plane centroid;
- the valve plane + pulmonary-valve position set the **anterior**, which is
  pointed at the starting camera. The camera then orbits 360° while it beats.

World axes are X=right, Y=anterior, Z=up. Defaults are for **case 1**
(`mitral=7, tricuspid=8, aortic=9, pulmonary=10, LV-endo=25`); re-run
`identify_tags.py` per case and override with `VALVE_TAGS` / `LV_ENDO_TAG`.

## Other scripts

- `render_streamlines.py` — standalone fibre-tract stills (glowing tubes over a
  ghosted heart):
  `blender ... --python render_streamlines.py -- <anterior|posterior|roof> <ventricles|atria|all> [every] [radius]`
- `convert_vtu_surface.py points <frame.vtu> <out.npz> <topo.npz>` — convert a
  single frame to the surface-subset format.
- `orient.py` — the shared orientation, imported by the others (not run directly).
