"""
Realism video: the beating heart as a wet specimen lying on a dark studio table,
in "the realistic look" (realistic_look.py).

Only what the data holds is drawn: the outer surface of the mechanics mesh, its
own motion (frame_NNN_full.npz), its tags (myocardium / great vessels / inner
surfaces) and, when <case>/fibres.npz exists, the real myofibre directions from
the .lon file, which orient the sheen and the fine striations of the muscle.
Without fibres.npz the tissue has neither (no synthetic fibre field is made up).

Staging: the heart lies on its posterior wall, anterior face up (RECLINE=90), and
the camera looks down on it from just past the vertical, over the base
(CAM_ELEV=100), so the whole anterior surface and the atria show and the apex is
foreshortened; apex at the bottom of the frame as in the other videos.
Every frame the heart is translated (rigidly, its shape untouched) so its lowest
point touches the table. The camera never moves, so one cycle loops seamlessly.

    blender --background --factory-startup --python render_realism.py -- still [t01 ...]
    blender --background --factory-startup --python render_realism.py -- beat

`still` writes <OUT>/stills/<tag>_tNNN.png (t01 = phase of the cycle, 0..1).
`beat` renders one cycle, FPS x cycle length x SLOW frames, to <OUT>/<tag>/f_NNNN.png
(existing frames are skipped). The cycle is n_frames x DT_FRAME ms of mechanics.

Env:
    BEAT_DIR   case dir (topo.npz, frame_NNN_full.npz, optional fibres.npz)
    OUT_DIR    output root                                     (default <BEAT_DIR>/realism)
    ROLL RECLINE    heart pose, degrees: roll about the anterior axis, then
                    recline backwards (90 = lying on the posterior wall)  (default 0, 90)
    CAM_AZ CAM_ELEV camera, degrees; az 180 = anterior side, elev > 90 = past
                    the vertical, over the base               (default 180, 100)
    LENS FILL       focal length (mm), heart extent / frame     (default 85, 0.78)
    FSTOP           depth of field, 0 = off                    (default 8)
    STRIATE         fibre striation bump strength, 0 = off     (default 0.3)
    LIGHT_SCALE     multiplies every light                     (default 1)
    RES_X RES_Y SAMPLES TEST   (default 1920 x 1080, 128 spp; TEST=1 -> 960 x 540, 32 spp)
    FPS SLOW DT_FRAME          (default 30, 1.0 = real time, 10 ms)
    MAX_FRAMES  load only the first N mechanics frames (stills)
    TAG         output name                                    (default from the pose)
    VALVE_TAGS LV_ENDO_TAG     as in render_beat_video.py
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector, Matrix

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import orient as orientmod
import realistic_look as look

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = (ARGS or ["still"])[0]
REST = ARGS[1:]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# absolute: Blender resolves a relative render filepath against the drive root, not the cwd
BEAT_DIR = os.path.abspath(os.environ.get("BEAT_DIR") or os.path.join(ROOT, "output", "beat_video", "case1"))
OUT_DIR = os.path.abspath(os.environ.get("OUT_DIR") or os.path.join(BEAT_DIR, "realism"))
TEST = os.environ.get("TEST", "0") == "1"
RES_X = int(os.environ.get("RES_X", "960" if TEST else "1920"))
RES_Y = int(os.environ.get("RES_Y", "540" if TEST else "1080"))
SAMPLES = int(os.environ.get("SAMPLES", "32" if TEST else "128"))
FPS = int(os.environ.get("FPS", "30"))
SLOW = float(os.environ.get("SLOW", "1.0"))
DT_FRAME = float(os.environ.get("DT_FRAME", "10"))
ROLL = float(os.environ.get("ROLL", "0"))
RECLINE = float(os.environ.get("RECLINE", "90"))
CAM_AZ = float(os.environ.get("CAM_AZ", "180"))
CAM_ELEV = float(os.environ.get("CAM_ELEV", "100"))
LENS = float(os.environ.get("LENS", "85"))
FILL = float(os.environ.get("FILL", "0.78"))
FSTOP = float(os.environ.get("FSTOP", "8"))
STRIATE = float(os.environ.get("STRIATE", "0.3"))
LIGHT_SCALE = float(os.environ.get("LIGHT_SCALE", "1.0"))
VALVE_TAGS = [int(x) for x in os.environ.get("VALVE_TAGS", "7,8,9,10").split(",")]
LV_ENDO_TAG = int(os.environ.get("LV_ENDO_TAG", "25"))
TAG = os.environ.get("TAG", f"r{int(ROLL)}_c{int(RECLINE)}_az{int(CAM_AZ)}_el{int(CAM_ELEV)}")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------- data
topo = np.load(os.path.join(BEAT_DIR, "topo.npz"))
FACES = topo["faces"].astype(np.int32)
FACE_TAGS = topo["face_tags"].astype(np.int64)
SV = topo["surf_vidx"]
_ff = sorted(f for f in os.listdir(BEAT_DIR) if f.startswith("frame_") and f.endswith("_full.npz"))
_maxf = int(os.environ.get("MAX_FRAMES", "0"))
if _maxf > 0:
    _ff = _ff[:_maxf]
RAW = [np.load(os.path.join(BEAT_DIR, f))["points"][SV].astype(np.float64) for f in _ff]
K = len(RAW)
CYCLE_MS = K * DT_FRAME

# orientation: anatomical, shared with the other videos (NO PCA — see orient.py)
_o = orientmod.compute_orientation(RAW[0], FACES, FACE_TAGS, VALVE_TAGS, LV_ENDO_TAG)
R, gc = _o["R"], _o["gc"]
scale = 2.0 / float(np.ptp((RAW[0] @ R.T)[:, 2]))
WORLD = [((p - gc) @ R.T) * scale for p in RAW]          # X right, Y anterior, Z up (apex down)
print(f"[realism] {K} frames ({CYCLE_MS:.0f} ms cycle), {len(SV)} verts, {len(FACES)} faces")

_fp = os.path.join(BEAT_DIR, "fibres.npz")
FIBRES = np.load(_fp)["surf_fiber"].astype(np.float64) @ R.T if (
    os.path.exists(_fp) and "surf_fiber" in np.load(_fp)) else None
print(f"[realism] myofibres: {'fibres.npz' if FIBRES is not None else 'none -> no sheen, no striations'}")


def _rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])  # y


# pose: roll about the anterior axis, then recline backwards (90 -> anterior face up, apex toward the camera side)
POSE = _rot("x", RECLINE) @ _rot("y", ROLL)
PC = WORLD[0].mean(0)


def posed(w):
    """World-frame points -> posed, translated so the lowest point is on the table (z=0)."""
    q = (w - PC) @ POSE.T
    q[:, 2] -= q[:, 2].min()
    return q


# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def mat_table():
    """Dark lacquered table: near-black, glossy, with a faint large-scale roughness drift."""
    m = bpy.data.materials.new("Table"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = look.srgb((0.012, 0.012, 0.014))
    b.inputs["Specular IOR Level"].default_value = 0.10
    tc = nt.nodes.new("ShaderNodeTexCoord")
    r = nt.nodes.new("ShaderNodeMapRange")
    r.inputs["To Min"].default_value = 0.30; r.inputs["To Max"].default_value = 0.45
    nt.links.new(look._noise(nt, 0.35, detail=2.0, vec=tc.outputs["Object"]), r.inputs["Value"])
    nt.links.new(r.outputs["Result"], b.inputs["Roughness"])
    return m


def build_heart():
    v0 = posed(WORLD[0])
    me = bpy.data.meshes.new("Heart")
    me.vertices.add(len(v0)); me.vertices.foreach_set("co", v0.astype(np.float32).ravel())
    nf = len(FACES); me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", FACES.ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32))
    # slots: 0 myocardium (atria + ventricles), 1 great vessels, 2 everything else (valve planes, inner surfaces)
    slot = np.full(nf, 2, np.int32)
    slot[np.isin(FACE_TAGS, look.MYO_TAGS)] = 0
    slot[np.isin(FACE_TAGS, look.VESSEL_TAGS)] = 1
    me.polygons.foreach_set("material_index", slot)
    fib = FIBRES is not None
    me.materials.append(look.make_specimen("Myocardium", look.MYOCARDIUM, fib, striate=STRIATE))
    me.materials.append(look.make_specimen("Vessels", look.VESSELS, fib, sss=0.15, muscle=False))
    me.materials.append(look.make_specimen("Inner", look.INNER, fib, sss=0.3, muscle=False))
    look.add_attributes(me, v0, FIBRES @ POSE.T if fib else None)
    me.update()
    ob = bpy.data.objects.new("Heart", me); scene.collection.objects.link(ob)
    return ob


HEART = build_heart()


def set_phase(t01):
    """The heart at cycle phase t01 (linear between mechanics frames, wrapping)."""
    f = (t01 % 1.0) * K
    i = int(f) % K; j = (i + 1) % K; a = f - int(f)
    v = posed(WORLD[i] * (1 - a) + WORLD[j] * a)
    HEART.data.vertices.foreach_set("co", v.astype(np.float32).ravel()); HEART.data.update()


# ---------------------------------------------------------------- stage: table, camera, lights
_allp = np.concatenate([posed(w) for w in WORLD[::max(1, K // 12)]])
BMIN, BMAX = _allp.min(0), _allp.max(0)
CENTER = Vector(tuple((BMIN + BMAX) / 2))
SIZE = float(np.linalg.norm(BMAX - BMIN))

bpy.ops.mesh.primitive_plane_add(size=60 * SIZE, location=(CENTER.x, CENTER.y, 0.0))
bpy.context.active_object.name = "Table"
bpy.context.active_object.data.materials.append(mat_table())

cam_d = bpy.data.cameras.new("C"); cam_d.lens = LENS; cam_d.sensor_fit = "HORIZONTAL"
cam_d.clip_start = 0.01; cam_d.clip_end = 500
cam = bpy.data.objects.new("C", cam_d); scene.collection.objects.link(cam); scene.camera = cam
_az, _el = math.radians(CAM_AZ), math.radians(CAM_ELEV)
# CAM_ELEV may pass 90: the camera then goes over the top, to the base side
CAM_DIR = Vector((math.cos(_el) * math.sin(_az), -math.cos(_el) * math.cos(_az), math.sin(_el)))
# image up = apex -> base, as in the other videos (explicit, so it holds through the vertical)
_fwd = -CAM_DIR
_right = _fwd.cross(Vector(tuple(POSE @ np.array([0.0, 0.0, 1.0]))).normalized()).normalized()
_up = _right.cross(_fwd).normalized()
# distance: the heart's extent along the camera's right and up axes fills FILL of the frame
_tx = cam_d.sensor_width / (2 * LENS)
_ty = _tx * RES_Y / RES_X
DIST = max(float(np.ptp(_allp @ np.array(_right))) / (2 * FILL * _tx),
           float(np.ptp(_allp @ np.array(_up))) / (2 * FILL * _ty))
cam.location = CENTER + CAM_DIR * DIST
cam.rotation_euler = Matrix((_right, _up, CAM_DIR)).transposed().to_euler()
if FSTOP > 0:
    cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = FSTOP
    cam_d.dof.focus_distance = DIST - 0.15 * SIZE                     # the near (anterior) wall

look.soft_rig(scene, CENTER, SIZE, cam, LIGHT_SCALE)
look.setup_cycles(scene, SAMPLES)
scene.render.resolution_x, scene.render.resolution_y = RES_X, RES_Y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"


def render_to(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------- modes
if MODE == "still":
    for t in (REST or ["0.0"]):
        set_phase(float(t))
        render_to(os.path.join(OUT_DIR, "stills", f"{TAG}_t{int(round(float(t) * 100)):03d}.png"))
elif MODE == "beat":
    n = int(round(FPS * CYCLE_MS / 1000.0 * SLOW))
    out = os.path.join(OUT_DIR, TAG)
    os.makedirs(out, exist_ok=True)
    print(f"[realism] beat: {n} frames for one {CYCLE_MS:.0f} ms cycle at {SLOW}x -> {out}")
    for i in range(n):
        p = os.path.join(out, f"f_{i:04d}.png")
        if os.path.exists(p):
            continue
        set_phase(i / n)
        render_to(p)
else:
    raise SystemExit(f"unknown mode {MODE}")
