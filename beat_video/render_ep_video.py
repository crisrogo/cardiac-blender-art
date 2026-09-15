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

Env:
    BEAT_DIR   case dir with topo.npz, frame_000_full.npz, ep_<SAMPLE>.npz
    SAMPLE     EP sample id                      (default 74)
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
SAMPLE = int(os.environ.get("SAMPLE", "74"))
OUT_DIR = os.path.abspath(os.environ.get("OUT_DIR") or os.path.join(BEAT_DIR, f"ep_{SAMPLE}"))
STYLE = os.environ.get("STYLE", "map").lower()
FINISH = os.environ.get("FINISH", "matte").lower()
AV_DELAY = float(os.environ.get("AV_DELAY", "100"))
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
bmin, bmax = VERTS.min(0), VERTS.max(0)
CENTER = Vector(tuple((bmin + bmax) / 2))
RADIUS = float(np.linalg.norm(VERTS - (bmin + bmax) / 2, axis=1).max())


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
else:
    raise SystemExit(f"unknown mode {MODE}")
json.dump(meta, open(os.path.join(OUT_DIR, f"meta_{TAG}.json"), "w"), indent=1)
