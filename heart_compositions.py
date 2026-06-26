import bpy
import bmesh
import sys
import os
import math
import numpy as np
from mathutils import Vector, Quaternion, Matrix

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
COMP = (ARGS or ["vshape"])[0]
HERO_YAW = None                                        # optional hero-yaw override (raphero)
if len(ARGS) > 1:
    try:
        HERO_YAW = float(ARGS[1])
    except ValueError:
        HERO_YAW = None
print(f"=== COMPOSITION: {COMP} ===")

SCIBLEND = (os.environ.get("SCIBLEND_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "meshes", "sciblend"))
OUTDIR = (os.environ.get("OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
TARGET_SIZE = 0.15
HEART_FILE = {1: 4, 2: 2, 3: 3, 4: 1, 5: 5}   # position 1 = hero (wireframe)
WARM_WHITE = (1.0, 0.85, 0.7)
LV_WIRE_TARGET_TRIS = 6000


def norm(v):
    return v / np.linalg.norm(v)


def surface_and_tags(me):
    nv = len(me.vertices); nl = len(me.loops)
    coords = np.empty(nv * 3); me.vertices.foreach_get("co", coords); coords = coords.reshape(-1, 3)
    tags = np.empty(nv); me.attributes["elemTag"].data.foreach_get("value", tags)
    lvi = np.empty(nl, dtype=np.int32); me.loops.foreach_get("vertex_index", lvi)
    faces = lvi.reshape(-1, 3); fs = np.sort(faces, axis=1)
    u, inv, cnt = np.unique(fs, axis=0, return_inverse=True, return_counts=True)
    surf = faces[cnt[inv.ravel()] == 1]
    used = np.unique(surf)
    remap = np.full(used.max() + 1, -1, dtype=np.int32); remap[used] = np.arange(used.size, dtype=np.int32)
    return coords[used], tags[used], remap[surf]


def anat_rot(coords, tags):
    rt = np.rint(tags).astype(np.int64)
    C = {l: coords[rt == l].mean(0) for l in range(1, 7) if (rt == l).any()}
    def grp(ls):
        return np.mean([C[l] for l in ls if l in C], axis=0)
    base = grp([3, 4, 5, 6]); lv = coords[rt == 1]
    d = np.linalg.norm(lv - base, axis=1)
    apex = lv[d >= np.percentile(d, 98)].mean(0)
    up = norm(base - apex)
    left = grp([1, 3]) - grp([2, 4]); left = norm(left - np.dot(left, up) * up)
    return np.array([left, up, norm(np.cross(left, up))])


def build_world(name, world, faces, midx=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(world)); me.vertices.foreach_set("co", world.astype(np.float32).ravel())
    nf = len(faces); me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    if midx is not None:
        me.polygons.foreach_set("material_index", midx.astype(np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32)); me.update()
    return me


def make_glass(name, color, rough=0.03, trans=0.84):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.50
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = trans
    nt.links.new(b.outputs["BSDF"], o.inputs["Surface"])
    return m


def make_wireglow(name, color, wire_size=0.6, strength=4.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True; wf.inputs["Size"].default_value = wire_size
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], o.inputs["Surface"])
    return m


# ---------------------------------------------------------------- composition ---
RAW = ("raw" in ARGS)        # plain matte "source meshes" modifier on ANY layout (AI-use disclosure)
if COMP in ("vshape", "vbow", "vslope", "raw"):
    LENS = 30.0
    LEAN = {1: -30, 2: -30, 3: -30, 4: -30, 5: -30}  # -30deg tilt
    YAW = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    CAM_LOC = Vector((0.0, -0.12, 0.45)); CAM_TARGET = Vector((0.0, 0.10, 0.05)); CAM_ROLL = 0.0
    IMG = {1: (0.00, -0.18, 0.27),                  # hero brought up toward the pack
           2: (-0.29, 0.08, 0.31), 3: (0.29, 0.08, 0.31),   # middle pair brought up
           4: (-0.40, 0.38, 0.38), 5: (0.40, 0.38, 0.38)}   # corners (fixed)
    FOCUS, FSTOP = 0.31, 18.0
    LIGHTS = [("Key", (-0.30, 0.40, 0.55), (0, 0.05, 0.15), 1.7, 12.0, (1.00, 0.93, 0.86)),
              ("Fill", (0.40, 0.00, 0.55), (0, 0.05, 0.15), 1.5, 7.0, (0.98, 0.98, 1.00)),
              ("Back", (0.00, 0.35, -0.15), (0, 0.10, 0.10), 0.9, 2.5, (0.78, 0.86, 1.00))]
    OUT = "composition - vshape"
    if COMP == "vbow":
        IMG = {1: (0.00, 0.28, 0.27),                       # hero -> top-centre keystone (lowered)
               2: (-0.33, 0.16, 0.31), 3: (0.33, 0.16, 0.31),   # inner pair (lowered)
               4: (-0.48, -0.24, 0.44), 5: (0.48, -0.24, 0.44)}  # outer pair: lowered + pushed back to fit
        OUT = "composition - vbow"
    if COMP == "vslope":
        RAMP_S = math.tan(math.radians(68.0)); RAMP_C = 0.0   # floor: Y = RAMP_C - RAMP_S*Z (68deg, rises away)
        POS_PHYS = {1: (0.00, 0.0, 0.167),                    # hero nearest, centre (Z compressed -> fits steep ramp)
                    2: (-0.11, 0.0, 0.089), 3: (0.11, 0.0, 0.089),
                    4: (-0.20, 0.0, -0.002), 5: (0.20, 0.0, -0.002)}
        CAM_LOC = Vector((0.0, -0.39, 0.45)); CAM_TARGET = Vector((0.0, -0.02, 0.02))  # foot of ramp, looking up, close
        FOCUS = 0.48
        OUT = "composition - vslope"
    if COMP == "raw":
        LEAN = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}             # straight anterior, no artistic tilt
        LIGHTS = [("Key",  (-0.40, 0.30, 0.60), (0, 0.05, 0.10), 2.0, 8.0, (1.0, 1.0, 1.0)),
                  ("Fill", ( 0.40, 0.20, 0.60), (0, 0.05, 0.10), 2.0, 8.0, (1.0, 1.0, 1.0)),
                  ("Top",  ( 0.00, 0.60, 0.30), (0, 0.00, 0.10), 1.5, 5.0, (1.0, 1.0, 1.0))]
        OUT = "raw - source meshes"
else:  # rap
    LENS = 24.0
    APEX_IMG = {1: (0.0, -1.0),                     # hero: apex points to the bottom edge
                2: (-0.866, -0.5), 3: (0.866, -0.5),  # laterals: apex out + 30deg down
                4: (-0.26, 0.96), 5: (0.26, 0.96)}  # top pair: apex up (unchanged)
    LEANZ = {1: 0.4, 2: 0.4, 3: 0.4, 4: 0.4, 5: 0.4}  # base/aorta tips toward the camera
    YAW_W = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}            # spin about long axis (0 = anterior dead-on)
    CAM_LOC = Vector((0.0, 0.0, 0.0)); CAM_TARGET = Vector((0.0, 0.5, 0.22)); CAM_ROLL = 0.0
    IMG = {1: (0.00, -0.42, 0.22),                  # hero -> bottom centre
           2: (-0.50, -0.10, 0.24), 3: (0.50, -0.10, 0.24),   # laterals pushed out + down
           4: (-0.22, 0.42, 0.24), 5: (0.22, 0.42, 0.24)}   # top pair pulled in/up -> no overlap
    FOCUS, FSTOP = 0.23, 13.0
    LIGHTS = [("Key", (-0.25, 0.00, 0.20), (0, 0.15, 0.18), 1.3, 6.0, (1.00, 0.93, 0.86)),
              ("Fill", (0.25, 0.00, 0.20), (0, 0.15, 0.18), 1.1, 4.0, (0.98, 0.98, 1.00)),
              ("CamFill", (0.0, -0.08, 0.05), (0, 0.18, 0.18), 0.6, 3.0, (1.0, 0.96, 0.92))]
    OUT = "composition - rap"
    if COMP == "raphero":
        IMG[1] = (0.00, -0.62, 0.15)   # hero pulled in close; raised a bit -> more LV/wireframe in frame
        YAW_W[1] = 0                   # anterior faces the camera (aorta/great vessels visible)
        LEANZ[1] = 0.1                 # nearly face-on so the anterior LV wireframe reads fully
        HERO_PITCH = 0.0 if HERO_YAW is None else HERO_YAW   # CLI arg sweeps PITCH (camera-right axis)
        FOCUS = 0.15                   # refocus on the foreground hero
        OUT = "composition - rap hero" if HERO_YAW is None else f"composition - rap hero pitch {int(HERO_YAW)}"

if RAW and not OUT.startswith("raw"):
    OUT = "raw - " + OUT.replace("composition - ", "")

# camera basis + image-space placement (shared)
_dir = (CAM_TARGET - CAM_LOC)
CAM_QUAT = Quaternion(_dir.normalized(), math.radians(CAM_ROLL)) @ _dir.to_track_quat("-Z", "Y")
_cm = CAM_QUAT.to_matrix(); CAM_R, CAM_U, CAM_F = _cm.col[0], _cm.col[1], -_cm.col[2]
def i2w(h, v, depth):
    return tuple(CAM_LOC + depth * CAM_F + (h * depth) * CAM_R + (v * depth) * CAM_U)
POS = POS_PHYS if COMP == "vslope" else {i: i2w(*IMG[i]) for i in range(1, 6)}
CAM_LOC_NP = np.array([float(CAM_LOC.x), float(CAM_LOC.y), float(CAM_LOC.z)])

# ---------------------------------------------------------------- build ---
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
if RAW:   # opaque matte -> "source geometry before glass styling"
    red_mat = make_glass("RedMatte", (0.62, 0.05, 0.05), rough=0.5, trans=0.0)
    blue_mat = make_glass("BlueMatte", (0.06, 0.10, 0.62), rough=0.5, trans=0.0)
    grey_mat = make_glass("GreyMatte", (0.78, 0.78, 0.80), rough=0.5, trans=0.0)
else:
    red_mat = make_glass("RedGlass", (0.55, 0.012, 0.02))
    blue_mat = make_glass("BlueGlass", (0.02, 0.05, 0.55))
    grey_mat = make_glass("GreyGlass", (0.70, 0.70, 0.74), rough=0.04, trans=0.80)
wire_mat = make_wireglow("LV_WireGlow", WARM_WHITE)

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
        lut[1] = 3
    midx = lut[np.clip(mode, 0, mx)]

    c_local = (coords.min(0) + coords.max(0)) / 2.0
    s = TARGET_SIZE / float((coords.max(0) - coords.min(0)).max())
    view = (coords - c_local) @ R.T                       # [left, up, ant]
    P = np.array(POS[i])
    if COMP in ("rap", "raphero"):
        # worm's-eye: anterior auto-faces the low camera; the long axis is aimed so the
        # apex points in a chosen image-space direction (the "feet"); the base/aorta tips
        # toward the camera (LEANZ) like a face looking down at the viewer.
        cr = np.array([CAM_R.x, CAM_R.y, CAM_R.z])
        cu = np.array([CAM_U.x, CAM_U.y, CAM_U.z])
        cf = np.array([CAM_F.x, CAM_F.y, CAM_F.z])
        ah, av = APEX_IMG[i]
        up = -(ah * cr + av * cu) - LEANZ[i] * cf         # apex->base; base tipped toward camera
        up = up / np.linalg.norm(up)
        tc = CAM_LOC_NP - P; tc = tc / np.linalg.norm(tc)  # toward camera
        ant = tc - np.dot(tc, up) * up                    # face camera, perpendicular to long axis
        ant = ant / np.linalg.norm(ant)
        left = np.cross(up, ant)                          # anterior = cross(left, up)
        yw = math.radians(YAW_W[i])                       # yaw about long axis (apex unchanged)
        if yw:
            ca, sa = math.cos(yw), math.sin(yw)
            ant, left = ant * ca + left * sa, -ant * sa + left * ca
        view = view @ np.column_stack([left, up, ant]).T
    else:
        to_cam = CAM_LOC_NP - P; to_cam[1] = 0.0          # horizontal direction to the camera
        if np.linalg.norm(to_cam) < 1e-4:
            to_cam = np.array([0.0, 0.0, -1.0])
        t_ant = to_cam / np.linalg.norm(to_cam)           # anterior faces the camera (apex stays down)
        t_up = np.array([0.0, 1.0, 0.0])
        t_left = np.cross(t_up, t_ant)
        b = math.radians(LEAN[i])                         # tilt forward: apex tips toward the low camera
        t_ant2 = t_ant * math.cos(b) + t_up * math.sin(b)
        t_up2 = t_up * math.cos(b) - t_ant * math.sin(b)
        yaw = math.radians(YAW[i])                        # spin about the heart's up axis
        ca, sa = math.cos(yaw), math.sin(yaw)
        t_antF = t_ant2 * ca + t_left * sa
        t_leftF = -t_ant2 * sa + t_left * ca
        view = view @ np.column_stack([t_leftF, t_up2, t_antF]).T
    world = view * s + np.array(POS[i])
    if COMP == "vslope":
        gap = world[:, 1] - (RAMP_C - RAMP_S * world[:, 2])   # height of each vertex above the ramp
        world[:, 1] -= gap.min()                              # drop so the lowest vertex rests on it
    if COMP == "raphero" and i == 1 and abs(HERO_PITCH) > 1e-6:
        k = np.array([CAM_R.x, CAM_R.y, CAM_R.z])             # camera right axis -> pitch (nod)
        th = math.radians(HERO_PITCH); rel = world - P        # tip the hero top toward/away from camera
        world = (rel * math.cos(th) + np.cross(k, rel) * math.sin(th)
                 + np.outer(rel @ k, k) * (1.0 - math.cos(th)) + P)

    me = build_world(f"Heart_{i}", world, faces, midx)
    me.materials.append(red_mat); me.materials.append(blue_mat); me.materials.append(grey_mat)
    if i == 1:
        me.materials.append(red_mat)
    ob = bpy.data.objects.new(f"Heart_{i}", me); scene.collection.objects.link(ob)

    if i == 1 and not RAW:
        heart1 = ob
        lvm = (mode == 1)
        lvf = faces[lvm]; lvu = np.unique(lvf)
        rmp = np.full(lvu.max() + 1, -1, dtype=np.int32); rmp[lvu] = np.arange(lvu.size, dtype=np.int32)
        lvw = world[lvu]; c0 = lvw.mean(0); lvw = c0 + (lvw - c0) * 1.004
        lv_overlay = (lvw, rmp[lvf])

if lv_overlay is not None:
    lw, lf = lv_overlay
    ovme = build_world("LV_wire", lw, lf); ovme.materials.append(wire_mat)
    ov = bpy.data.objects.new("LV_wire", ovme); scene.collection.objects.link(ov)
    dec = ov.modifiers.new("Decimate", "DECIMATE"); dec.ratio = min(1.0, LV_WIRE_TARGET_TRIS / max(1, len(lf)))

if COMP == "vslope":
    # large sloped floor the hearts rest on: Y = RAMP_C - RAMP_S*Z (rises away from camera)
    L = 2.5
    yb = RAMP_C - RAMP_S * (-L); yf = RAMP_C - RAMP_S * (L)
    fpts = [(-L, yb, -L), (L, yb, -L), (L, yf, L), (-L, yf, L)]
    fme2 = bpy.data.meshes.new("Floor"); fme2.from_pydata(fpts, [], [(0, 3, 2, 1)]); fme2.update()
    fmat = bpy.data.materials.new("FloorMat"); fmat.use_nodes = True
    fbsdf = fmat.node_tree.nodes.get("Principled BSDF")
    fbsdf.inputs["Base Color"].default_value = (0.72, 0.72, 0.76, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.55
    fme2.materials.append(fmat)
    fob = bpy.data.objects.new("Floor", fme2); scene.collection.objects.link(fob)

# camera
cd = bpy.data.cameras.new("Cam"); cd.lens = LENS
cd.sensor_fit = "VERTICAL"; cd.sensor_height = 36.0; cd.clip_start = 0.005; cd.clip_end = 100
cd.dof.use_dof = (not RAW); cd.dof.focus_distance = FOCUS; cd.dof.aperture_fstop = FSTOP
cam = bpy.data.objects.new("Cam", cd); cam.location = CAM_LOC
cam.rotation_euler = CAM_QUAT.to_euler()
scene.collection.objects.link(cam); scene.camera = cam

# lights
for nm, loc, tgt, size, energy, col in LIGHTS:
    ld = bpy.data.lights.new(nm, "AREA"); ld.shape = "SQUARE"; ld.size = size; ld.energy = energy
    ld.color = (1.0, 1.0, 1.0) if RAW else col
    o = bpy.data.objects.new(nm, ld); o.location = Vector(loc)
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)

world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if RAW:
    bg.inputs["Color"].default_value = (0.70, 0.70, 0.72, 1); bg.inputs["Strength"].default_value = 1.0
elif COMP == "vslope":
    bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1); bg.inputs["Strength"].default_value = 1.0
else:
    bg.inputs["Color"].default_value = (0.03, 0.03, 0.05, 1); bg.inputs["Strength"].default_value = 0.03

# render
scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"
scene.cycles.samples = 512 if "4k" in ARGS else (32 if "test" in ARGS else 96)
scene.cycles.use_denoising = True
scene.cycles.transmission_bounces = 16; scene.cycles.max_bounces = 24
scene.cycles.caustics_reflective = True; scene.cycles.caustics_refractive = True
scene.render.film_transparent = (COMP == "vslope")
scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_depth = "8" if "4k" in ARGS else "16"
if "4k" in ARGS:
    scene.render.image_settings.color_mode = "RGB"   # no alpha -> guaranteed opaque background for submission
try:
    if RAW:
        scene.view_settings.view_transform = "Standard"
    else:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - High Contrast"
except Exception:
    pass
scene.use_nodes = True
cn = scene.node_tree; cn.nodes.clear()
rl = cn.nodes.new("CompositorNodeRLayers")
cp = cn.nodes.new("CompositorNodeComposite")
if RAW:
    cn.links.new(rl.outputs["Image"], cp.inputs["Image"])   # plain reference -> no bloom
else:
    gl = cn.nodes.new("CompositorNodeGlare")
    gl.glare_type = "FOG_GLOW"; gl.quality = "HIGH"; gl.threshold = 2.0 if COMP == "vslope" else 1.0; gl.size = 7
    cn.links.new(rl.outputs["Image"], gl.inputs["Image"])
    if COMP == "vslope":
        ao = cn.nodes.new("CompositorNodeAlphaOver")          # composite the scene over pure white
        ao.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
        cn.links.new(gl.outputs["Image"], ao.inputs[2])
        cn.links.new(ao.outputs["Image"], cp.inputs["Image"])
    else:
        cn.links.new(gl.outputs["Image"], cp.inputs["Image"])
scene.render.resolution_x = scene.render.resolution_y = (4096 if "4k" in ARGS else (2048 if RAW else (512 if "test" in ARGS else 1024)))
if "4k" in ARGS:
    os.makedirs(f"{OUTDIR}\\4k", exist_ok=True)
    scene.render.filepath = f"{OUTDIR}\\4k\\{OUT}.png"
else:
    scene.render.filepath = f"{OUTDIR}\\{OUT}.png"
print("Rendering ->", scene.render.filepath)
bpy.ops.render.render(write_still=True)
print(f"COMPOSITION DONE: {OUT}")
