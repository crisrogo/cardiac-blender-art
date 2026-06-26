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

## Notes

- **Materials:** chambers are coloured glass (Principled BSDF, transmission);
  the "hero" structure is a glowing emissive wireframe; tone-mapping is AgX
  High-Contrast with a fog-glow bloom in the compositor.
- **Orientation** is derived from the mesh anatomy (HCM) or PCA (beat) and baked
  into vertex coordinates, so it's stable across frames.
- **Reproducibility:** Cycles + denoising is deterministic for a given Blender
  version; expect tiny differences across versions/CPUs.
