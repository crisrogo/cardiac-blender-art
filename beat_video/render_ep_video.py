"""
EP video, stage 2: electrical activation spreading over the end-diastolic heart.

Static camera (anatomical anterior), no motion: the end-diastolic geometry
(frame_000_full.npz) coloured by the reaction-eikonal activation times that
prepare_ep.py wrote to <case>/ep_<sample>.npz.

Timeline of one beat (sim ms): atria activate from t=0, the ventricles from
t=AV_DELAY (the AT of every ventricular node is shifted by it). Each region is
coloured on its OWN scale (min..max of its ATs, CARTO order red -> purple), so
atria and ventricles each read as a full activation map.

Looks (STYLE):
  map   CARTO-style filling map: grey tissue takes its activation colour when the
        wave reaches it and keeps it, with dark isochrones every ISO_MS and a
        bright leading edge.
  wave  optical-mapping-like travelling front: a hot band with a fading tail on
        neutral tissue.
Finishes (FINISH): matte | glow | tissue.

Frames are rendered with a transparent film (RGBA) so compose_ep_video.py can
put the same render on black and on white and add the clock / colour bar.

    blender --background --factory-startup --python render_ep_video.py -- still <t_ms> [<t_ms> ...]
    blender --background --factory-startup --python render_ep_video.py -- beat
    MECH=1 SAMPLE=cycle532 STYLE=wave blender ... --python render_ep_video.py -- mech

`mech` shows EP AND contraction: the heart moves through every mechanics frame
(frame_NNN_full.npz, DT_FRAME ms apart, one cycle = n_frames * DT_FRAME) and the
activation times are those that drove that run, with the AV delay already in
them. The wave is evaluated modulo the cycle, so the atrial wave at the end of
one loop runs straight into the ventricles of the next. It plans a video
timeline at SLOW x slow motion in which the quiet diastasis (ventricles
relaxed -> atrial activation) plays in QUIET_S seconds, renders every distinct
time the timeline needs to raw_mech/t_NNNNN.png (0.1 ms keys) and writes it to
meta_mech.json for `compose_ep_video.py --mech`.

`arrhythmia` is an artificial, deliberately chaotic take on `mech`: the
contraction and the electrical wave run on independent random schedules (SEED).
Each contraction plays at a random rate, never slower than `mech`, and a wobble
inside the beat only ever speeds it up (MECH_RATE, WOBBLE). Each diastasis is no
longer than `mech`'s (GAP_S). The waves fire on their own schedule, at their own
fast speed and with their own random pauses (EP_RATE, EP_GAP_S), so they do not
pair up with the contractions. BEATS contractions are planned as one loop -> raw_arrhythmia/e<EP>_m<mech>.png +
meta_arrhythmia.json for `compose_ep_video.py --arrhythmia`. Not physiological.

Env:
    BEAT_DIR   case dir with topo.npz, frame_000_full.npz, ep_<SAMPLE>.npz
    SAMPLE     name of ep_<SAMPLE>.npz           (default 74)
    MECH       1 -> load every mechanics frame (needed by `mech`)
    DT_FRAME SLOW QUIET_S SHUTTER SUBSAMPLES LEAD_MS  mech timing (10 ms, 2x, 0.25 s, 1 frame, 9, 40 ms)
    OUT_DIR    output root                       (default <BEAT_DIR>/ep_<SAMPLE>)
    STYLE      map | wave                        (default map)
    FINISH     matte | glow | tissue             (default matte)
    AV_DELAY   ms between atrial and ventricular onset (default 100)
    MS_PER_FRAME  sim ms advanced per video frame (default 1.0 -> 33x slow at 30 fps)
    ISO_MS     isochrone spacing for STYLE=map   (default 10)
    RES SAMPLES TEST VALVE_TAGS LV_ENDO_TAG START_AZ CAM_ELEV   as in render_beat_video.py
"""
import bpy, bmesh, sys, os, math, json
import numpy as np
from mathutils import Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import orient as orientmod

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = (ARGS or ["still"])[0]
REST = ARGS[1:]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# absolute: Blender resolves a relative render filepath against the drive root, not the cwd
BEAT_DIR = os.path.abspath(os.environ.get("BEAT_DIR") or os.path.join(ROOT, "output", "beat_video", "case1"))
SAMPLE = os.environ.get("SAMPLE", "74")
MECH = os.environ.get("MECH", "0") == "1" or MODE in ("mech", "arrhythmia")
OUT_DIR = os.path.abspath(os.environ.get("OUT_DIR") or os.path.join(BEAT_DIR, f"ep_{SAMPLE}"))
STYLE = os.environ.get("STYLE", "map").lower()
FINISH = os.environ.get("FINISH", "matte").lower()
AV_DELAY = float(os.environ.get("AV_DELAY", "0" if MECH else "100"))   # mech ATs already hold it
MS_PER_FRAME = float(os.environ.get("MS_PER_FRAME", "1.0"))
ISO_MS = float(os.environ.get("ISO_MS", "10"))
TEST = os.environ.get("TEST", "0") == "1"
RES = int(os.environ.get("RES", "720" if TEST else "1080"))
SAMPLES = int(os.environ.get("SAMPLES", "16" if TEST else "64"))
VALVE_TAGS = [int(x) for x in os.environ.get("VALVE_TAGS", "7,8,9,10").split(",")]
LV_ENDO_TAG = int(os.environ.get("LV_ENDO_TAG", "25"))
START_AZ = float(os.environ.get("START_AZ", "180"))     # 180 = anatomical anterior
CAM_ELEV = float(os.environ.get("CAM_ELEV", "8"))
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------- data
topo = np.load(os.path.join(BEAT_DIR, "topo.npz"))
FACES = topo["faces"].astype(np.int32)
FACE_TAGS = topo["face_tags"].astype(np.int64)
P0 = np.load(os.path.join(BEAT_DIR, "frame_000_full.npz"))["points"].astype(np.float64)[topo["surf_vidx"]]
EP = np.load(os.path.join(BEAT_DIR, f"ep_{SAMPLE}.npz"))
AT = EP["at"].astype(np.float32)
REGION = EP["region"].astype(np.int32)
AT_RANGE = EP["at_range"]
END_MS = max(AT_RANGE[0, 1], AV_DELAY + AT_RANGE[1, 1])      # last activation of the beat
print(f"[ep] {len(P0)} verts, {len(FACES)} faces; atria {AT_RANGE[0]} ms, "
      f"ventricles {AT_RANGE[1]} ms (+{AV_DELAY} ms) -> beat ends at {END_MS:.1f} ms")

# orientation: anatomical, shared with the beat video (NO PCA — see orient.py)
_o = orientmod.compute_orientation(P0, FACES, FACE_TAGS, VALVE_TAGS, LV_ENDO_TAG)
R, gc = _o["R"], _o["gc"]
scale = 2.0 / float((P0 @ R.T)[:, 2].ptp())
VERTS = ((P0 - gc) @ R.T) * scale
FRAMES = [VERTS.astype(np.float32)]
DT_FRAME = float(os.environ.get("DT_FRAME", "10"))
if MECH:
    _ff = sorted(f for f in os.listdir(BEAT_DIR) if f.startswith("frame_") and f.endswith("_full.npz"))
    FRAMES = [(((np.load(os.path.join(BEAT_DIR, f))["points"].astype(np.float64)[topo["surf_vidx"]] - gc) @ R.T)
               * scale).astype(np.float32) for f in _ff]
CYCLE_MS = len(FRAMES) * DT_FRAME if MECH else 0.0
_allv = np.concatenate(FRAMES[::4], 0)                   # frame the whole motion, not just ED
bmin, bmax = _allv.min(0), _allv.max(0)
CENTER = Vector(tuple((bmin + bmax) / 2))
RADIUS = float(np.linalg.norm(_allv - (bmin + bmax) / 2, axis=1).max())
if MECH:
    print(f"[ep] mech: {len(FRAMES)} frames x {DT_FRAME} ms -> cycle {CYCLE_MS:.0f} ms")


def surface_gradient_norm():
    """|grad AT| per vertex (ms per world unit), area-weighted over its triangles.
    Lets the shader turn 'ms from an isochrone' into 'distance on the surface', so
    lines keep a constant width instead of smearing where activation is flat."""
    p = VERTS[FACES]; a = AT[FACES].astype(np.float64)
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    n = np.cross(e1, e2); n2 = (n * n).sum(1)
    ok = (n2 > 0) & (a >= 0).all(1)
    g = ((a[:, 1] - a[:, 0])[:, None] * np.cross(n, e2) + (a[:, 2] - a[:, 0])[:, None] * np.cross(e1, n))
    gn = np.where(ok, np.linalg.norm(g, axis=1) / np.where(ok, n2, 1.0), 0.0)
    w = np.where(ok, np.sqrt(n2), 0.0)
    num = np.zeros(len(VERTS)); den = np.zeros(len(VERTS))
    for k in range(3):
        np.add.at(num, FACES[:, k], gn * w); np.add.at(den, FACES[:, k], w)
    return (num / np.maximum(den, 1e-12)).astype(np.float32)


GRAD = surface_gradient_norm()
LINE_W = float(os.environ.get("LINE_W", "0.0045"))     # isochrone half-width, world units (heart = 2 tall)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ---------------------------------------------------------------- colour
def srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# CARTO order: earliest red -> orange -> yellow -> green -> blue -> latest purple (sRGB).
# compose_ep_video.py draws the colour bar from this same list.
CARTO = [(0.00, (0.80, 0.02, 0.04)), (0.18, (1.00, 0.42, 0.00)), (0.36, (1.00, 0.90, 0.05)),
         (0.54, (0.15, 0.78, 0.20)), (0.72, (0.05, 0.60, 0.95)), (0.86, (0.15, 0.20, 0.90)),
         (1.00, (0.55, 0.12, 0.72))]
HOT = [(0.00, (0.50, 0.03, 0.02)), (0.35, (0.95, 0.20, 0.02)), (0.70, (1.00, 0.75, 0.10)),
       (1.00, (1.00, 0.98, 0.85))]
REST_GREY = (0.46, 0.45, 0.44)          # myocardium the wave has not reached yet (sRGB)
TISSUE = (0.62, 0.22, 0.20)             # fresh-tissue base for FINISH=tissue (sRGB)
CONTEXT_GREY = (0.80, 0.80, 0.82)

CTRL = []      # every (T, K) Value-node pair: T = sim time (ms), K = map visibility (fade-out)


class G:
    """Tiny node-graph builder for scalar maths."""
    def __init__(self, nt):
        self.nt = nt

    def node(self, kind, **kw):
        n = self.nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def math(self, op, a, b=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = float(x)
            else:
                self.nt.links.new(x, n.inputs[i])
        return n.outputs[0]

    def value(self, name, v):
        n = self.node("ShaderNodeValue", name=name, label=name)
        n.outputs[0].default_value = v
        return n

    def ramp(self, fac, stops):
        n = self.node("ShaderNodeValToRGB")
        els = n.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for e, (pos, col) in zip(els, stops):
            e.position = pos
            e.color = (*srgb_to_lin(col), 1.0)
        self.nt.links.new(fac, n.inputs["Fac"])
        return n.outputs["Color"]

    def mix(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="RGBA")
        for sock, x in ((0, fac), (6, a), (7, b)):
            if isinstance(x, (tuple, list)):
                n.inputs[sock].default_value = (*srgb_to_lin(x), 1.0)
            elif isinstance(x, (int, float)):
                n.inputs[sock].default_value = float(x)
            else:
                self.nt.links.new(x, n.inputs[sock])
        return n.outputs[2]

    def smooth(self, x, lo, hi):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        n.inputs["From Min"].default_value = lo
        n.inputs["From Max"].default_value = hi
        self.nt.links.new(x, n.inputs["Value"])
        return n.outputs["Result"]


def _principled(nt):
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return b


def _set(b, name, val):
    if name in b.inputs:
        b.inputs[name].default_value = val


def make_ep_material(name, offset, a0, a1):
    """Activation material for one region. offset: ms added to its ATs (the AV
    delay for the ventricles); [a0, a1]: its own colour scale."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); g = G(nt)
    b = _principled(nt)
    T = g.value("T", -1.0).outputs[0]
    K = g.value("K", 1.0).outputs[0]
    CTRL.append((T.node, K.node))
    at = g.node("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="at").outputs["Fac"]
    grad = g.math("MAXIMUM", g.node("ShaderNodeAttribute", attribute_type="GEOMETRY",
                                    attribute_name="grad").outputs["Fac"], 1.0)

    since = g.math("SUBTRACT", T, g.math("ADD", at, offset))            # ms since this point activated
    if CYCLE_MS > 0:                                                    # periodic beat: time within the cycle
        since = g.math("FLOORED_MODULO", since, CYCLE_MS)
    active = g.smooth(since, -0.6, 0.6)                                 # 0 before, 1 after (soft 1 ms edge)
    u = g.math("DIVIDE", g.math("SUBTRACT", at, a0), max(1e-3, a1 - a0), clamp=True)
    rest = TISSUE if FINISH == "tissue" else REST_GREY

    if STYLE == "map":
        col = g.ramp(u, CARTO)
        # isochrones: distance to the nearest multiple of ISO_MS, in ms, then / |grad| -> surface distance
        ph = g.math("FRACT", g.math("ADD", g.math("DIVIDE", at, ISO_MS), 0.5))
        d = g.math("DIVIDE", g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", ph, 0.5)), ISO_MS), grad)
        line = g.math("SUBTRACT", 1.0, g.smooth(d, 0.5 * LINE_W, LINE_W))
        col = g.mix(g.math("MULTIPLY", line, 0.75), col, (0.02, 0.02, 0.02))
        # bright leading edge, a constant ~0.03-unit band just behind the front
        edge = g.math("MULTIPLY", active, g.math("EXPONENT", g.math("DIVIDE", g.math("DIVIDE", since, grad), -0.02)))
        col = g.mix(g.math("MULTIPLY", edge, 0.8), col, (1.0, 1.0, 1.0))
        vis = g.math("MULTIPLY", active, K)
        base = g.mix(vis, rest, col)
        glow_amt = vis
        glow_col = col
    else:  # wave: hot front with a fading tail (tau ~ 12 ms), tissue otherwise neutral
        inten = g.math("MULTIPLY", g.math("MULTIPLY", active, K),
                       g.math("EXPONENT", g.math("DIVIDE", g.math("MAXIMUM", since, 0.0), -12.0)))
        glow_col = g.ramp(inten, HOT)
        base = g.mix(g.math("POWER", inten, 0.6), rest, glow_col)
        glow_amt = inten

    if FINISH == "glow":
        dim = g.mix(0.8, base, (0.0, 0.0, 0.0))                        # dark body, light comes from emission
        nt.links.new(dim, b.inputs["Base Color"])
        nt.links.new(glow_col, b.inputs["Emission Color"])
        nt.links.new(g.math("MULTIPLY", glow_amt, 2.2), b.inputs["Emission Strength"])
        _set(b, "Roughness", 0.35); _set(b, "Coat Weight", 0.3)
    elif FINISH == "tissue":
        nt.links.new(base, b.inputs["Base Color"])
        _set(b, "Roughness", 0.34); _set(b, "Specular IOR Level", 0.6)
        _set(b, "Subsurface Weight", 0.15); _set(b, "Subsurface Radius", (0.34, 0.12, 0.08))
        _set(b, "Subsurface Scale", 0.08)
        _set(b, "Coat Weight", 0.3); _set(b, "Coat Roughness", 0.2)
        tex = g.node("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 7
        bp = g.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.12
        nt.links.new(tex.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
        if STYLE == "wave":
            nt.links.new(glow_col, b.inputs["Emission Color"])
            nt.links.new(g.math("MULTIPLY", glow_amt, 1.2), b.inputs["Emission Strength"])
    else:  # matte
        nt.links.new(base, b.inputs["Base Color"])
        _set(b, "Roughness", 0.55); _set(b, "Specular IOR Level", 0.35)
        if STYLE == "wave":
            nt.links.new(glow_col, b.inputs["Emission Color"])
            nt.links.new(g.math("MULTIPLY", glow_amt, 1.2), b.inputs["Emission Strength"])
    return m


def make_context_material():
    m = bpy.data.materials.new("Context"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b = _principled(nt)
    col = (0.10, 0.10, 0.11) if FINISH == "glow" else CONTEXT_GREY
    _set(b, "Base Color", (*srgb_to_lin(col), 1)); _set(b, "Roughness", 0.4)
    _set(b, "Alpha", 0.35)
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    return m


# ---------------------------------------------------------------- mesh
def build_heart():
    me = bpy.data.meshes.new("Heart")
    v = VERTS.astype(np.float32)
    me.vertices.add(len(v)); me.vertices.foreach_set("co", v.ravel())
    nf = len(FACES); me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", FACES.ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32))
    a = me.attributes.new("at", "FLOAT", "POINT"); a.data.foreach_set("value", AT)
    a = me.attributes.new("grad", "FLOAT", "POINT"); a.data.foreach_set("value", GRAD)
    # material slots: 0 = context (ghosted), 1 = atria, 2 = ventricles  (== REGION)
    me.polygons.foreach_set("material_index", REGION)
    me.materials.append(make_context_material())
    me.materials.append(make_ep_material("Atria", 0.0, *AT_RANGE[0]))
    me.materials.append(make_ep_material("Ventricles", AV_DELAY, *AT_RANGE[1]))
    me.update()
    ob = bpy.data.objects.new("Heart", me); scene.collection.objects.link(ob)
    return ob


HEART = build_heart()


def set_frame(t_ms):
    """Mechanics geometry at cycle time t (linear between frames, wrapping)."""
    f = (t_ms % CYCLE_MS) / DT_FRAME
    i = int(f) % len(FRAMES); j = (i + 1) % len(FRAMES); a = f - int(f)
    v = FRAMES[i] * (1 - a) + FRAMES[j] * a
    HEART.data.vertices.foreach_set("co", v.ravel()); HEART.data.update()


def set_time(t_ms, k=1.0):
    for T, K in CTRL:
        T.outputs[0].default_value = t_ms
        K.outputs[0].default_value = k


# ---------------------------------------------------------------- camera + lights (studio, as the beat video)
cam_d = bpy.data.cameras.new("C"); cam_d.lens = 70; cam_d.clip_start = 0.01; cam_d.clip_end = 100
cam = bpy.data.objects.new("C", cam_d); scene.collection.objects.link(cam); scene.camera = cam
_az, _el, _d = math.radians(START_AZ), math.radians(CAM_ELEV), RADIUS * 3.9
cam.location = Vector((CENTER.x + _d * math.cos(_el) * math.sin(_az),
                       CENTER.y - _d * math.cos(_el) * math.cos(_az),
                       CENTER.z + _d * math.sin(_el)))
cam.rotation_euler = (CENTER - cam.location).to_track_quat("-Z", "Y").to_euler()


def add_light(name, loc, energy, size, color):
    ld = bpy.data.lights.new(name, "AREA"); ld.shape = "SQUARE"; ld.size = size
    ld.energy = energy; ld.color = color
    o = bpy.data.objects.new(name, ld); o.location = Vector(loc)
    o.rotation_euler = (CENTER - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)


# the camera looks from +Y (anterior); keep the key in front so the colours stay readable
S = RADIUS
add_light("Key",  (CENTER.x - 2.2 * S, 2.6 * S, CENTER.z + 2.0 * S), 60 * S * S, 5.0 * S, (1.0, 0.98, 0.95))
add_light("Fill", (CENTER.x + 2.8 * S, 1.8 * S, CENTER.z + 0.3 * S), 26 * S * S, 6.0 * S, (0.95, 0.97, 1.0))
add_light("Rim",  (CENTER.x + 0.4 * S, -2.8 * S, CENTER.z + 1.8 * S), 50 * S * S, 4.0 * S, (1.0, 1.0, 1.0))
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (1, 1, 1, 1); bg.inputs["Strength"].default_value = 0.25

scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = SAMPLES
for attr in ("use_raytracing", "use_shadows", "use_gtao"):
    if hasattr(scene.eevee, attr):
        setattr(scene.eevee, attr, True)
scene.render.resolution_x = scene.render.resolution_y = RES
scene.render.film_transparent = True
scene.view_settings.view_transform = "Standard"       # keep the colour map true to the colour bar
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"


def render_to(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------- modes
TAG = f"{STYLE}_{FINISH}"
meta = dict(case=os.path.basename(os.path.normpath(BEAT_DIR)), sample=SAMPLE, style=STYLE, finish=FINISH,
            av_delay=AV_DELAY, ms_per_frame=MS_PER_FRAME, at_range=AT_RANGE.tolist(), end_ms=END_MS,
            carto=CARTO, params=json.loads(str(EP["params"])))

if MODE == "still":
    for t in (REST or ["60"]):
        set_time(float(t))
        if MECH:
            set_frame(float(t))
        render_to(os.path.join(OUT_DIR, "stills", f"{TAG}_el{int(CAM_ELEV):02d}_t{int(float(t)):03d}.png"))
elif MODE == "beat":
    # only the frames that change: t = -MS_PER_FRAME (rest) .. END_MS + a few ms for the
    # wave-style tail to die out. The hold / fade / repeat are assembled by the composer.
    tail = 60.0 if STYLE == "wave" else 6.0
    out = os.path.join(OUT_DIR, TAG, "raw")
    os.makedirs(out, exist_ok=True)
    n = int(math.ceil((END_MS + tail) / MS_PER_FRAME)) + 2
    f0 = int(os.environ.get("FRAME_FROM", "0"))
    f1 = int(os.environ.get("FRAME_TO", str(n - 1)))
    for i in range(f0, f1 + 1):
        t = (i - 1) * MS_PER_FRAME
        p = os.path.join(out, f"f_{i:04d}.png")
        if os.path.exists(p):
            continue
        set_time(t)
        render_to(p)
    if STYLE == "map":   # fade-out frames (map repolarises back to rest tissue)
        for j, k in enumerate(np.linspace(1.0, 0.0, 13)[1:]):
            p = os.path.join(out, f"fade_{j:02d}.png")
            if not os.path.exists(p):
                set_time(END_MS + tail, float(k)); render_to(p)
    meta["n_frames"] = n
    json.dump(meta, open(os.path.join(OUT_DIR, TAG, "meta.json"), "w"), indent=1)
    print(f"[ep] beat {TAG}: {n} frames -> {out}")
elif MODE in ("mech", "arrhythmia"):
    SLOW = float(os.environ.get("SLOW", "2"))
    QUIET_S = float(os.environ.get("QUIET_S", "0.25"))
    SHUTTER = float(os.environ.get("SHUTTER", "1.0"))
    LEAD = float(os.environ.get("LEAD_MS", "40"))
    NSUB = int(os.environ.get("SUBSAMPLES", "9" if MODE == "mech" else "5"))   # averaged per frame while a wave shows
    if MODE == "arrhythmia" and "SHUTTER" not in os.environ:
        SHUTTER = 0.5                                    # its waves are fast: a full-frame blur smears them
    TAIL = 60.0 if STYLE == "wave" else 6.0
    FPS = 30
    # ventricles relaxed = first frame after peak contraction where the median
    # ventricular surface-area change per frame drops below 0.12 %
    vf = FACES[REGION == 2]
    def _area(v):
        p = v[vf]; return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    a0 = _area(FRAMES[0])
    med = np.array([np.median(_area(v) / a0) for v in FRAMES])
    pk = int(med.argmin())
    t_wake = AT_RANGE[0, 0] - LEAD                       # a little before the atria fire
    plateau = med[int(t_wake // DT_FRAME)]
    rel = next((k for k in range(pk + 1, len(FRAMES) - 1)
                if med[k] >= med[pk] + 0.9 * (plateau - med[pk]) and med[k + 1] - med[k] < 0.0012), pk)
    t_relax = rel * DT_FRAME
    quiet = max(0.0, t_wake - t_relax)
    dtv = 1000.0 / (FPS * SLOW)

    def electrically_live(t):
        return any(((t - lo) % CYCLE_MS) <= (hi - lo) + TAIL for lo, hi in AT_RANGE)

if MODE == "arrhythmia":
    SEED = int(os.environ.get("SEED", "7"))
    rng = np.random.default_rng(SEED)
    NB = int(os.environ.get("BEATS", "10"))

    def span(name, default):
        lo, hi = (float(x) for x in os.environ.get(name, default).split(","))
        return lo, hi

    MR, ER = span("MECH_RATE", "1.0,2.5"), span("EP_RATE", "1.0,2.0")    # x the `mech` speed
    GAP, EGAP = span("GAP_S", f"0.1,{QUIET_S}"), span("EP_GAP_S", "0,0.5")
    WOB = float(os.environ.get("WOBBLE", "0.4"))
    act_len = CYCLE_MS - quiet                           # t_wake -> relaxed, in sim ms
    # mechanics clock: each beat at its own rate, wobbling only faster, then a random diastasis
    tm, mrate, starts, plan = [], [], [], []
    for b in range(NB):
        r = rng.uniform(*MR); ph = rng.uniform(0, 2 * np.pi); per = rng.uniform(0.4, 1.1) * FPS
        starts.append(len(tm)); x, k = 0.0, 0
        while x < act_len:
            step = dtv * r * (1 + WOB * (0.5 + 0.5 * math.sin(2 * math.pi * k / per + ph)))
            tm.append((t_wake + x) % CYCLE_MS); mrate.append(step); x += step; k += 1
        ng = max(3, int(round(rng.uniform(*GAP) * FPS)))  # never 0: the motion must not jump
        tm += [t_relax + quiet * (j + 0.5) / ng for j in range(ng)]; mrate += [quiet / ng] * ng
        plan.append(dict(mech_rate=round(r, 2), gap_frames=ng))
    N = len(tm)
    # EP clock, independent of the contractions: at rest (t_relax: nothing fires)
    # except while a wave runs; waves follow each other after random pauses and
    # stop where the next one would not finish inside the loop
    ep_len = (CYCLE_MS - t_wake) + AT_RANGE[1, 1] + TAIL
    te, erate, waves = [t_relax] * N, [0.0] * N, []
    e0 = int(round(rng.uniform(*EGAP) * FPS))
    while True:
        r = rng.uniform(*ER)
        n = int(math.ceil(ep_len / (dtv * r)))
        if e0 + n > N:
            break
        for j in range(n):
            te[e0 + j] = (t_wake + j * dtv * r) % CYCLE_MS; erate[e0 + j] = dtv * r
        waves.append(dict(start=e0, frames=n, ep_rate=round(r, 2)))
        e0 += n + int(round(rng.uniform(*EGAP) * FPS))

    timeline, jobs = [], {}
    for k in range(N):
        live = erate[k] > 0 and electrically_live(te[k])
        fr = []
        for j in (range(NSUB) if live else range(1)):
            a = SHUTTER * j / max(1, NSUB - 1)
            e = (te[k] - a * erate[k]) % CYCLE_MS; m = (tm[k] - a * mrate[k]) % CYCLE_MS
            name = f"e{int(round(e * 10)):05d}_m{int(round(m * 10)):05d}"
            jobs[name] = (e, m); fr.append(name)
        timeline.append(fr)
    out = os.path.join(OUT_DIR, TAG, "raw_arrhythmia")
    os.makedirs(out, exist_ok=True)
    print(f"[ep] arrhythmia seed {SEED}: {NB} contractions, {len(waves)} waves, {N} video frames "
          f"({N / FPS:.1f} s), {len(jobs)} renders", flush=True)
    print("    contractions:", plan, "\n    waves:", waves, flush=True)
    for name, (e, m) in sorted(jobs.items()):
        p = os.path.join(out, name + ".png")
        if os.path.exists(p):
            continue
        set_frame(m); set_time(e)
        render_to(p)
    meta.update(cycle_ms=CYCLE_MS, dt_frame=DT_FRAME, slow=SLOW, seed=SEED, beats=plan, waves=waves,
                timeline=timeline, fps=FPS)
    json.dump(meta, open(os.path.join(OUT_DIR, TAG, "meta_arrhythmia.json"), "w"))
elif MODE == "mech":
    # the loop starts just before atrial activation and ends in the compressed diastasis
    n_act = int(round((CYCLE_MS - quiet) / dtv))
    times = [(t_wake + k * dtv) % CYCLE_MS for k in range(n_act)]
    n_q = max(1, int(round(QUIET_S * FPS))) if quiet > 0 else 0
    times += [t_relax + quiet * (k + 0.5) / n_q for k in range(n_q)]

    timeline = []
    for k, t in enumerate(times):
        if k < n_act and electrically_live(t):         # motion blur while a wave is visible
            sub = [t - SHUTTER * dtv * j / max(1, NSUB - 1) for j in range(NSUB)]
        else:
            sub = [t]
        timeline.append([int(round((x % CYCLE_MS) * 10)) for x in sub])
    keys = sorted({x for fr in timeline for x in fr})
    out = os.path.join(OUT_DIR, TAG, "raw_mech")
    os.makedirs(out, exist_ok=True)
    print(f"[ep] mech: relaxed at {t_relax:.0f} ms, atria at {AT_RANGE[0, 0]:.0f} ms -> {quiet:.0f} ms of "
          f"diastasis in {n_q} frames; {len(timeline)} video frames/beat, {len(keys)} renders")
    for key in keys:
        p = os.path.join(out, f"t_{key:05d}.png")
        if os.path.exists(p):
            continue
        set_frame(key / 10.0); set_time(key / 10.0)
        render_to(p)
    meta.update(cycle_ms=CYCLE_MS, dt_frame=DT_FRAME, slow=SLOW, quiet_ms=quiet, t_relax=t_relax,
                timeline=timeline, fps=FPS)
    json.dump(meta, open(os.path.join(OUT_DIR, TAG, "meta_mech.json"), "w"))
else:
    raise SystemExit(f"unknown mode {MODE}")
json.dump(meta, open(os.path.join(OUT_DIR, f"meta_{TAG}.json"), "w"), indent=1)
