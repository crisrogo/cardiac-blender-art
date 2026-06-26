# Meshes (added once the paper is published)

The input meshes are **not** in this repository yet — they'll be added when the
associated paper is published. Place them here as follows (or point the scripts
elsewhere with the environment variables noted below).

## `sciblend/` — HCM glass-heart figures
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

## `pacemaker/` — cardiac-cycle "beat" figures
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
