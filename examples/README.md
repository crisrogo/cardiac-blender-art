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
