# Cardiac glass-heart renders (Blender)

Artistic, physically-based Blender renders of cardiac simulation meshes, built
for three projects:

1. **HCM glass hearts** — five hypertrophic-cardiomyopathy hearts as coloured
   glass, for the WCCM–ECCOMAS 2026 "Arts & Science" art competition
   (a receding queue, plus V / bow / uphill-slope / worm's-eye compositions and
   wireframe variants).
2. **The cardiac-cycle "beat"** — one heart across the 10 phases of the cardiac
   cycle (from a leadless-pacemaker collision study), rendered as a glass
   "cardiac clock" and as a single luminous "one-beat" long exposure.
3. **The beating-heart video** — the HCM volumetric time series as a 20-second
   choreographed shot: the fibre tracts light up, the camera orbits, the heart
   beats, then it is cut open and the beating cross-section is held. Eight
   material looks, rendered for all five cases.
4. **The electrical activation video** — the end-diastolic heart with the
   reaction-eikonal activation wave spreading over it (atria, then the
   ventricles after the AV delay), as a travelling front or a CARTO-style
   activation map, either on the static end-diastolic heart or together with its
   contraction, plus an artificially arrhythmic version.

> **Meshes are on Zenodo; low-res examples are in this repo.**
> The meshes behind projects 1 and 2 are archived on Zenodo — see
> [`meshes/README.md`](meshes/README.md) for the DOI, the expected layout and the
> tag conventions. The volumetric time series behind project 3 is ~30 GB per case
> and is **not** published, so that pipeline can be re-run on equivalent data but
> not on ours. The activation times behind project 4 are published in their own
> [Zenodo record](https://zenodo.org/records/21720235); its geometry is that same
> unpublished series. Low-resolution versions of every figure and video the pipeline
> produces live in [`examples/`](examples/) (gallery below), so you can see the
> expected end result before rendering your own. The full-resolution 4K contest
> renders and the 1080² videos are not tracked here — they are what the scripts
> produce once you drop the meshes in.

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

**JMCC cover art** (five hearts on a glowing floor):

<p>
  <img src="examples/cover/arc-femesh.png" width="180" alt="Five hearts standing on a green finite-element mesh floor">
  <img src="examples/cover/vshape-femesh.png" width="180" alt="V composition over the mesh floor, hero heart in wireframe">
  <img src="examples/cover/arc-grid.png" width="180" alt="Arc of five hearts on a square Tron grid, seen from 55 degrees">
  <img src="examples/cover/tree-grid.png" width="180" alt="Hearts on the grid with the glowing cluster tree drawn between them">
  <img src="examples/cover/mirror-grid.png" width="180" alt="Single heart above its coarse mesh reflection">
</p>

**Cardiac-cycle beat** (stills):

<p>
  <img src="examples/beat-stills/tagmap.png" width="180" alt="Anatomy tag map">
  <img src="examples/beat-stills/one.png" width="180" alt="Single-beat luminous long exposure">
  <img src="examples/beat-stills/ring.png" width="180" alt="Cardiac clock: 10 phases in a ring">
  <img src="examples/beat-stills/expo.png" width="180" alt="Long-exposure composite">
</p>

### Beating-heart video

The finished 20-second shot, in fresh-tissue and wax:

<table>
  <tr>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/beat-video/story-realistic-fresh.mp4" controls loop muted width="100%"></video>
    </td>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/beat-video/story-wax.mp4" controls loop muted width="100%"></video>
    </td>
  </tr>
  <tr>
    <td align="center"><a href="examples/beat-video/story-realistic-fresh.mp4">realistic fresh tissue</a></td>
    <td align="center"><a href="examples/beat-video/story-wax.mp4">wax</a></td>
  </tr>
</table>

All eight materials side by side:

<video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/beat-video/grid-materials.mp4" controls loop muted width="100%"></video>

[`examples/beat-video/grid-materials.mp4`](examples/beat-video/grid-materials.mp4)

The other six looks:
[fibres](examples/beat-video/story-realistic-fibres.mp4) ·
[ruby glass](examples/beat-video/story-glass-ruby.mp4) ·
[porcelain](examples/beat-video/story-porcelain.mp4) ·
[bronze](examples/beat-video/story-bronze.mp4) ·
[steampunk](examples/beat-video/story-steampunk.mp4) ·
[HiP-CT](examples/beat-video/story-hipct.mp4)

*(The players above stream the copies committed to this repo. If your viewer does
not play them inline, the links open the same files directly. These are 540²
previews; the pipeline renders 1080² and also produces alpha-channel versions —
see [Delivery encodes](beat_video/README.md#delivery-encodes).)*

### Electrical activation video

Activation **and contraction** on the beating heart, HCM1 and HCM3 (2× slow, the
pause between beats shortened):

<table>
  <tr>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/ep-video/ep-mech-hcm1.mp4" controls loop muted width="100%"></video>
    </td>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/ep-video/ep-mech-hcm3.mp4" controls loop muted width="100%"></video>
    </td>
  </tr>
  <tr>
    <td align="center"><a href="examples/ep-video/ep-mech-hcm1.mp4">HCM1, cycle 532</a> (<a href="examples/ep-video/ep-mech-hcm1-slow7.mp4">7× slow</a>)</td>
    <td align="center"><a href="examples/ep-video/ep-mech-hcm3.mp4">HCM3, cycle 237</a></td>
  </tr>
</table>

An **artificial arrhythmia**, randomised for the look rather than simulated: fast
contractions and fast electrical waves on independent schedules:

<table>
  <tr>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/ep-video/ep-arrhythmia-hcm1.mp4" controls loop muted width="100%"></video>
    </td>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/ep-video/ep-arrhythmia-hcm3.mp4" controls loop muted width="100%"></video>
    </td>
  </tr>
  <tr>
    <td align="center"><a href="examples/ep-video/ep-arrhythmia-hcm1.mp4">HCM1, cycle 532</a></td>
    <td align="center"><a href="examples/ep-video/ep-arrhythmia-hcm3.mp4">HCM3, cycle 237</a></td>
  </tr>
</table>

The wave alone on the static end-diastolic heart (5× slow, real 800 ms cycle), and the annotated CARTO map:

<table>
  <tr>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/ep-video/ep-wave-hcm1.mp4" controls loop muted width="100%"></video>
    </td>
    <td width="50%">
      <video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/ep-video/ep-wave-hcm3.mp4" controls loop muted width="100%"></video>
    </td>
  </tr>
  <tr>
    <td align="center"><a href="examples/ep-video/ep-wave-hcm1.mp4">HCM1</a></td>
    <td align="center"><a href="examples/ep-video/ep-wave-hcm3.mp4">HCM3</a></td>
  </tr>
</table>

<video src="https://github.com/crisrogo/cardiac-blender-art/raw/main/examples/ep-video/ep-map-overlays-hcm1.mp4" controls loop muted width="100%"></video>

[`examples/ep-video/ep-map-overlays-hcm1.mp4`](examples/ep-video/ep-map-overlays-hcm1.mp4) ·
every look side by side: [`examples/ep-video/looks.png`](examples/ep-video/looks.png)

<img src="examples/ep-video/looks.png" width="100%" alt="The two EP styles (wave, map) in three finishes, on black and on white">

---

## Requirements

- **Blender 4.5** (Cycles and EEVEE; CPU is fine). The `blender` executable must
  be runnable from a terminal — on Windows that is typically
  `"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"`.
- **Python 3.10+** for the helper/conversion scripts, with:
  ```
  pip install -r requirements.txt    # numpy, Pillow, pypdf, meshio, scipy
  ```
  (Blender ships its own Python with numpy, so the Blender scripts don't need a
  separate install. `meshio` and `scipy` are only needed by `beat_video/`.)
- **ffmpeg** on `PATH`, for the transparent/alpha video deliverables only.
  Blender's bundled ffmpeg handles the plain MP4s.
- Developed and tested on **Windows**; the in-script paths use `\` separators.

## Layout

```
.
├── heart_contest_render.py   # HCM: baseline queue, 6 wireframe variants, 4K final
├── heart_compositions.py     # HCM: V / bow / uphill-slope / worm's-eye + raw + 4K
├── heart_orient_check.py     # HCM: solid-colour orientation QA
├── cover_render.py           # Cover: five HCM glass hearts over a grid / FE-mesh floor
├── sweep_cover.sh            # Cover: low-res sweep of every cover concept
├── beat_render.py            # Beat: tagmap / one / ring / expo
├── convert_vtk.py            # Beat: transformed-*.vtk  ->  .npz
├── analyze_tags.py           # Beat: per-structure anatomy + motion stats
├── vtk_scan.py               # util: print a VTK file's schema
├── make_contact_sheet.py     # util: stitch a yaw/roll/pitch sweep into one grid
├── finalize_4k.py            # util: flatten to RGB, embed 300 dpi, report size
├── finalize_cover.py         # util: tag the dpi that declares 19.7 cm (JMCC cover spec)
├── to_jpg.py                 # util: high-quality PNG -> JPEG (for upload limits)
├── beat_video/               # Videos: beating heart + electrical activation (own README)
├── examples/                 # low-res previews of every figure + video (tracked)
├── meshes/                   # <- put input meshes here (gitignored; see Zenodo)
└── output/                   # <- renders land here (gitignored)
```

`beat_video/` is the video pipeline end to end — VTU conversion, anatomical
orientation, cross-section extraction, fibre tracts, the Blender renderer and the
encodes. It has [its own README](beat_video/README.md) with every stage, mode and
environment variable.

## Configuration (paths)

Scripts default to repo-relative `meshes/` and `output/` folders, overridable
with environment variables:

| Variable        | Default                     | Used by |
|-----------------|-----------------------------|---------|
| `SCIBLEND_DIR`  | `./meshes/sciblend`         | HCM scripts (the `.blend` files) |
| `VTK_DIR`       | `./meshes/pacemaker`        | `convert_vtk.py` (the `.vtk` files) |
| `OUT_DIR`       | `./output`                  | all render scripts |
| `NPZ_DIR`       | `./output/beat_npz`         | `convert_vtk.py`, `beat_render.py` |
| `BEAT_DIR`      | `./output/beat_video/case1` | `beat_video/` (converted frames + topology) |

## Quick start

```bash
# (once) install the helper deps
pip install -r requirements.txt

# get the meshes from Zenodo and unpack them into meshes/  (see meshes/README.md)

# a fast HCM preview:
blender --background --factory-startup --python heart_compositions.py -- vshape test

# a beat figure (needs the .vtk -> .npz conversion first):
python  convert_vtk.py
blender --background --factory-startup --python beat_render.py -- ring

# the beating-heart video (after converting a case — see TUTORIAL.md Part C):
blender --background --factory-startup --python beat_video/render_beat_video.py -- story

# the electrical activation video (activation times from Zenodo record 21720235):
python  beat_video/prepare_ep.py <unpacked HCM1_EP> output/beat_video/case1 74
blender --background --factory-startup --python beat_video/render_ep_video.py -- beat
python  beat_video/compose_ep_video.py output/beat_video/case1/ep_74/map_matte white ep.mp4

# a cover render: five hearts on the finite-element mesh floor
blender --background --factory-startup --python cover_render.py -- arc floor=femesh test
```

**Step-by-step instructions to reproduce every figure and video are in
[`TUTORIAL.md`](TUTORIAL.md)** (Part A: glass hearts, Part B: beat stills,
Part C: the video, Part D: the activation video).
