# Example outputs (low-res)

These are low-resolution versions of the figures and videos the pipeline
produces, included so you can see the expected end result before you render your
own. The full-resolution 4K contest submissions and the raw meshes are not
included here (see the note in the top-level [`README.md`](../README.md)).

Every file below is reproducible from the scripts in this repo once the input
meshes are in place; the command that produces each one is listed.

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

A 360-degree orbit of one HCM heart as it beats, rendered in eight materials
plus a side-by-side comparison grid. Produced by
[`beat_video/render_beat_video.py`](../beat_video/render_beat_video.py) (see
[`beat_video/README.md`](../beat_video/README.md)). GitHub shows these as
download links rather than an inline player.

| Video | Material |
|-------|----------|
| [`beat-video/grid-materials.mp4`](beat-video/grid-materials.mp4) | all eight materials side by side |
| [`beat-video/story-realistic-fresh.mp4`](beat-video/story-realistic-fresh.mp4) | realistic fresh tissue |
| [`beat-video/story-realistic-fibres.mp4`](beat-video/story-realistic-fibres.mp4) | realistic tissue with fibres |
| [`beat-video/story-wax.mp4`](beat-video/story-wax.mp4) | wax |
| [`beat-video/story-glass-ruby.mp4`](beat-video/story-glass-ruby.mp4) | ruby glass |
| [`beat-video/story-porcelain.mp4`](beat-video/story-porcelain.mp4) | porcelain |
| [`beat-video/story-bronze.mp4`](beat-video/story-bronze.mp4) | bronze |
| [`beat-video/story-steampunk.mp4`](beat-video/story-steampunk.mp4) | steampunk |
| [`beat-video/story-hipct.mp4`](beat-video/story-hipct.mp4) | HiP-CT grey |
