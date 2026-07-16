# Cardiac glass-heart renders (Blender)

Artistic, physically-based Blender renders of cardiac simulation meshes, built
for two projects:

1. **HCM glass hearts** — five hypertrophic-cardiomyopathy hearts as coloured
   glass, for the WCCM–ECCOMAS 2026 "Arts & Science" art competition
   (a receding queue, plus V / bow / uphill-slope / worm's-eye compositions and
   wireframe variants).
2. **The cardiac-cycle "beat"** — one heart across the 10 phases of the cardiac
   cycle (from a leadless-pacemaker collision study), rendered as a glass
   "cardiac clock" and as a single luminous "one-beat" long exposure.

> **Low-res examples included; full-res and meshes still pending.**
> Low-resolution versions of every figure and video the pipeline produces now
> live in [`examples/`](examples/) (see the gallery below), so you can see the
> expected end result. The full-resolution 4K contest renders and the input
> meshes are **not** included yet: they will be added once the associated papers
> are published. The scripts and this tutorial are everything you need to
> reproduce every figure once you drop the meshes in
> (see [`meshes/README.md`](meshes/README.md)).

All of this code was written with **Claude (Claude Code)**; the human directed
the artistic decisions and the iteration.

---

## Gallery

Low-res previews of the expected output. Full listing, with the exact command
behind each figure, is in [`examples/README.md`](examples/README.md).

**HCM glass hearts** (art competition):

<p>
  <img src="examples/hcm-glass/queue-white-wireframe.png" width="180" alt="Receding queue of five glass hearts with a white wireframe overlay">
  <img src="examples/hcm-glass/vshape.png" width="180" alt="V / chevron composition">
  <img src="examples/hcm-glass/vbow.png" width="180" alt="Inverted-U bow / arch composition">
  <img src="examples/hcm-glass/vslope.png" width="180" alt="Hearts on an uphill slope">
  <img src="examples/hcm-glass/rap-hero.png" width="180" alt="Worm's-eye hero close-up">
</p>

**Cardiac-cycle beat** (stills, plus beating-heart videos in
[`examples/beat-video/`](examples/beat-video/)):

<p>
  <img src="examples/beat-stills/tagmap.png" width="180" alt="Anatomy tag map">
  <img src="examples/beat-stills/one.png" width="180" alt="Single-beat luminous long exposure">
  <img src="examples/beat-stills/ring.png" width="180" alt="Cardiac clock: 10 phases in a ring">
  <img src="examples/beat-stills/expo.png" width="180" alt="Long-exposure composite">
</p>

---

## Requirements

- **Blender 4.5** (Cycles renderer; CPU is fine). The `blender` executable must
  be runnable from a terminal — on Windows that is typically
  `"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"`.
- **Python 3.10+** for the small helper/utility scripts, with:
  ```
  pip install -r requirements.txt    # numpy, Pillow, pypdf
  ```
  (Blender ships its own Python with numpy, so the Blender scripts don't need a
  separate install.)
- Developed and tested on **Windows**; the in-script paths use `\` separators.

## Layout

```
.
├── heart_contest_render.py   # HCM: baseline queue, 6 wireframe variants, 4K final
├── heart_compositions.py     # HCM: V / bow / uphill-slope / worm's-eye + raw + 4K
├── heart_orient_check.py     # HCM: solid-colour orientation QA
├── beat_render.py            # Beat: tagmap / one / ring / expo
├── convert_vtk.py            # Beat: transformed-*.vtk  ->  .npz
├── analyze_tags.py           # Beat: per-structure anatomy + motion stats
├── vtk_scan.py               # util: print a VTK file's schema
├── make_contact_sheet.py     # util: stitch a yaw/roll/pitch sweep into one grid
├── finalize_4k.py            # util: flatten to RGB, embed 300 dpi, report size
├── to_jpg.py                 # util: high-quality PNG -> JPEG (for upload limits)
├── beat_video/               # Beat: full beating-heart video pipeline (own README)
├── examples/                 # low-res previews of every figure + video (tracked)
├── meshes/                   # <- put input meshes here (gitignored)
└── output/                   # <- renders land here (gitignored)
```

## Configuration (paths)

Scripts default to repo-relative `meshes/` and `output/` folders, overridable
with environment variables:

| Variable        | Default                     | Used by |
|-----------------|-----------------------------|---------|
| `SCIBLEND_DIR`  | `./meshes/sciblend`         | HCM scripts (the `.blend` files) |
| `VTK_DIR`       | `./meshes/pacemaker`        | `convert_vtk.py` (the `.vtk` files) |
| `OUT_DIR`       | `./output`                  | all render scripts |
| `NPZ_DIR`       | `./output/beat_npz`         | `convert_vtk.py`, `beat_render.py` |

## Quick start

```bash
# (once) install the helper deps
pip install -r requirements.txt

# drop meshes into meshes/sciblend and meshes/pacemaker  (see meshes/README.md)

# a fast HCM preview:
blender --background --factory-startup --python heart_compositions.py -- vshape test

# a beat figure (needs the .vtk -> .npz conversion first):
python  convert_vtk.py
blender --background --factory-startup --python beat_render.py -- ring
```

**Step-by-step instructions to reproduce every figure are in
[`TUTORIAL.md`](TUTORIAL.md).**
