import bpy, bmesh, sys, math, os
import numpy as np
from mathutils import Vector, Quaternion

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = (ARGS or ["one"])[0]
NPZ = (os.environ.get("NPZ_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "beat_npz"))
OUTDIR = (os.environ.get("OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
os.makedirs(OUTDIR, exist_ok=True)
TARGET = 0.15
WARM_WHITE = (1.0, 0.85, 0.7)

# tag -> material slot (0 red, 1 blue, 2 grey)   + wireframe on WIRE_TAG
RED = {0, 1}; BLUE = {40, 10}; GREY = {2, 30}; WIRE_TAG = 0
FLIP_UP = True       # apex down
FLIP_ANT = False     # face toward camera

# ---------- load + orient (one fixed frame for all timesteps) ----------
topo = np.load(os.path.join(NPZ, "topo.npz"))
FACES = topo["faces"].astype(np.int32); TAGS = topo["tags"].astype(np.int64)
FRAMES = [np.load(os.path.join(NPZ, f"frame_{i:02d}.npz"))["points"].astype(np.float64) for i in range(10)]

c0 = FRAMES[0].mean(0)
X = FRAMES[0] - c0
w, V = np.linalg.eigh(X.T @ X / len(X))          # ascending eigenvalues
e_small, e_mid, e_long = V[:, 0], V[:, 1], V[:, 2]
# apex = long-axis end with smaller cross-section -> point it down
proj = X @ e_long
lo = X[proj < np.percentile(proj, 8)]; hi = X[proj > np.percentile(proj, 92)]
if np.linalg.norm(lo - lo.mean(0), axis=1).mean() < np.linalg.norm(hi - hi.mean(0), axis=1).mean():
    e_long = -e_long                              # ensure +long is the broad (base) end
up = -e_long if FLIP_UP else e_long
ant = e_small if not FLIP_ANT else -e_small
left = np.cross(up, ant); left /= np.linalg.norm(left)
ant = np.cross(left, up); ant /= np.linalg.norm(ant)
R = np.array([left, up, ant])                    # rows
scale = TARGET / float((FRAMES[0].max(0) - FRAMES[0].min(0)).max())
VIEWS = [((f - c0) @ R.T) * scale for f in FRAMES]   # all frames in canonical space (beat preserved)

# chambers -> red/blue glass ; inner structures -> glowing architecture ; epicardium (tag 0) omitted
GLASS_TAGS = [40, 10]; GLOW_TAGS = [1, 2, 30]
glass_mask = np.isin(TAGS, GLASS_TAGS)
glass_midx = np.where(TAGS[glass_mask] == 40, 0, 1).astype(np.int32)
glow_mask = np.isin(TAGS, GLOW_TAGS)


def make_glass(name, color, rough=0.03, trans=0.84):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.50
    if "Transmission Weight" in b.inputs: b.inputs["Transmission Weight"].default_value = trans
    nt.links.new(b.outputs["BSDF"], o.inputs["Surface"]); return m


def make_wireglow(name, color, wire_size=0.6, strength=4.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True; wf.inputs["Size"].default_value = wire_size
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs["Fac"], mix.inputs["Fac"]); nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2]); nt.links.new(mix.outputs["Shader"], o.inputs["Surface"])
    return m


def build(name, verts, faces, mat_idx=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts)); me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    nf = len(faces); me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    if mat_idx is not None: me.polygons.foreach_set("material_index", mat_idx.astype(np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32)); me.update(); return me


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
red_mat = make_glass("Red", (0.55, 0.012, 0.02))
blue_mat = make_glass("Blue", (0.02, 0.05, 0.55))
grey_mat = make_glass("Grey", (0.70, 0.70, 0.74), rough=0.04, trans=0.80)
wire_mat = make_wireglow("Wire", WARM_WHITE)

# tag identification palette (emission) for "tagmap" mode
TAG_LIST = [0, 1, 2, 10, 30, 40]
_t2s = {t: i for i, t in enumerate(TAG_LIST)}
midx6 = np.array([_t2s[int(t)] for t in TAGS], dtype=np.int32)
TAG_COLORS = [(0.85, 0.85, 0.88), (0.95, 0.10, 0.10), (0.10, 0.90, 0.20),
              (0.15, 0.35, 1.00), (1.00, 0.85, 0.10), (1.00, 0.20, 0.90)]
def make_emit(name, col, strength=1.6):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*col, 1.0); e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs["Emission"], o.inputs["Surface"]); return m
emit_mats = [make_emit(f"E{t}", c) for t, c in zip(TAG_LIST, TAG_COLORS)]


def place(frame_i, offset, glow_strength=5.0, glass=True, glow=True, wire_chambers=False, chamber_strength=2.2):
    v = VIEWS[frame_i] + np.array(offset)
    if glass:
        me = build(f"G{frame_i}", v, FACES[glass_mask], glass_midx)
        me.materials.append(red_mat); me.materials.append(blue_mat)
        ob = bpy.data.objects.new(f"G{frame_i}", me); scene.collection.objects.link(ob)
    if wire_chambers:
        cf = FACES[glass_mask]
        cme = build(f"CW{frame_i}", v, cf, glass_midx)
        cme.materials.append(make_wireglow(f"RW{frame_i}", (0.95, 0.06, 0.05), wire_size=0.55, strength=chamber_strength))
        cme.materials.append(make_wireglow(f"BW{frame_i}", (0.10, 0.22, 0.98), wire_size=0.55, strength=chamber_strength))
        co = bpy.data.objects.new(f"CW{frame_i}", cme); scene.collection.objects.link(co)
        cd_ = co.modifiers.new("Dec", "DECIMATE"); cd_.ratio = min(1.0, 15000.0 / max(1, len(cf)))
    if glow:
        lf = FACES[glow_mask]
        lme = build(f"L{frame_i}", v, lf)
        lme.materials.append(make_wireglow(f"Glow{frame_i}", WARM_WHITE, wire_size=0.7, strength=glow_strength))
        lo = bpy.data.objects.new(f"L{frame_i}", lme); scene.collection.objects.link(lo)
        dec = lo.modifiers.new("Dec", "DECIMATE"); dec.ratio = min(1.0, 9000.0 / max(1, len(lf)))


# ---------------- compositions ----------------
if MODE == "tagmap":
    v = VIEWS[0]
    keep = (TAGS != 0)                       # hide enveloping shell -> reveal inner structures
    me = build("tagmap", v, FACES[keep], midx6[keep])
    for m in emit_mats: me.materials.append(m)
    ob = bpy.data.objects.new("tagmap", me); scene.collection.objects.link(ob)
    CAM_LOC = Vector((0.30, 0.06, 0.30)); CAM_TGT = Vector((0, 0, 0)); LENS = 42; FOCUS = 0.42; FSTOP = 64
elif MODE == "one":
    place(0, (0, 0, 0), glow_strength=5.0)
    CAM_LOC = Vector((0.0, 0.0, 0.42)); CAM_TGT = Vector((0.0, 0.0, 0.0)); LENS = 45; FOCUS = 0.42; FSTOP = 64
elif MODE == "expo":
    for i in range(10):
        place(i, (0, 0, 0), glass=False, glow_strength=3.5, wire_chambers=True, chamber_strength=1.5)  # luminous motion-cloud
    CAM_LOC = Vector((0.0, 0.0, 0.40)); CAM_TGT = Vector((0.0, 0.0, 0.0)); LENS = 45; FOCUS = 0.40; FSTOP = 64
else:  # ring  (clock of the cardiac cycle)
    Rr = 0.28
    for k in range(10):
        ang = math.pi / 2 - k * (2 * math.pi / 10)       # start at top (end-diastole), go clockwise
        off = (Rr * math.cos(ang), Rr * math.sin(ang), 0.0)
        place(k, off, glow_strength=(5.0 if k == 4 else 3.0))   # end-systole (frame 4) glows brightest
    CAM_LOC = Vector((0.0, 0.0, 1.05)); CAM_TGT = Vector((0.0, 0.0, 0.0)); LENS = 50; FOCUS = 1.05; FSTOP = 80

# camera
cd = bpy.data.cameras.new("C"); cd.lens = LENS; cd.sensor_fit = "VERTICAL"; cd.sensor_height = 36
cd.clip_start = 0.005; cd.clip_end = 100; cd.dof.use_dof = True; cd.dof.focus_distance = FOCUS; cd.dof.aperture_fstop = FSTOP
cam = bpy.data.objects.new("C", cd); cam.location = CAM_LOC
cam.rotation_euler = (CAM_TGT - CAM_LOC).to_track_quat("-Z", "Y").to_euler()
scene.collection.objects.link(cam); scene.camera = cam

# lights
for nm, loc, e, sz, col in [("K", (-0.3, 0.35, 0.5), 9, 1.4, (1.0, 0.93, 0.86)),
                            ("F", (0.4, -0.1, 0.5), 6, 1.4, (0.95, 0.97, 1.0)),
                            ("B", (0.0, 0.25, -0.4), 3, 0.8, (0.8, 0.86, 1.0))]:
    ld = bpy.data.lights.new(nm, "AREA"); ld.shape = "SQUARE"; ld.size = sz; ld.energy = e; ld.color = col
    o = bpy.data.objects.new(nm, ld); o.location = Vector(loc)
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)

world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.03, 0.03, 0.05, 1); bg.inputs["Strength"].default_value = 0.03

scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"
scene.cycles.samples = 48 if "test" in ARGS else 128
scene.cycles.use_denoising = True
scene.cycles.transmission_bounces = 16; scene.cycles.max_bounces = 24
scene.cycles.caustics_reflective = True; scene.cycles.caustics_refractive = True
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_depth = "8"
try:
    if MODE == "tagmap":
        scene.view_settings.view_transform = "Standard"
    else:
        scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - High Contrast"
except Exception: pass
scene.use_nodes = True
cn = scene.node_tree; cn.nodes.clear()
rl = cn.nodes.new("CompositorNodeRLayers"); cp = cn.nodes.new("CompositorNodeComposite")
if MODE == "tagmap":
    cn.links.new(rl.outputs["Image"], cp.inputs["Image"])
else:
    gl = cn.nodes.new("CompositorNodeGlare")
    gl.glare_type = "FOG_GLOW"; gl.quality = "HIGH"; gl.threshold = 1.0; gl.size = 7
    cn.links.new(rl.outputs["Image"], gl.inputs["Image"]); cn.links.new(gl.outputs["Image"], cp.inputs["Image"])
res = 700 if "test" in ARGS else 1500
scene.render.resolution_x = scene.render.resolution_y = res
scene.render.filepath = os.path.join(OUTDIR, f"beat - {MODE}.png")
print("Rendering ->", scene.render.filepath)
bpy.ops.render.render(write_still=True)
print("BEAT DONE:", MODE)
