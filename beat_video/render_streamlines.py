"""
Render myofiber streamlines as glowing tubes (coloured by apex->base height) over a
fleshy-red ghosted heart, using the shared anatomical orientation.

    blender --background --factory-startup --python render_streamlines.py -- <view> <coverage> [every] [radius]
      view      anterior | posterior | roof        (default anterior)
      coverage  ventricles | atria | all           (default all)  -> streamlines_<coverage>.npz
      every     keep 1 of every N tracts           (default 3)
      radius    tube radius in Blender units        (default 0.006)
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import orient as orientmod

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
VIEW = ARGS[0] if len(ARGS) > 0 else "anterior"
COV = ARGS[1] if len(ARGS) > 1 else "all"
EVERY = int(ARGS[2]) if len(ARGS) > 2 else 3
RADIUS_T = float(ARGS[3]) if len(ARGS) > 3 else 0.006
RES = int(os.environ.get("RES", "1000"))
SAMPLES = int(os.environ.get("SAMPLES", "48"))
HEART_ALPHA = float(os.environ.get("HEART_ALPHA", "0.5"))    # uniform wall opacity (alpha, not refractive)
HEART_ROUGH = float(os.environ.get("HEART_ROUGH", "0.45"))
FIB_EMIT = float(os.environ.get("FIB_EMIT", "1.6"))          # flat fibre glow (attenuated ~alpha by the wall)
GLARE_THRESH = float(os.environ.get("GLARE_THRESH", "1.6"))  # minimal bloom
GLARE_SIZE = int(os.environ.get("GLARE_SIZE", "3"))
GLARE_MIX = float(os.environ.get("GLARE_MIX", "-0.7"))
FIB_INSET = float(os.environ.get("FIB_INSET", "0.985"))      # slight inward nudge (behind outer wall, but transmural)
VIEWS = {"anterior": (180.0, 8.0), "posterior": (0.0, 8.0), "roof": (180.0, 78.0)}
AZ, EL = VIEWS.get(VIEW, VIEWS["anterior"])

HERE = os.path.dirname(os.path.abspath(__file__))
BEAT = os.path.join(os.path.dirname(HERE), "output", "beat_video", "case1")
topo = np.load(os.path.join(BEAT, "topo.npz"))
FACES = topo["faces"].astype(np.int32); FTAGS = topo["face_tags"].astype(np.int64); SVIDX = topo["surf_vidx"]
FULL0 = np.load(os.path.join(BEAT, "frame_000_full.npz"))["points"].astype(np.float64)
P_surf = FULL0[SVIDX]
o = orientmod.compute_orientation(P_surf, FACES, FTAGS)
R, gc = o["R"], o["gc"]
Vs = (P_surf - gc) @ R.T
TARGET = 2.0; scale = TARGET / float(Vs[:, 2].ptp())
allv = Vs * scale
bmin, bmax = allv.min(0), allv.max(0)
CENTER = Vector(tuple((bmin + bmax) / 2)); RADIUS = float(np.linalg.norm(allv - (bmin + bmax) / 2, axis=1).max())


def W(p):
    return (p - gc) @ R.T * scale


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---- streamlines -> bevelled tube curve ----
sl = np.load(os.path.join(BEAT, f"streamlines_{COV}.npz"))
pts = W(sl["points"].astype(np.float64)).astype(np.float32)
_c = np.array([CENTER.x, CENTER.y, CENTER.z], np.float32)
pts = (_c + (pts - _c) * FIB_INSET).astype(np.float32)       # inset -> tracts within the wall
offs = sl["offsets"]
z0, z1 = float(allv[:, 2].min()), float(allv[:, 2].max())     # apex..base for the gradient
cu = bpy.data.curves.new("Fibres", 'CURVE'); cu.dimensions = '3D'
cu.bevel_depth = RADIUS_T; cu.bevel_resolution = 1; cu.use_fill_caps = True
n_used = 0
for l in range(0, len(offs) - 1, EVERY):
    a, b = offs[l], offs[l + 1]
    if b - a < 2:
        continue
    sp = cu.splines.new('POLY'); sp.points.add(b - a - 1)
    co = np.ones((b - a, 4), np.float32); co[:, :3] = pts[a:b]
    sp.points.foreach_set("co", co.ravel()); n_used += 1
print(f"[fibres] {COV}/{VIEW}: {n_used} tracts, radius {RADIUS_T}")

# fibre material: PURE flat emission (view/light-independent) coloured by apex->base Z
fm = bpy.data.materials.new("Fib"); fm.use_nodes = True
nt = fm.node_tree; nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = z0; mr.inputs["From Max"].default_value = z1
nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
ramp = nt.nodes.new("ShaderNodeValToRGB")
e = ramp.color_ramp.elements
e[0].position = 0.0; e[0].color = (0.12, 0.10, 0.78, 1)          # apex  = blue-violet
e[1].position = 1.0; e[1].color = (0.98, 0.72, 0.14, 1)          # base  = gold
em = ramp.color_ramp.elements.new(0.5); em.color = (0.10, 0.70, 0.55, 1)   # mid = teal
nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
emn = nt.nodes.new("ShaderNodeEmission")
nt.links.new(ramp.outputs["Color"], emn.inputs["Color"])
# per-tube shading so strands separate: bright down the facing centre, dark at the
# grazing edges -> dark grooves between adjacent tubes (view-relative, not scene-lit).
lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.35
fm1 = nt.nodes.new("ShaderNodeMath"); fm1.operation = 'MULTIPLY'; fm1.inputs[1].default_value = 0.85
nt.links.new(lw.outputs["Facing"], fm1.inputs[0])
fa1 = nt.nodes.new("ShaderNodeMath"); fa1.operation = 'ADD'; fa1.inputs[1].default_value = 0.15
nt.links.new(fm1.outputs["Value"], fa1.inputs[0])
fm2 = nt.nodes.new("ShaderNodeMath"); fm2.operation = 'MULTIPLY'; fm2.inputs[1].default_value = FIB_EMIT
nt.links.new(fa1.outputs["Value"], fm2.inputs[0])
nt.links.new(fm2.outputs["Value"], emn.inputs["Strength"])
nt.links.new(emn.outputs["Emission"], out.inputs["Surface"])
cu.materials.append(fm)
fob = bpy.data.objects.new("Fibres", cu); scene.collection.objects.link(fob)

# ---- fleshy-red ghosted heart for context ----
me = bpy.data.meshes.new("Heart"); v = allv.astype(np.float32)
me.vertices.add(len(v)); me.vertices.foreach_set("co", v.ravel())
nf = len(FACES); me.loops.add(nf * 3); me.polygons.add(nf)
me.loops.foreach_set("vertex_index", FACES.ravel())
me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
me.update(calc_edges=True)
bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # fix winding
bm.to_mesh(me); bm.free()
me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32)); me.update()
gm = bpy.data.materials.new("Flesh"); gm.use_nodes = True
gnt = gm.node_tree; gnt.nodes.clear()
go = gnt.nodes.new("ShaderNodeOutputMaterial"); gb = gnt.nodes.new("ShaderNodeBsdfPrincipled")
gb.inputs["Base Color"].default_value = (0.55, 0.06, 0.05, 1); gb.inputs["Roughness"].default_value = HEART_ROUGH
# uniform alpha (one wall-crossing) -> fibres attenuate evenly regardless of wall thickness
gb.inputs["Alpha"].default_value = HEART_ALPHA
gnt.links.new(gb.outputs["BSDF"], go.inputs["Surface"])
me.materials.append(gm)
hob = bpy.data.objects.new("Heart", me); scene.collection.objects.link(hob)

# ---- camera + lights + dark world ----
cam_d = bpy.data.cameras.new("C"); cam_d.lens = 72
cam = bpy.data.objects.new("C", cam_d); scene.collection.objects.link(cam); scene.camera = cam
D = RADIUS * 3.4; el = math.radians(EL); az = math.radians(AZ)
loc = Vector((CENTER.x + D * math.cos(el) * math.sin(az), CENTER.y - D * math.cos(el) * math.cos(az), CENTER.z + D * math.sin(el)))
cam.location = loc; cam.rotation_euler = (CENTER - loc).to_track_quat("-Z", "Y").to_euler()
for nm, ll, en, sz, col in [("K", (-2.2, -2.4, 2.2), 60, 4.0, (1, 0.97, 0.9)),
                            ("F", (2.6, -1.4, 0.5), 25, 5.0, (0.9, 0.95, 1)),
                            ("R", (0.3, 2.6, 1.6), 70, 3.0, (1, 0.92, 0.86))]:
    ld = bpy.data.lights.new(nm, "AREA"); ld.energy = en * RADIUS * RADIUS; ld.size = sz * RADIUS
    lo = bpy.data.objects.new(nm, ld); lo.location = CENTER + Vector(ll) * RADIUS
    lo.rotation_euler = (CENTER - lo.location).to_track_quat("-Z", "Y").to_euler(); scene.collection.objects.link(lo)
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bgn = world.node_tree.nodes.get("Background")
bgn.inputs["Color"].default_value = (0.01, 0.01, 0.012, 1); bgn.inputs["Strength"].default_value = 0.15

scene.render.engine = "CYCLES"
if not list(bpy.context.preferences.addons["cycles"].preferences.bl_rna.properties["compute_device_type"].enum_items.keys()):
    scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
try:
    scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.render.resolution_x = scene.render.resolution_y = RES
scene.render.image_settings.file_format = "PNG"
# fog-glow bloom so the emissive fibres visibly glow
scene.use_nodes = True
cn = scene.node_tree; cn.nodes.clear()
rl = cn.nodes.new("CompositorNodeRLayers"); cp = cn.nodes.new("CompositorNodeComposite")
gl = cn.nodes.new("CompositorNodeGlare"); gl.glare_type = 'FOG_GLOW'; gl.quality = 'HIGH'
gl.threshold = GLARE_THRESH; gl.size = GLARE_SIZE
try: gl.mix = GLARE_MIX
except Exception: pass
cn.links.new(rl.outputs["Image"], gl.inputs["Image"]); cn.links.new(gl.outputs["Image"], cp.inputs["Image"])
scene.render.filepath = os.path.join(BEAT, f"fibres_{COV}_{VIEW}.png")
bpy.ops.render.render(write_still=True)
print("STREAMLINES DONE ->", scene.render.filepath)
