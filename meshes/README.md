# Meshes

The input meshes are **not** stored in this repository (they are far too large for
git). The two still-figure mesh sets — `sciblend/` and `pacemaker/` — are
archived on **Zenodo**:

> **DOI: [10.5281/zenodo.XXXXXXX](https://doi.org/10.5281/zenodo.XXXXXXX)**
> *(placeholder — replace with the record DOI once it is minted)*

Download the record and unpack it here, as below. Every path is overridable with
the environment variable noted, so you can keep the meshes on another drive.

The **volumetric time series behind the beating-heart video is not published** —
see `videos_HCM/` at the bottom of this page.

## `sciblend/` — HCM glass-heart figures (TUTORIAL Part A)
Five Blender files, one per hypertrophic-cardiomyopathy case:

```
meshes/sciblend/HCM1.blend
meshes/sciblend/HCM2.blend
meshes/sciblend/HCM3.blend
meshes/sciblend/HCM4.blend
meshes/sciblend/HCM5.blend
```

Each `.blend` must contain a mesh object named **`Frame_1`** carrying a
per-vertex float attribute **`elemTag`**
(`1`=LV, `2`=RV, `3`=LA, `4`=RA, `5`=aorta, `6`=PA, other=valves/vessels).
Override the folder with `SCIBLEND_DIR`.

## `pacemaker/` — cardiac-cycle "beat" figures (TUTORIAL Part B)
Eleven motion-tracked surface meshes, one per cardiac-cycle phase
(`transformed-7` may be absent — the code tolerates gaps):

```
meshes/pacemaker/transformed-0.vtk
meshes/pacemaker/transformed-1.vtk
...
meshes/pacemaker/transformed-10.vtk
```

ASCII VTK **`POLYDATA`** with a per-cell **`elemTag`** scalar
(`0`=myocardial shell, `40`/`10`=ventricular chambers,
`1`/`2`/`30`=inner structures — papillary muscles, moderator band, valve).
Override the folder with `VTK_DIR`.

## `videos_HCM/` — beating-heart video (TUTORIAL Part C)

> **Not on Zenodo, and not otherwise published.** At ~300 MB per timestep, ~100
> timesteps per case and five cases, the series runs to roughly 30 GB per case —
> impractical to archive, so it is not part of the record above. Part C therefore
> cannot be re-run from published data: what the repo gives you is the exact
> transformation, not the input. The scripts are not specific to these files
> though — any tetrahedral time series with the same structure (see below) will
> go through the pipeline unchanged.

The HCM volumetric simulation time series, one folder per case:

```
meshes/videos_HCM/case1/HCM1_532_0000.vtu … HCM1_532_0101.vtu
meshes/videos_HCM/case1/HCM1_532.lon
```

Each `.vtu` is **~300 MB** (≈0.75 M points, ≈3.9 M tetrahedra, units in
micrometres) with point `displacement` and cell `elemTags` / `fibres`; the `.lon`
is the openCARP fibre file, one row per tetrahedron in the same order as the VTU.
The tag convention is the same as `sciblend/` for chambers and vessels
(`1`–`6`); the higher tags are valves, veins and endocardial surfaces and are
**case-specific** — run `beat_video/identify_tags.py` per case to find them.

There is no fixed location for these: the source directory is passed on the
command line, and the converted frames land in the case directory
(`output/beat_video/<case>`, override with `BEAT_DIR`). The five published
videos correspond to `case1` … `case5`.

## EP activation times — electrical activation video (TUTORIAL Part D)

> **Published separately**, on Zenodo:
> [record 21720235](https://zenodo.org/records/21720235) (*Electrophysiology
> simulations in hypertrophic cardiomyopathy patients*).

One `HCMn_EP_light.tar.zst` per patient. Each unpacks to `HCMn_EP/` with 120
reaction-eikonal activation-time maps (`activation_maps/<id>.dat`, one value in
ms per node of the `videos_HCM` mesh, `-1` where the tissue is not excitable) and
their inputs (`inputs/json_files/<id>.json`, `default.json`, `tags_EP.json`).
There is no fixed location; the unpacked folder is passed to
`beat_video/prepare_ep.py`. The activation times of the mechanics runs themselves
(`HCMn_cycle_<N>_vm_act_seq.dat`, used for EP + contraction) are **not** in this
record. The geometry these values sit on is the unpublished
time series above.
