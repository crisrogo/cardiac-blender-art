# Tutorial — reproducing every figure

This walks through both projects step by step. Every render lands in `output/`.

Throughout, `blender` means the Blender 4.5 executable. On Windows you'll
usually need the full path, so either add it to your `PATH` or substitute it:

```powershell
# PowerShell: define it once per session
$blender = "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
```

All Blender commands follow the same shape — the part after `--` is passed to
the script:

```
blender --background --factory-startup --python <SCRIPT>.py -- <args>
```

`--background` = no GUI, `--factory-startup` = ignore your personal Blender
config. Renders are **CPU Cycles**; a 1024² preview is a minute or two, a 4096²
final is ~1–2 hours.

---

## Part A — HCM glass hearts

**Data:** `meshes/sciblend/HCM1.blend … HCM5.blend` (see `meshes/README.md`).

### A0. (optional) Check the anatomical orientation
Solid-colour QA renders, one per heart, to confirm each faces anterior, apex
down:

```
blender --background --factory-startup --python heart_orient_check.py
```
→ `output/heart_check_1.png … heart_check_5.png`

### A1. The baseline queue (the submitted style)
```
# fast preview (1024², 64 samples)
blender --background --factory-startup --python heart_contest_render.py -- test
```
→ `output/contest_test.png` — five glass hearts receding in a shallow-focus
queue, the front heart's LV carrying a glowing warm-white wireframe.

### A2. The six wireframe variants
```
blender --background --factory-startup --python heart_contest_render.py -- variants
```
→ `output/variant 1 … 6 *.png` (green / fire-red / white / no-ventricle / glow
wireframe treatments).

### A3. The alternative compositions
`heart_compositions.py` takes a composition name, plus optional flags
`test` (512²), `4k` (4096²), or `raw` (matte reference). Default is 1024².

```
blender --background --factory-startup --python heart_compositions.py -- vshape
blender --background --factory-startup --python heart_compositions.py -- vbow
blender --background --factory-startup --python heart_compositions.py -- vslope
blender --background --factory-startup --python heart_compositions.py -- rap
blender --background --factory-startup --python heart_compositions.py -- raphero
```
→ `output/composition - vshape.png`, `… - vbow.png`, `… - vslope.png`
(white background), `… - rap.png` (worm's-eye ring), `… - rap hero.png`
(worm's-eye close-up — the submitted piece).

### A4. A rotation sweep + contact sheet
To choose the hero's angle, render the close-up across a range, then stitch the
results into one labelled grid. The numeric argument is the swept angle:

```powershell
foreach ($a in -100,-80,-60,-40,-20,0,20,40,60,80,100) {
  & $blender --background --factory-startup --python heart_compositions.py -- raphero $a
}
python make_contact_sheet.py pitch    # also: yaw, roll (match what you swept)
```
→ `output/composition - rap hero pitch <a>.png` (the frames) and
`output/pitch contact sheet.png` (the grid).

### A5. The "raw" source-mesh reference (matte, no glass)
```
blender --background --factory-startup --python heart_compositions.py -- raphero raw
```
→ `output/raw - rap hero.png` — the same layout in plain matte materials
(useful as an "original image" for AI-use disclosure).

### A6. Final 4K + submission packaging
```
# 4K (4096², 512 samples, 8-bit RGB) — slow
blender --background --factory-startup --python heart_compositions.py -- raphero 4k
blender --background --factory-startup --python heart_contest_render.py -- final
```
→ `output/4k/composition - rap hero.png`,
`output/4k/queue - white wireframe.png`.

```
# finalize: flatten to opaque RGB, embed 300 dpi, report size
python finalize_4k.py "output/4k/composition - rap hero.png"

# if a PNG is over an upload limit, export a high-quality JPEG
python to_jpg.py "output/4k/composition - rap hero.png" 90 95 97
```

---

## Part B — the cardiac-cycle "beat"

**Data:** `meshes/pacemaker/transformed-0.vtk … transformed-10.vtk`
(one per cardiac-cycle phase; a missing frame is tolerated).

### B1. (optional) Inspect a mesh
```
python vtk_scan.py "meshes/pacemaker/transformed-0.vtk"
```
→ prints the VTK schema (points, polygons, the `elemTag` cell scalar).

### B2. Convert the meshes to a Blender-friendly format
```
python convert_vtk.py
```
→ `output/beat_npz/frame_00.npz … frame_10.npz` + `topo.npz`, and prints each
phase's centroid and bounding-box diagonal (you'll see it contract then relax).

### B3. (optional) Inspect structures + motion
```
python analyze_tags.py
```
→ per-structure cell/vertex counts, centroids, PCA long axis, and the peak
per-vertex displacement over the cycle.

### B4. Identify the structures (colour-coded)
```
blender --background --factory-startup --python beat_render.py -- tagmap test
```
→ `output/beat - tagmap.png` — each `elemTag` in a distinct colour (the script
hides the outer shell so the inner structures are visible).

### B5. The figures
```
# single phase, close-up (red/blue glass chambers + glowing inner architecture)
blender --background --factory-startup --python beat_render.py -- one

# "cardiac clock": the 10 phases as a ring of glass hearts
blender --background --factory-startup --python beat_render.py -- ring

# "one beat": all 10 phases overlaid as a luminous wireframe long-exposure
blender --background --factory-startup --python beat_render.py -- expo
```
→ `output/beat - one.png`, `output/beat - ring.png`, `output/beat - expo.png`.

Add `test` to any beat command for a fast 700², 48-sample preview, e.g.
`-- ring test`.

---

## Part C — the beating-heart video

**Data:** the HCM volumetric time series, one `.vtu` per timestep plus the case's
`.lon` fibre file. Unlike Parts A and B, **this input is not published** — it is
roughly 30 GB per case, too large to archive (see `meshes/README.md`). The steps
below are exact, but you will need an equivalent tetrahedral time series of your
own to follow them. This is a different pipeline from
Parts A and B — it lives in `beat_video/`, which has its own README with the full
reference (every env var, every material, the delivery encodes). This section is
the short path from meshes to the finished 20-second video.

Everything for one case lives in one directory; the default is
`output/beat_video/case1`, overridable with `BEAT_DIR`. Below, `<case>` is that
directory, `<ref.vtu>` is any one timestep and `<lon>` the fibre file.

### C1. Surface topology (once per case)
The node connectivity never changes, so the outer-surface triangulation is
extracted once and reused for every frame:

```
python beat_video/convert_vtu_surface.py topo <ref.vtu> <case>/topo.npz
```

### C2. Convert the timesteps
```
python beat_video/batch_convert_local.py <src_dir> <case> --prefix HCM1_532_ --first 0 --last 101
```
→ `<case>/frame_000_full.npz …` — the full deformed point array per timestep.
The renderer reads **only** `frame_*_full.npz`, because the cross-section needs
interior vertices that the surface subset does not contain.

If the source `.vtu` files are OneDrive cloud-only placeholders, hydrate them
first with `fetch_frames.py` (it overlaps the ~20 min-per-file downloads); see
`beat_video/README.md`.

### C3. Identify this case's valve tags
```
python beat_video/identify_tags.py <case>
```
→ a per-tag table. The valves are the tags whose barycentre sits between the
relevant chamber pair; you need mitral, tricuspid, aortic, pulmonary and the
LV endocardium. Case 1 gives `7, 8, 9, 10` and `25`, which are the defaults —
for any other case pass `VALVE_TAGS` / `LV_ENDO_TAG` to every render command.

### C4. Cross-section depths + fibres (needed by the `story` mode only)
```
python beat_video/extract_cut.py fastseries <ref.vtu> <case>/topo.npz <case> 12
python beat_video/add_fibres.py      <ref.vtu> <lon> <case>
python beat_video/make_streamlines.py <ref.vtu> <lon> <case> 3000
python beat_video/add_nv.py <case>
```
→ `topo_cut_00.npz … topo_cut_11.npz` (the progressive cut), `fibres.npz` (the
anisotropy direction) and `streamlines_*.npz` (the tracts, with the
nearest-vertex index that lets them follow the beat).

### C5. Check the orientation before rendering anything long
```
blender --background --factory-startup --python beat_video/render_beat_video.py -- turntable
```
→ `<case>/turntable_00_az180.png …`, 8 views 45° apart. Confirm the first one is
anterior, apex down. **Look at it** — the orientation is anatomical, not
self-checking, so this is the step that catches a wrong tag number.

### C6. Pick a material
```
blender --background --factory-startup --python beat_video/render_beat_video.py -- materials
```
→ `<case>/material_<key>.png` for every look in the library: `realistic_fresh`,
`realistic_fibres`, `wax`, `glass_ruby`, `porcelain`, `bronze`, `steampunk`,
`steampunk_flesh`, `hipct`, `fibres_debug`.

### C7. Render the story
```powershell
$env:MATERIAL="realistic_fresh"
$env:TRANSPARENT="1"      # RGBA frames, so the alpha deliverables are possible
& $blender --background --factory-startup --python beat_video/render_beat_video.py -- story
```
→ `<case>/story_realistic_fresh/f_0000.png … f_0599.png` (20 s at 30 fps).
Set `TEST=1` first for a 720², 16-sample rehearsal.

### C8. Encode
```
# opaque MP4
blender --background --factory-startup --python beat_video/encode_video.py -- <case>/story_realistic_fresh <case>/story_realistic_fresh.mp4 30

# alpha master + the two delivery formats (needs ffmpeg on PATH)
ffmpeg -framerate 30 -i <case>/story_realistic_fresh/f_%04d.png -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le <case>/story_realistic_fresh_alpha.mov
ffmpeg -i <case>/story_realistic_fresh_alpha.mov -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 30 -row-mt 1 -auto-alt-ref 0 <case>/story_realistic_fresh_alpha.webm
ffmpeg -i <case>/story_realistic_fresh_alpha.mov -filter_complex "color=white:s=1080x1080:r=30[bg];[bg][0:v]overlay=shortest=1,format=yuv420p" -c:v libx264 -crf 18 -preset medium <case>/story_realistic_fresh_white_1080.mp4
```
The ProRes `.mov` is the master (it is large — ~700 MB for 20 s); the WebM keeps
the transparency for slides and the web, and the white MP4 is the fallback for
players that ignore alpha.

### C9. (optional) The material comparison grid
```
python beat_video/grid_videos.py <case> 320
blender --background --factory-startup --python beat_video/encode_video.py -- <case>/grid_frames <case>/grid_materials.mp4 30
```
→ every `story_<material>/` sequence tiled into one labelled 4-column montage.

---

## Notes

- **Materials:** chambers are coloured glass (Principled BSDF, transmission);
  the "hero" structure is a glowing emissive wireframe; tone-mapping is AgX
  High-Contrast with a fog-glow bloom in the compositor.
- **Orientation** is derived from the mesh anatomy (Part A) or PCA (Part B) and
  baked into vertex coordinates, so it's stable across frames. Part C uses
  neither: PCA fails on a whole heart with atria and great vessels attached, so
  the video pipeline orients itself from the valve barycentres and the LV apex
  (`beat_video/orient.py`).
- **Engines:** Parts A and B are CPU Cycles. Part C defaults to EEVEE (fast
  enough for 600-frame sequences) and switches to Cycles for the looks that need
  real transmission or subsurface scattering.
- **Reproducibility:** Cycles + denoising is deterministic for a given Blender
  version; expect tiny differences across versions/CPUs.
