import os
import bpy
import bmesh
import math
import numpy as np

SCIBLEND = (os.environ.get("SCIBLEND_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "meshes", "sciblend"))
OUTDIR = (os.environ.get("OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
TARGET = 150.0

YAW = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
ROLL = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: -90.0}


def norm(v):
    return v / np.linalg.norm(v)


def rotY(deg):
    t = math.radians(deg); c, s = math.cos(t), math.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rotZ(deg):
    t = math.radians(deg); c, s = math.cos(t), math.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def surface_and_tags(me):
    nv = len(me.vertices); nl = len(me.loops)
    coords = np.empty(nv * 3); me.vertices.foreach_get("co", coords); coords = coords.reshape(-1, 3)
    tags = np.empty(nv); me.attributes["elemTag"].data.foreach_get("value", tags)
    lvi = np.empty(nl, dtype=np.int32); me.loops.foreach_get("vertex_index", lvi)
    faces = lvi.reshape(-1, 3)
    fsorted = np.sort(faces, axis=1)
    uniq, inv, cnt = np.unique(fsorted, axis=0, return_inverse=True, return_counts=True)
    surf = faces[cnt[inv.ravel()] == 1]
    used = np.unique(surf)
    remap = np.full(used.max() + 1, -1, dtype=np.int32)
    remap[used] = np.arange(used.size, dtype=np.int32)
    return coords[used], tags[used], remap[surf]


def anat_rot(coords, tags):
    """rows map local -> (left=+X right, superior=+Y up, anterior=+Z toward cam)."""
    rt = np.rint(tags).astype(np.int64)
    C = {l: coords[rt == l].mean(0) for l in range(1, 7) if (rt == l).any()}
    def grp(ls):
        return np.mean([C[l] for l in ls if l in C], axis=0)
    base = grp([3, 4, 5, 6]); lv = coords[rt == 1]
    d = np.linalg.norm(lv - base, axis=1)
    apex = lv[d >= np.percentile(d, 98)].mean(0)
    up = norm(base - apex)
    left = grp([1, 3]) - grp([2, 4]); left = norm(left - np.dot(left, up) * up)
    ant = norm(np.cross(left, up))
    return np.array([left, up, ant])


def build_world(name, world, faces, midx):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(world)); me.vertices.foreach_set("co", world.astype(np.float32).ravel())
    nf = len(faces)
    me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set("material_index", midx.astype(np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32))
    me.update()
    return me


def mat(n, col):
    m = bpy.data.materials.new(n); m.diffuse_color = (*col, 1.0); return m


for i in range(1, 6):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    with bpy.data.libraries.load(f"{SCIBLEND}\\HCM{i}.blend", link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n == "Frame_1"]
    mo = dst.objects[0]
    fme = mo.data

    fnv = len(fme.vertices)
    fco = np.empty(fnv * 3); fme.vertices.foreach_get("co", fco); fco = fco.reshape(-1, 3)
    ftg = np.empty(fnv); fme.attributes["elemTag"].data.foreach_get("value", ftg)
    R = anat_rot(fco, ftg)

    coords, tags, faces = surface_and_tags(fme)
    rt = np.rint(tags).astype(np.int64)
    ft = rt[faces]; a, b, c = ft[:, 0], ft[:, 1], ft[:, 2]
    mode = np.where(a == b, a, np.where(a == c, a, np.where(b == c, b, a)))
    mx = int(mode.max())
    lut = np.full(mx + 1, 2, dtype=np.int32)
    for t in (1, 3):
        if t <= mx: lut[t] = 0
    for t in (2, 4):
        if t <= mx: lut[t] = 1
    midx = lut[np.clip(mode, 0, mx)]

    # --- bake orientation directly into vertex coords (no matrix_world) ---
    c_local = (coords.min(0) + coords.max(0)) / 2.0
    s = TARGET / float((coords.max(0) - coords.min(0)).max())
    corr = rotZ(ROLL[i]) @ rotY(YAW[i])
    view = (coords - c_local) @ R.T          # -> [right, up, ant]
    view = view @ corr.T
    world = view * s + np.array([0.0, 0.0, -400.0])

    me2 = build_world(f"H{i}", world, faces, midx)
    me2.materials.append(mat("r", (0.8, 0.05, 0.05)))
    me2.materials.append(mat("b", (0.05, 0.15, 0.85)))
    me2.materials.append(mat("g", (0.8, 0.8, 0.82)))
    # fresh object with identity transform (loaded Frame_1 carries a parent +
    # 0.001 scale that otherwise shrinks the baked-in world coords to nothing)
    ob = bpy.data.objects.new(f"H{i}", me2)
    scene.collection.objects.link(ob)

    cd = bpy.data.cameras.new("c"); cd.lens = 70
    cd.clip_end = 10000.0
    cam = bpy.data.objects.new("c", cd)
    scene.collection.objects.link(cam); scene.camera = cam
    cam.location = (0.0, 0.0, 0.0)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = scene.render.resolution_y = 600
    scene.render.filepath = f"{OUTDIR}\\heart_check_{i}.png"
    bpy.ops.render.render(write_still=True)
    print(f"CHECK {i} DONE")

print("ALL CHECKS DONE")
