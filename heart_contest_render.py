import os
import bpy
import bmesh
import sys
import math
import numpy as np
from mathutils import Vector, Quaternion

# ----------------------------------------------------------------------------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["test"]
MODE = argv[0] if argv else "test"
print(f"=== RENDER MODE: {MODE} ===")

SCIBLEND = (os.environ.get("SCIBLEND_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "meshes", "sciblend"))
OUTDIR = (os.environ.get("OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
TARGET_SIZE = 0.15   # ~15 cm hearts (metres) -> realistic photographic scale

# Camera at world origin looking -Z; -Z is in front, +X right, +Y up.
# --- camera defined here so Hearts 3-5 can be laid out directly in image space ---
CAM_LOC = Vector(( 0.09, -0.02,  0.17))
CAM_TARGET = Vector(( 0.02,  0.04, -0.35))
ROLL_DEG = 70.0
_d = (CAM_TARGET - CAM_LOC)
CAM_QUAT = Quaternion(_d.normalized(), math.radians(ROLL_DEG)) @ _d.to_track_quat("-Z", "Y")
_cm = CAM_QUAT.to_matrix()
CAM_RIGHT, CAM_UP, CAM_FWD = _cm.col[0], _cm.col[1], -_cm.col[2]


def img_to_world(h, v, depth):
    """World point that projects to image coords (h, v) at the given view depth.
    h, v are tangent units; frame edge ~ +/-0.36 (50mm lens / 36mm vertical sensor)."""
    return tuple(CAM_LOC + depth * CAM_FWD + (h * depth) * CAM_RIGHT + (v * depth) * CAM_UP)


QUEUE = {
    1: ( 0.00,  0.00,  0.00),                # hero, bottom-left
    2: img_to_world(-0.11, 0.03, 0.30),      # moved left, more behind Heart 1
    3: img_to_world( 0.05, 0.15, 0.50),      # queue recedes to the RIGHT at a level height
    4: img_to_world( 0.18, 0.16, 0.70),
    5: img_to_world( 0.27, 0.15, 0.88),      # kept level (not dipping low)
}
# per-heart fine orientation corrections (degrees), validated against the user
YAW = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
ROLL = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 10.0}
# which HCM mesh sits at each queue position (Heart 1 <-> Heart 4 swapped)
HEART_FILE = {1: 4, 2: 2, 3: 3, 4: 1, 5: 5}

LV_WIRE_TARGET_TRIS = 6000
WARM_WHITE = (1.0, 0.85, 0.7)


# ---------------------------------------------------------------- geometry ---
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
    faces = lvi.reshape(-1, 3); fsorted = np.sort(faces, axis=1)
    uniq, inv, cnt = np.unique(fsorted, axis=0, return_inverse=True, return_counts=True)
    surf = faces[cnt[inv.ravel()] == 1]
    used = np.unique(surf)
    remap = np.full(used.max() + 1, -1, dtype=np.int32); remap[used] = np.arange(used.size, dtype=np.int32)
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


def build_world(name, world, faces, midx=None):
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
    if midx is not None:
        me.polygons.foreach_set("material_index", midx.astype(np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32))
    me.update()
    return me


# --------------------------------------------------------------- materials ---
def make_glass(name, color, rough=0.03, trans=0.45):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.50
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = trans
    elif "Transmission" in b.inputs:
        b.inputs["Transmission"].default_value = trans
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_wireglow(name, wire_color, wire_size=0.6, strength=4.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*wire_color, 1.0)
    em.inputs["Strength"].default_value = strength
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True
    wf.inputs["Size"].default_value = wire_size
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


# --------------------------------------------------------------- build ------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

red_mat = make_glass("RedGlass", (0.55, 0.012, 0.02), trans=0.84)    # deep jewel red
blue_mat = make_glass("BlueGlass", (0.02, 0.05, 0.55), trans=0.84)   # deep jewel blue
grey_mat = make_glass("GreyGlass", (0.70, 0.70, 0.74), rough=0.04, trans=0.80)
wire_mat = make_wireglow("LV_WireGlow", WARM_WHITE)

lv_clear_mat = bpy.data.materials.new("LV_Clear")          # transparent -> "no ventricle"
lv_clear_mat.use_nodes = True
_ct = lv_clear_mat.node_tree; _ct.nodes.clear()
_co = _ct.nodes.new("ShaderNodeOutputMaterial")
_cb = _ct.nodes.new("ShaderNodeBsdfTransparent")
_ct.links.new(_cb.outputs["BSDF"], _co.inputs["Surface"])


def update_wire(mat, color, strength):
    for n in mat.node_tree.nodes:
        if n.type == "EMISSION":
            n.inputs["Color"].default_value = (*color, 1.0)
            n.inputs["Strength"].default_value = strength

heart1 = None
lv_overlay = None

for i in range(1, 6):
    with bpy.data.libraries.load(f"{SCIBLEND}\\HCM{HEART_FILE[i]}.blend", link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n == "Frame_1"]
    fme = dst.objects[0].data
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
    if i == 1 and mx >= 1:
        lut[1] = 3                          # hero LV -> own slot (toggle glass/clear per variant)
    midx = lut[np.clip(mode, 0, mx)]

    c_local = (coords.min(0) + coords.max(0)) / 2.0
    s = TARGET_SIZE / float((coords.max(0) - coords.min(0)).max())
    corr = rotZ(ROLL[i]) @ rotY(YAW[i])
    view = ((coords - c_local) @ R.T) @ corr.T          # [right, up, ant]
    world = view * s + np.array(QUEUE[i])

    me = build_world(f"Heart_{i}", world, faces, midx)
    me.materials.append(red_mat); me.materials.append(blue_mat); me.materials.append(grey_mat)
    if i == 1:
        me.materials.append(red_mat)        # slot 3 = hero LV (swapped to clear per variant)
    ob = bpy.data.objects.new(f"Heart_{i}", me)
    scene.collection.objects.link(ob)
    print(f"Heart {i}: faces={len(faces)} pos={QUEUE[i]}")

    if i == 1:
        heart1 = ob
        lv_mask = (mode == 1)                            # LV only (not LA)
        lv_faces = faces[lv_mask]
        lv_used = np.unique(lv_faces)
        lv_remap = np.full(lv_used.max() + 1, -1, dtype=np.int32)
        lv_remap[lv_used] = np.arange(lv_used.size, dtype=np.int32)
        lvw = world[lv_used]
        c0 = lvw.mean(0)
        lvw = c0 + (lvw - c0) * 1.004                    # float just outside the glass
        lv_overlay = (lvw, lv_remap[lv_faces])

# --- Heart 1 LV glowing-wire overlay ---
if lv_overlay is not None:
    lvw, lvf = lv_overlay
    ov_me = build_world("LV_wire", lvw, lvf)
    ov_me.materials.append(wire_mat)
    ov = bpy.data.objects.new("Heart_1_LV_wire", ov_me)
    scene.collection.objects.link(ov)
    dec = ov.modifiers.new("Decimate", "DECIMATE")
    dec.ratio = min(1.0, LV_WIRE_TARGET_TRIS / max(1, len(lvf)))
    print(f"LV wire overlay: base={len(lvf)} ratio={dec.ratio:.4f}")

# --------------------------------------------------------------- camera ------
cd = bpy.data.cameras.new("MainCam")
cd.lens = 50.0
cd.sensor_fit = "VERTICAL"; cd.sensor_height = 36.0
cd.clip_start = 0.01; cd.clip_end = 10000.0
cd.dof.use_dof = True
# orientation is baked into the mesh (object origins at 0,0,0), so focus by
# DISTANCE, not object. Focus ~Heart 1; higher f-stop keeps Heart 2 fairly sharp.
cd.dof.focus_distance = 0.16              # on Heart 1's wireframe
cd.dof.aperture_fstop = 80.0             # deeper DoF -> Heart 2 sharper, Heart 1 still crisp
cam = bpy.data.objects.new("MainCam", cd)
cam.location = CAM_LOC
cam.rotation_euler = CAM_QUAT.to_euler()   # same transform used to lay out Hearts 3-5
scene.collection.objects.link(cam); scene.camera = cam

# --------------------------------------------------------------- lights ------
from mathutils import Vector
def add_area(name, loc, target, size, energy, color):
    ld = bpy.data.lights.new(name, "AREA"); ld.shape = "SQUARE"
    ld.size = size; ld.energy = energy; ld.color = color
    o = bpy.data.objects.new(name, ld); o.location = Vector(loc)
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)

CENTER = (0.04, 0.05, -0.12)
add_area("Key",  (-0.25,  0.25,  0.35), CENTER, 1.9, 10.0, (1.00, 0.93, 0.86))  # large soft
add_area("Fill", ( 0.40, -0.10,  0.35), CENTER, 1.6,  7.0, (0.98, 0.98, 1.00))  # large soft fill
add_area("Back", ( 0.15,  0.25, -0.85), CENTER, 0.9,  2.0, (0.78, 0.86, 1.00))  # mid size -> moderately sharp rim

world = bpy.data.worlds.new("World"); scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.03, 0.03, 0.05, 1)   # near-black cool
bg.inputs["Strength"].default_value = 0.03

# --------------------------------------------------------------- render ------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.use_denoising = True
try:
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception:
    pass
scene.cycles.transmission_bounces = 16
scene.cycles.max_bounces = 24
scene.cycles.caustics_reflective = True
scene.cycles.caustics_refractive = True
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "16"
try:
    scene.view_settings.view_transform = "AgX"
except Exception:
    scene.view_settings.view_transform = "Filmic"
for look in ("AgX - High Contrast", "High Contrast"):
    try:
        scene.view_settings.look = look; break
    except Exception:
        continue

scene.render.resolution_percentage = 100

if MODE == "variants":
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.cycles.samples = 96
    # bloom on the bright wireframe -> "glowy"
    scene.use_nodes = True
    _cn = scene.node_tree; _cn.nodes.clear()
    _rl = _cn.nodes.new("CompositorNodeRLayers")
    _gl = _cn.nodes.new("CompositorNodeGlare")
    _gl.glare_type = "FOG_GLOW"; _gl.quality = "HIGH"; _gl.threshold = 1.0; _gl.size = 7
    _cp = _cn.nodes.new("CompositorNodeComposite")
    _cn.links.new(_rl.outputs["Image"], _gl.inputs["Image"])
    _cn.links.new(_gl.outputs["Image"], _cp.inputs["Image"])
    VARIANTS = [
        ("variant 1 - green wireframe",              (0.06, 1.00, 0.12),  6.5, True),
        ("variant 2 - fire red wireframe",           (1.00, 0.18, 0.01), 12.0, True),
        ("variant 3 - white wireframe no ventricle", (1.00, 0.95, 0.88),  5.5, False),
        ("variant 4 - green wireframe no ventricle", (0.06, 1.00, 0.12),  6.5, False),
        ("variant 5 - red wireframe no ventricle",   (1.00, 0.06, 0.05),  7.0, False),
        ("variant 6 - white wireframe glow",         (1.00, 0.85, 0.70), 12.0, True),
    ]
    for vname, wcol, wstr, lv_glass in VARIANTS:
        update_wire(wire_mat, wcol, wstr)
        if heart1 is not None and len(heart1.data.materials) >= 4:
            heart1.data.materials[3] = red_mat if lv_glass else lv_clear_mat
        scene.render.filepath = f"{OUTDIR}\\{vname}.png"
        bpy.ops.render.render(write_still=True)
        print(f"VARIANT DONE: {vname}")
elif MODE == "final":
    import os
    out4k = os.path.join(OUTDIR, "4k")
    os.makedirs(out4k, exist_ok=True)
    scene.render.resolution_x = scene.render.resolution_y = 4096
    scene.cycles.samples = 512
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = f"{out4k}\\queue - white wireframe.png"
    print("Rendering ->", scene.render.filepath)
    bpy.ops.render.render(write_still=True)
    print(f"RENDER COMPLETE: {scene.render.filepath}")
else:
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.cycles.samples = 64
    scene.render.filepath = f"{OUTDIR}\\contest_test.png"
    print("Rendering ->", scene.render.filepath)
    bpy.ops.render.render(write_still=True)
    print(f"RENDER COMPLETE: {scene.render.filepath}")
