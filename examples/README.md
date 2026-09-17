# Example outputs (low-res)

These are low-resolution versions of the figures and videos the pipeline
produces, included so you can see the expected end result before you render your
own. The full-resolution 4K contest submissions and the 1080² videos are not
included here.

The still figures below are reproducible from the scripts in this repo once you
have the meshes from Zenodo (see [`../meshes/README.md`](../meshes/README.md));
the command that produces each one is listed. The commands for the videos are
just as exact, but their input time series is far too large to archive and is not
published, so those can only be re-run on equivalent data of your own.

## HCM glass hearts (art competition)

Five hypertrophic-cardiomyopathy hearts rendered as coloured glass, for the
WCCM-ECCOMAS 2026 "Arts & Science" competition.

| Figure | Script | Command |
|--------|--------|---------|
| [`hcm-glass/queue-white-wireframe.png`](hcm-glass/queue-white-wireframe.png) | `heart_contest_render.py` | `blender --background --factory-startup --python heart_contest_render.py -- final` |
| [`hcm-glass/vshape.png`](hcm-glass/vshape.png) | `heart_compositions.py` | `blender ... --python heart_compositions.py -- vshape` |
| [`hcm-glass/vbow.png`](hcm-glass/vbow.png) | `heart_compositions.py` | `blender ... --python heart_compositions.py -- vbow` |
| [`hcm-glass/vslope.png`](hcm-glass/vslope.png) | `heart_compositions.py` | `blender ... --python heart_compositions.py -- vslope` |
| [`hcm-glass/rap-hero.png`](hcm-glass/rap-hero.png) | `heart_compositions.py` | `blender ... --python heart_compositions.py -- raphero` |

## JMCC cover art

The same five HCM hearts staged over a "digital world" floor, for a journal
cover. `floor=femesh` is a jittered triangulated plane shaded with a wireframe
node — the ground reads as a finite-element mesh; `floor=grid` is the regular
square-cell version. Every render is square, and `finalize_cover.py` tags the
4K version with the dpi that declares 19.7 cm.

| Figure | Script | Command |
|--------|--------|---------|
| [`cover/arc-femesh.png`](cover/arc-femesh.png) | `cover_render.py` | `blender ... --python cover_render.py -- arc floor=femesh` |
| [`cover/vshape-femesh.png`](cover/vshape-femesh.png) | `cover_render.py` | `blender ... --python cover_render.py -- vshape floor=femesh` |
| [`cover/arc-grid.png`](cover/arc-grid.png) | `cover_render.py` | `blender ... --python cover_render.py -- arc floor=grid elev=55` |
| [`cover/tree-grid.png`](cover/tree-grid.png) | `cover_render.py` | `blender ... --python cover_render.py -- tree floor=grid elev=35` |
| [`cover/mirror-grid.png`](cover/mirror-grid.png) | `cover_render.py` | `blender ... --python cover_render.py -- mirror floor=grid` |

These are the 1024² `preview` renders. Add `4k` to the command for the 4096²
submission version, or `test` for a fast 512² check; `./sweep_cover.sh test`
renders the concepts side by side.

## Cardiac-cycle "beat" stills

One heart across the 10 phases of the cardiac cycle, from a leadless-pacemaker
collision study.

| Figure | Script | Command |
|--------|--------|---------|
| [`beat-stills/tagmap.png`](beat-stills/tagmap.png) | `beat_render.py` | `blender ... --python beat_render.py -- tagmap` |
| [`beat-stills/one.png`](beat-stills/one.png) | `beat_render.py` | `blender ... --python beat_render.py -- one` |
| [`beat-stills/ring.png`](beat-stills/ring.png) | `beat_render.py` | `blender ... --python beat_render.py -- ring` |
| [`beat-stills/expo.png`](beat-stills/expo.png) | `beat_render.py` | `blender ... --python beat_render.py -- expo` |

## Beating-heart videos

The 20-second `story` shot — the heart appears, its fibre tracts light up, the
camera orbits 360°, the fibres fade as the beat starts, then the heart is
progressively cut open and the beating cross-section is held. All eight materials
here are **case 1**; the same commands produce cases 2–5 by pointing `BEAT_DIR` at
another converted case.

These previews are 540², 30 fps, 20 s. The delivered versions are 1080², and each
also exists as a ProRes 4444 alpha master, a VP9 WebM with alpha, and a
white-background MP4 fallback — see
[Delivery encodes](../beat_video/README.md#delivery-encodes).

Each was rendered with
`MATERIAL=<key> blender --background --factory-startup --python beat_video/render_beat_video.py -- story`
and encoded with
`blender ... --python beat_video/encode_video.py -- <case>/story_<key> <out>.mp4 30`.

| Video | `MATERIAL` |
|-------|------------|
| [`beat-video/story-realistic-fresh.mp4`](beat-video/story-realistic-fresh.mp4) | `realistic_fresh` |
| [`beat-video/story-realistic-fibres.mp4`](beat-video/story-realistic-fibres.mp4) | `realistic_fibres` |
| [`beat-video/story-wax.mp4`](beat-video/story-wax.mp4) | `wax` |
| [`beat-video/story-glass-ruby.mp4`](beat-video/story-glass-ruby.mp4) | `glass_ruby` |
| [`beat-video/story-porcelain.mp4`](beat-video/story-porcelain.mp4) | `porcelain` |
| [`beat-video/story-bronze.mp4`](beat-video/story-bronze.mp4) | `bronze` |
| [`beat-video/story-steampunk.mp4`](beat-video/story-steampunk.mp4) | `steampunk` |
| [`beat-video/story-hipct.mp4`](beat-video/story-hipct.mp4) | `hipct` |

[`beat-video/grid-materials.mp4`](beat-video/grid-materials.mp4) tiles all eight
into one labelled montage (`python beat_video/grid_videos.py <case> 320`, then
encode `<case>/grid_frames` the same way).

The players for these are embedded in the [top-level README](../README.md#beating-heart-video);
GitHub shows them as download links when viewed from this folder.

## Electrical activation videos

The end-diastolic heart (no motion, fixed anterior view) with the electrical
wave spreading over it: reaction-eikonal activation times from the
[Zenodo EP record](https://zenodo.org/records/21720235), sample 74 (the nearest
to the baseline parameters), atria first and the ventricles 100 ms later. The
activation times are published. The geometry comes from the same unpublished time
series as the beating-heart videos, so these can be re-run on that data or on your
own. Full pipeline:
[Electrical activation video](../beat_video/README.md#electrical-activation-video-ep).

| Output | What | Command |
|--------|------|---------|
| [`ep-video/ep-wave-hcm1.mp4`](ep-video/ep-wave-hcm1.mp4) | HCM1, travelling wave, white, 5× slow, 800 ms cycle, 3 beats | `STYLE=wave FINISH=matte blender ... --python beat_video/render_ep_video.py -- beat`, then `python beat_video/compose_ep_video.py <case>/ep_74/wave_matte white out.mp4 --plain --slow 5 --cl 800 --beats 3` |
| [`ep-video/ep-wave-hcm3.mp4`](ep-video/ep-wave-hcm3.mp4) | HCM3, same settings | as above with `BEAT_DIR=<case3>` |
| [`ep-video/ep-map-overlays-hcm1.mp4`](ep-video/ep-map-overlays-hcm1.mp4) | HCM1, CARTO activation map with isochrones, ms clock, beat timeline and per-region colour bars (33× slow) | `STYLE=map FINISH=matte blender ... -- beat`, then `python beat_video/compose_ep_video.py <case>/ep_74/map_matte white out.mp4 --beats 2 --label "HCM patient 1"` |
| [`ep-video/ep-mech-hcm1.mp4`](ep-video/ep-mech-hcm1.mp4) | HCM1 cycle 532, EP **and contraction**, 2× slow, diastasis compressed, 6 beats | `python beat_video/prepare_ep.py HCM1_cycle_532_vm_act_seq.dat <case1> cycle532`, then `SAMPLE=cycle532 STYLE=wave FINISH=matte blender ... --python beat_video/render_ep_video.py -- mech`, then `python beat_video/compose_ep_video.py <case1>/ep_cycle532/wave_matte white out.mp4 --mech` |
| [`ep-video/ep-mech-hcm3.mp4`](ep-video/ep-mech-hcm3.mp4) | HCM3 cycle 237, same settings | as above with `HCM3_cycle_237_vm_act_seq.dat`, `<case3>`, `SAMPLE=cycle237` |
| [`ep-video/ep-mech-hcm1-slow7.mp4`](ep-video/ep-mech-hcm1-slow7.mp4) | HCM1 cycle 532 at 7× slow, 3 beats | `SLOW=7 SHUTTER=0.5 SUBSAMPLES=3` on the `mech` render, `--beats 3` |
| [`ep-video/looks.png`](ep-video/looks.png) | every `STYLE` × `FINISH` at t = 160 ms, on black and on white | `STYLE=<s> FINISH=<f> blender ... -- still 160` for each combination |

The `ep-mech-*` videos use the `vm_act_seq.dat` activation times that drove each
mechanics run (not on Zenodo). The wave and mech previews are 540² crops of the
1920×1080 videos; the map preview is
960×540 and was cut from a 720² `TEST=1` render. All of them are rendered with
a transparent background, so the same frames give the black-background versions
(`black` instead of `white`).
