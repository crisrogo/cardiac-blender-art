"""
HCM beating-heart pipeline, stage 2: Blender render of the surface npz frames.

Lives in its own `beat_video/` directory (different visualisation type from the
glass-art stills -> kept separate for reproducibility).

>>> WORKFLOW RULE (do not remove): the user's visual inspection is the ground
>>> truth. This code/agent does NOT decide whether a render's orientation, the
>>> anterior face, or the look is correct. Always render, show the user, and
>>> WAIT for an explicit green light before proceeding to the next step. <<<

ORIENTATION — PCA IS BANNED. A previous version used PCA (max-variance axis) to
find the apex-base axis; it FAILED because the heart (with atria + great vessels)
is too globular and its max-variance axis is not the anatomical long axis. Do not
reintroduce PCA. Instead, orientation is anatomical, from the elemTags:
  * valve barycentres (mitral/tricuspid/aortic/pulmonary) give the basal plane,
  * apex = the LV-endocardium point farthest from the mitral-valve barycentre,
  * apex-base (up) axis = from that apex up to the valve-plane centroid (apex
    down), and the valve plane + pulmonary-valve position orient the anterior.
Tag numbers are case-specific; (re)identify them with identify_tags.py.

Run with Blender 4.5:
    blender --background --factory-startup --python render_beat_video.py -- <mode> [opts]

Modes:  turntable | still [az] [fi] | video        (see env vars below)

Env:
    BEAT_DIR  dir with topo.npz + frame_XX.npz   (default <repo>/output/beat_video/case1)
    OUT_DIR   render output root                 (default = BEAT_DIR)
    ENGINE    EEVEE | CYCLES                      (default EEVEE)
    START_AZ  starting azimuth deg               (default 0 = anatomical anterior toward camera)
    VALVE_TAGS  "mitral,tricuspid,aortic,pulmonary" tag ints (default 7,8,9,10)
    LV_ENDO_TAG int                              (default 25)
    FPS ORBIT_SECONDS BEATS RES SAMPLES TEST     (video tunables)
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import orient as orientmod

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = (ARGS or ["turntable"])[0]
REST = ARGS[1:]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BEAT_DIR = os.environ.get("BEAT_DIR") or os.path.join(ROOT, "output", "beat_video", "case1")
OUT_DIR = os.environ.get("OUT_DIR") or BEAT_DIR
ENGINE = os.environ.get("ENGINE", "EEVEE").upper()
START_AZ = float(os.environ.get("START_AZ", "180"))   # az180 = anterior (user-confirmed start)
MATERIAL = os.environ.get("MATERIAL", "realistic_fresh")
TEST = os.environ.get("TEST", "0") == "1"
FPS = int(os.environ.get("FPS", "30"))
ORBIT_SECONDS = float(os.environ.get("ORBIT_SECONDS", "12"))
BEATS = float(os.environ.get("BEATS", "10"))
RES = int(os.environ.get("RES", "720" if TEST else "1080"))
SAMPLES = int(os.environ.get("SAMPLES", "16" if TEST else "64"))
VALVE_TAGS = [int(x) for x in os.environ.get("VALVE_TAGS", "7,8,9,10").split(",")]
LV_ENDO_TAG = int(os.environ.get("LV_ENDO_TAG", "25"))
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------- load frames
# Each frame is stored as the FULL point array (frame_*_full.npz); the outer
# surface and the cross-section are both derived from it via topo / topo_cut.
topo = np.load(os.path.join(BEAT_DIR, "topo.npz"))
FACES = topo["faces"].astype(np.int32)
FACE_TAGS = topo["face_tags"].astype(np.int64)
SURF_VIDX = topo["surf_vidx"]
full_files = sorted(f for f in os.listdir(BEAT_DIR) if f.startswith("frame_") and f.endswith("_full.npz"))
_maxf = int(os.environ.get("MAX_FRAMES", "0"))         # cap frames loaded (still modes only need 1)
if _maxf > 0:
    full_files = full_files[:_maxf]
FULL = [np.load(os.path.join(BEAT_DIR, f))["points"].astype(np.float64) for f in full_files]
RAW = [p[SURF_VIDX] for p in FULL]                 # outer-surface points per frame
K = len(RAW)
print(f"[render] {K} frames, {len(RAW[0])} surf verts, {len(FACES)} faces, engine={ENGINE}")


# ---------------------------------------- orientation (anatomical; NO PCA, see header)
def tag_verts(tg):
    return np.unique(FACES[FACE_TAGS == tg])


P0 = RAW[0]
_o = orientmod.compute_orientation(P0, FACES, FACE_TAGS, VALVE_TAGS, LV_ENDO_TAG)
R, gc, BASE, APEX = _o["R"], _o["gc"], _o["base"], _o["apex"]
# diagnostics only (NEVER used to self-judge correctness — that is the user's call)
print(f"[orient] apex-base from LV-endo(tag{LV_ENDO_TAG}) & mitral(tag{VALVE_TAGS[0]}); valves={VALVE_TAGS}")
print(f"[orient] apex@{np.round(APEX/1000,1)}mm base@{np.round(BASE/1000,1)}mm "
      f"up={np.round(_o['up'],3)} ant={np.round(_o['anterior'],3)}")
TARGET = 2.0
scale = TARGET / float((P0 @ R.T)[:, 2].ptp())
VERTS = [((p - gc) @ R.T) * scale for p in RAW]
allv = np.concatenate(VERTS, 0)
bmin, bmax = allv.min(0), allv.max(0)
CENTER = Vector(tuple((bmin + bmax) / 2))
RADIUS = float(np.linalg.norm(allv - (bmin + bmax) / 2, axis=1).max())

# real myofiber directions (from the .lon), rotated into world space; used as the
# anisotropy tangent. Falls back to a synthetic circumferential weave if absent.
SURF_FIBER_W = CUT_FIBER_W = None
_fibp = os.path.join(BEAT_DIR, "fibres.npz")
if os.path.exists(_fibp):
    _fz = np.load(_fibp)
    if "surf_fiber" in _fz:
        SURF_FIBER_W = (_fz["surf_fiber"].astype(np.float64) @ R.T).astype(np.float32)
    if "cut_fiber" in _fz:
        CUT_FIBER_W = (_fz["cut_fiber"].astype(np.float64) @ R.T).astype(np.float32)
    print(f"[fib] real fibres loaded (surf={SURF_FIBER_W is not None}, cut={CUT_FIBER_W is not None})")

# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ---- material library: a few realistic + artistic looks to choose from -------
def _principled(nt):
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return b, out


def _set(b, name, val):
    if name in b.inputs:
        b.inputs[name].default_value = val


def _bump(nt, b, scale=8.0, strength=0.18, detail=4.0):
    """procedural surface-detail bump (muscle/tissue micro-relief)."""
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    if "Detail" in tex.inputs: tex.inputs["Detail"].default_value = detail
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])


def _objcoord(nt):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    return tc.outputs["Object"]


def _stretch_bump(nt, b, scale=(6, 6, 1.2), strength=0.25, detail=8.0, noise=True):
    """bump from object-space noise stretched along Z -> vertical drip/streak relief."""
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = scale
    nt.links.new(_objcoord(nt), mp.inputs["Vector"])
    tex = nt.nodes.new("ShaderNodeTexNoise")
    if "Detail" in tex.inputs: tex.inputs["Detail"].default_value = detail
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])


def mat_realistic_fresh():
    m = bpy.data.materials.new("realistic_fresh"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (0.40, 0.052, 0.045, 1)); _set(b, "Roughness", 0.34)
    _set(b, "Specular IOR Level", 0.6)
    _set(b, "Subsurface Weight", 0.22); _set(b, "Subsurface Radius", (0.34, 0.12, 0.08))
    _set(b, "Subsurface Scale", 0.10)
    _set(b, "Coat Weight", 0.25); _set(b, "Coat Roughness", 0.22)   # wet pericardial sheen
    _bump(nt, b, scale=7, strength=0.12)
    return m


def mat_realistic_fibres():
    """Fresh myocardium with anisotropic 'muscle-fibre' sheen following the
    synthetic circumferential fiber_tan attribute, plus fine fibrous relief."""
    m = bpy.data.materials.new("realistic_fibres"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (0.45, 0.07, 0.06, 1)); _set(b, "Roughness", 0.40)
    _set(b, "Specular IOR Level", 0.55)
    _set(b, "Subsurface Weight", 0.16); _set(b, "Subsurface Radius", (0.30, 0.11, 0.08))
    _set(b, "Anisotropic", 0.85)
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "fiber_tan"
    if "Tangent" in b.inputs:
        nt.links.new(at.outputs["Vector"], b.inputs["Tangent"])
    _stretch_bump(nt, b, scale=(3, 3, 26), strength=0.22, detail=6)   # fine striations along fibres
    return m


def mat_wax():
    """Wet, drippy candle-wax look: deep subsurface + glossy clear coat + drips."""
    m = bpy.data.materials.new("wax"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (0.86, 0.40, 0.38, 1)); _set(b, "Roughness", 0.22)
    _set(b, "Subsurface Weight", 0.65); _set(b, "Subsurface Radius", (1.1, 0.55, 0.4))
    _set(b, "Subsurface Scale", 0.2)
    _set(b, "Coat Weight", 0.9); _set(b, "Coat Roughness", 0.04)      # wet glossy film
    _set(b, "Specular IOR Level", 0.7)
    _stretch_bump(nt, b, scale=(7, 7, 1.0), strength=0.32, detail=6)  # vertical drips
    return m


def mat_glass_ruby():
    """Clear, bright ruby glass (needs Cycles for real transmission)."""
    m = bpy.data.materials.new("glass_ruby"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (0.80, 0.10, 0.14, 1)); _set(b, "Roughness", 0.0)
    _set(b, "Transmission Weight", 1.0); _set(b, "IOR", 1.45)
    _set(b, "Metallic", 0.0)
    return m


def mat_porcelain():
    """Delicate, fragile thin porcelain: glaze + craquelure crack lines +
    light glowing through the thin grazing edges."""
    m = bpy.data.materials.new("porcelain"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    _set(b, "Base Color", (0.78, 0.75, 0.73, 1)); _set(b, "Roughness", 0.30)   # dimmed
    _set(b, "Specular IOR Level", 0.4)
    _set(b, "Subsurface Weight", 0.30); _set(b, "Subsurface Radius", (0.6, 0.55, 0.5))
    _set(b, "Subsurface Scale", 0.22)
    _set(b, "Coat Weight", 0.5); _set(b, "Coat Roughness", 0.08)      # glaze
    # craquelure: Voronoi distance-to-edge -> dark recessed crack lines (colour + relief)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    try: vor.feature = 'DISTANCE_TO_EDGE'
    except Exception: pass
    vor.inputs["Scale"].default_value = 9.0
    nt.links.new(_objcoord(nt), vor.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[0].color = (0, 0, 0, 1)
    cr.color_ramp.elements[1].position = 0.055; cr.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(vor.outputs["Distance"], cr.inputs["Fac"])
    mixc = nt.nodes.new("ShaderNodeMixRGB")                       # dark cracks into the base colour
    mixc.inputs["Color1"].default_value = (0.05, 0.045, 0.04, 1)  # crack
    mixc.inputs["Color2"].default_value = (0.80, 0.77, 0.75, 1)   # porcelain
    nt.links.new(cr.outputs["Color"], mixc.inputs["Fac"])
    nt.links.new(mixc.outputs["Color"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.7
    bp.inputs["Distance"].default_value = 0.04
    nt.links.new(cr.outputs["Color"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    # thin-edge glow: emission added at grazing angles -> reads as fragile thin shell
    # (dimmed per feedback: was too bright)
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.92
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.96, 0.92, 1)
    em.inputs["Strength"].default_value = 0.45
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lw.outputs["Facing"], mix.inputs["Fac"])
    nt.links.new(b.outputs["BSDF"], mix.inputs[1]); nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m


def mat_steampunk_flesh():
    """Bio-mechanical: fresh flesh fused with brass, exposed glowing wireframe mesh."""
    m = bpy.data.materials.new("steampunk_flesh"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    flesh = nt.nodes.new("ShaderNodeBsdfPrincipled")
    _set(flesh, "Base Color", (0.42, 0.06, 0.05, 1)); _set(flesh, "Roughness", 0.4)
    _set(flesh, "Subsurface Weight", 0.2); _set(flesh, "Subsurface Radius", (0.32, 0.12, 0.08))
    metal = nt.nodes.new("ShaderNodeBsdfPrincipled")
    _set(metal, "Base Color", (0.72, 0.46, 0.16, 1)); _set(metal, "Metallic", 1.0); _set(metal, "Roughness", 0.20)
    # crisp flesh<->brass patches (sharp mask so the two read clearly, not muddy)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.0
    if "Detail" in nz.inputs: nz.inputs["Detail"].default_value = 5.0
    rmp = nt.nodes.new("ShaderNodeValToRGB")
    rmp.color_ramp.interpolation = 'CONSTANT'                 # hard edge between flesh & metal
    rmp.color_ramp.elements[0].position = 0.50
    nt.links.new(nz.outputs["Fac"], rmp.inputs["Fac"])
    # shared mechanical relief (hammered plate) on both shaders
    bz = nt.nodes.new("ShaderNodeTexNoise"); bz.inputs["Scale"].default_value = 6.0
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.18
    nt.links.new(bz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], flesh.inputs["Normal"]); nt.links.new(bp.outputs["Normal"], metal.inputs["Normal"])
    mix1 = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(rmp.outputs["Color"], mix1.inputs["Fac"])
    nt.links.new(flesh.outputs["BSDF"], mix1.inputs[1]); nt.links.new(metal.outputs["BSDF"], mix1.inputs[2])
    nt.links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    return m


def mat_bronze():
    m = bpy.data.materials.new("bronze"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (0.62, 0.36, 0.16, 1)); _set(b, "Metallic", 1.0)
    _set(b, "Roughness", 0.30); _bump(nt, b, scale=10, strength=0.10)
    return m


def mat_steampunk():
    """Brass/copper steampunk: hammered metal with verdigris patina in the recesses."""
    m = bpy.data.materials.new("steampunk"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    # patina mask from noise -> mixes brass <-> aged copper-green, and dulls roughness
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.5
    if "Detail" in nz.inputs: nz.inputs["Detail"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[1].position = 0.62
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    mixc = nt.nodes.new("ShaderNodeMixRGB")
    mixc.inputs["Color1"].default_value = (0.71, 0.45, 0.17, 1)   # polished brass
    mixc.inputs["Color2"].default_value = (0.18, 0.42, 0.33, 1)   # verdigris
    nt.links.new(ramp.outputs["Color"], mixc.inputs["Fac"])
    nt.links.new(mixc.outputs["Color"], b.inputs["Base Color"])
    _set(b, "Metallic", 0.85); _set(b, "Roughness", 0.32)
    # hammered-plate relief + finer rivet-ish stipple
    _bump(nt, b, scale=5, strength=0.22, detail=8)
    return m


def mat_fibres_debug():
    """DTI-style fibre-direction colour map (|fiber| -> RGB) to verify the field."""
    m = bpy.data.materials.new("fibres_debug"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "fiber_tan"
    ab = nt.nodes.new("ShaderNodeVectorMath"); ab.operation = 'ABSOLUTE'
    nt.links.new(at.outputs["Vector"], ab.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ab.outputs["Vector"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def mat_hipct():
    """HiP-CT synchrotron tissue look: matte, deeply translucent burnt-amber with
    heavy SSS, a soft NOISY phase-contrast edge glow (not a hard outline), and a
    microscopic myocardial grain. Cycles only."""
    m = bpy.data.materials.new("hipct"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    _set(b, "Base Color", (0.40, 0.20, 0.12, 1))       # slightly desaturated burnt amber
    _set(b, "Roughness", 0.90)                          # completely matte, non-reflective
    _set(b, "Specular IOR Level", 0.02)                 # absolute zero -> no wet sheen
    _set(b, "Metallic", 0.0)
    _set(b, "Subsurface Weight", 1.0)                   # rely on SSS for volumetric depth
    _set(b, "Subsurface Radius", (1.2, 0.3, 0.15))      # deep red/orange bleed
    _set(b, "Subsurface Scale", 0.16)
    _set(b, "Subsurface Anisotropy", 0.5)               # forward scatter -> light reaches camera
    # microscopic myocardial grain
    ntex = nt.nodes.new("ShaderNodeTexNoise"); ntex.inputs["Scale"].default_value = 220.0
    if "Detail" in ntex.inputs: ntex.inputs["Detail"].default_value = 15.0
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5
    bp.inputs["Distance"].default_value = 0.003
    nt.links.new(ntex.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    # phase contrast from FEATURES, not just the silhouette: combine Fresnel facing with
    # geometry pointiness (grooves/ridges: sulcus, crevices) via a screen blend.
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.45
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = 0.5
    nt.links.new(geo.outputs["Pointiness"], sub.inputs[0])
    ab = nt.nodes.new("ShaderNodeMath"); ab.operation = 'ABSOLUTE'; nt.links.new(sub.outputs["Value"], ab.inputs[0])
    feat = nt.nodes.new("ShaderNodeMath"); feat.operation = 'MULTIPLY'; feat.inputs[1].default_value = 4.5
    nt.links.new(ab.outputs["Value"], feat.inputs[0])
    # screen(facing, feature) = 1 - (1-facing)*(1-feature)
    na = nt.nodes.new("ShaderNodeMath"); na.operation = 'SUBTRACT'; na.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], na.inputs[1])
    nb = nt.nodes.new("ShaderNodeMath"); nb.operation = 'SUBTRACT'; nb.inputs[0].default_value = 1.0
    nt.links.new(feat.outputs["Value"], nb.inputs[1])
    pr = nt.nodes.new("ShaderNodeMath"); pr.operation = 'MULTIPLY'
    nt.links.new(na.outputs["Value"], pr.inputs[0]); nt.links.new(nb.outputs["Value"], pr.inputs[1])
    sc = nt.nodes.new("ShaderNodeMath"); sc.operation = 'SUBTRACT'; sc.inputs[0].default_value = 1.0
    nt.links.new(pr.outputs["Value"], sc.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = 'EASE'
    ramp.color_ramp.elements[0].position = 0.30; ramp.color_ramp.elements[1].position = 0.85
    nt.links.new(sc.outputs["Value"], ramp.inputs["Fac"])
    enz = nt.nodes.new("ShaderNodeTexNoise"); enz.inputs["Scale"].default_value = 90.0   # break the halo
    if "Detail" in enz.inputs: enz.inputs["Detail"].default_value = 8.0
    m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = 'MULTIPLY'
    nt.links.new(ramp.outputs["Color"], m1.inputs[0]); nt.links.new(enz.outputs["Fac"], m1.inputs[1])
    m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = 'MULTIPLY'; m2.inputs[1].default_value = 3.0  # gentle
    nt.links.new(m1.outputs["Value"], m2.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.976, 0.902, 1)  # warm ivory #FFF9E6
    nt.links.new(m2.outputs["Value"], em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(b.outputs["BSDF"], add.inputs[0]); nt.links.new(em.outputs["Emission"], add.inputs[1])
    nt.links.new(add.outputs["Shader"], out.inputs["Surface"])
    return m


MAT_BUILDERS = {
    "realistic_fresh": mat_realistic_fresh,
    "realistic_fibres": mat_realistic_fibres,
    "fibres_debug": mat_fibres_debug,
    "hipct": mat_hipct,
    "wax": mat_wax,
    "glass_ruby": mat_glass_ruby,
    "porcelain": mat_porcelain,
    "bronze": mat_bronze,
    "steampunk": mat_steampunk,
    "steampunk_flesh": mat_steampunk_flesh,
}


def make_material(key):
    return MAT_BUILDERS.get(key, mat_realistic_fresh)()


MYO = make_material(MATERIAL)


def _solid(name, col, rough=0.42):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (*col, 1)); _set(b, "Roughness", rough)
    _set(b, "Subsurface Weight", 0.12); _set(b, "Subsurface Radius", (0.3, 0.1, 0.08))
    return m


def _ghost(name, col, trans=0.6):
    """semi-translucent grey (see-through but present)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (*col, 1)); _set(b, "Roughness", 0.25)
    _set(b, "Transmission Weight", trans); _set(b, "IOR", 1.2)
    return m


def _glass(name, col, rough=0.05):
    """coloured jewel glass (needs Cycles)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); b, _ = _principled(nt)
    _set(b, "Base Color", (*col, 1)); _set(b, "Roughness", rough)
    _set(b, "Transmission Weight", 1.0); _set(b, "IOR", 1.45)
    return m


def _invisible(name="Invisible"):
    """fully transparent -> the faces are 'gone' (used to remove a region's solid)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    nt.links.new(tr.outputs["BSDF"], out.inputs["Surface"])
    return m


# anatomy by SIDE: left heart (LV+LA) red, right heart (RV+RA) blue, rest ghosted grey
ANATOMY_GROUPS = [("Left", [1, 3], (0.62, 0.05, 0.05)),
                  ("Right", [2, 4], (0.07, 0.12, 0.55)),
                  ("Other", None, (0.55, 0.55, 0.57))]


def make_wireglow(color=(1.0, 0.55, 0.15), size=1.4, strength=3.5):
    m = bpy.data.materials.new("WireGlow"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True; wf.inputs["Size"].default_value = size
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1]); nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m


def add_wire_overlay(src_ob, tag=1, target_faces=14000, color=(1.0, 0.55, 0.15)):
    """Glowing wireframe overlay built from ONE region's faces (default LV, tag 1),
    decimated so the struts read, then SHRINK-WRAPPED back onto the heart surface so
    the wire lies on the bronze instead of forming a coarse cage around a 'blob'."""
    mask = FACE_TAGS == tag
    lf = FACES[mask]
    vid = np.unique(lf)
    remap = np.full(len(VERTS[0]), -1, dtype=np.int64); remap[vid] = np.arange(len(vid))
    f = remap[lf].astype(np.int32)
    v = VERTS[0][vid].astype(np.float32)
    me = bpy.data.meshes.new("WireLV")
    me.vertices.add(len(v)); me.vertices.foreach_set("co", v.ravel())
    nf = len(f); me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", f.ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update()
    ob = bpy.data.objects.new("WireLV", me); scene.collection.objects.link(ob)
    dec = ob.modifiers.new("Dec", "DECIMATE"); dec.ratio = min(1.0, target_faces / max(1, nf))
    sw = ob.modifiers.new("Wrap", "SHRINKWRAP")        # conform struts to the surface
    sw.target = src_ob; sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.wrap_mode = 'ABOVE_SURFACE'; sw.offset = 0.004
    ob.data.materials.append(make_wireglow(color=color))
    return ob


def build_base():
    me = bpy.data.meshes.new("Heart")
    v = VERTS[0].astype(np.float32)
    me.vertices.add(len(v)); me.vertices.foreach_set("co", v.ravel())
    nf = len(FACES); me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", FACES.ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32)); me.update()
    # fiber tangent for anisotropy: real myofibers from the .lon when available,
    # else a synthetic circumferential weave (wraps around the apex-base axis).
    if SURF_FIBER_W is not None:
        tan = SURF_FIBER_W
    else:
        p = v - np.array([CENTER.x, CENTER.y, CENTER.z], dtype=np.float32)
        tan = np.stack([-p[:, 1], p[:, 0], np.zeros(len(p), np.float32)], axis=1)
        nrm = np.linalg.norm(tan, axis=1, keepdims=True); nrm[nrm == 0] = 1
        tan = (tan / nrm).astype(np.float32)
    at = me.attributes.new("fiber_tan", 'FLOAT_VECTOR', 'POINT')
    at.data.foreach_set("vector", tan.ravel())
    if MATERIAL == "anatomy":
        grp = np.full(nf, len(ANATOMY_GROUPS) - 1, np.int32)        # default = "Other"
        for gi, (_nm, tags, _col) in enumerate(ANATOMY_GROUPS):
            if tags is not None:
                grp[np.isin(FACE_TAGS, tags)] = gi
        me.polygons.foreach_set("material_index", grp.astype(np.int32))
        for nm, tags, col in ANATOMY_GROUPS:
            me.materials.append(_solid(nm, col) if tags is not None else _ghost(nm, col))
    elif MATERIAL == "chamber_porcelain":
        # one chamber rendered in porcelain, the rest ghosted (HIGHLIGHT_TAG: 1=LV 2=RV 3=LA 4=RA)
        htag = int(os.environ.get("HIGHLIGHT_TAG", "1"))
        grp = np.zeros(nf, np.int32); grp[FACE_TAGS == htag] = 1
        me.polygons.foreach_set("material_index", grp.astype(np.int32))
        me.materials.append(_solid("Rest", (0.16, 0.015, 0.015), rough=0.45))   # dark deep red
        me.materials.append(mat_porcelain())
    elif MATERIAL == "steampunk_flesh":
        # just the wireframe: dark matte body so the glowing LV wire is the whole look
        me.materials.append(_solid("Dark", (0.02, 0.02, 0.025), rough=0.6))
    elif MATERIAL == "wire_red_nolv":
        # LV solid removed (transparent), rest dark -> only the red LV wireframe remains
        grp = np.zeros(nf, np.int32); grp[FACE_TAGS == 1] = 1
        me.polygons.foreach_set("material_index", grp.astype(np.int32))
        me.materials.append(_solid("Dark", (0.02, 0.02, 0.025), rough=0.6))
        me.materials.append(_invisible())
    elif MATERIAL == "wire_gold_red_nolv":
        # red heart body, LV solid removed -> gold LV wireframe cage over a red heart
        grp = np.zeros(nf, np.int32); grp[FACE_TAGS == 1] = 1
        me.polygons.foreach_set("material_index", grp.astype(np.int32))
        me.materials.append(_solid("HeartRed", (0.40, 0.04, 0.035), rough=0.42))
        me.materials.append(_invisible())
    elif MATERIAL == "anatomy_jewel":
        grp = np.full(nf, 2, np.int32)
        grp[np.isin(FACE_TAGS, [1, 3])] = 0           # left  -> ruby
        grp[np.isin(FACE_TAGS, [2, 4])] = 1           # right -> sapphire
        me.polygons.foreach_set("material_index", grp.astype(np.int32))
        me.materials.append(_glass("LeftRuby", (0.80, 0.06, 0.10)))
        me.materials.append(_glass("RightSapphire", (0.06, 0.14, 0.80)))
        me.materials.append(_ghost("Other", (0.60, 0.60, 0.62)))
    else:
        me.materials.append(MYO)
    ob = bpy.data.objects.new("Heart", me); scene.collection.objects.link(ob)
    if MATERIAL == "steampunk_flesh":
        add_wire_overlay(ob, tag=1)    # gold LV wire, wrapped to the surface
    elif MATERIAL == "wire_red_nolv":
        add_wire_overlay(ob, tag=1, color=(0.95, 0.05, 0.05))   # red LV wire, solid removed
    elif MATERIAL == "wire_gold_red_nolv":
        add_wire_overlay(ob, tag=1)                             # gold LV wire over red heart
    return ob


HEART = build_base()


def set_heart_material(key):
    HEART.data.materials.clear()
    HEART.data.materials.append(make_material(key))


def set_frame_verts(t01):
    f = (t01 % 1.0) * K
    i = int(f) % K; j = (i + 1) % K; a = f - int(f)
    v = (VERTS[i] * (1 - a) + VERTS[j] * a).astype(np.float32)
    HEART.data.vertices.foreach_set("co", v.ravel()); HEART.data.update()


# ---- cross-section ("cut in half") geometry, built from topo_cut + full points ----
# CUT_DEPTH selects a depth from the progressive series (topo_cut_NN.npz); else the half cut.
_cd = os.environ.get("CUT_DEPTH")
CUT_TOPO = (os.path.join(BEAT_DIR, f"topo_cut_{int(_cd):02d}.npz") if _cd is not None
            else os.path.join(BEAT_DIR, "topo_cut.npz"))
HAS_CUT = os.path.exists(CUT_TOPO)
CUT_OBJ = None
CUT_VERTS = []
if HAS_CUT:
    _ct = np.load(CUT_TOPO)
    CUT_FACES = _ct["faces"].astype(np.int32)
    CUT_VIDX = _ct["cut_vidx"]
    CUT_TAGS = _ct["face_tags"].astype(np.int64)
    CUT_VERTS = [((p[CUT_VIDX] - gc) @ R.T) * scale for p in FULL]
    print(f"[cut] {len(CUT_VERTS)} frames, {len(CUT_VIDX)} verts, {len(CUT_FACES)} faces")


def build_cut():
    me = bpy.data.meshes.new("Cut")
    v = CUT_VERTS[0].astype(np.float32)
    me.vertices.add(len(v)); me.vertices.foreach_set("co", v.ravel())
    nf = len(CUT_FACES); me.loops.add(nf * 3); me.polygons.add(nf)
    me.loops.foreach_set("vertex_index", CUT_FACES.ravel())
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32)); me.update()
    me.materials.append(make_material(MATERIAL))
    ob = bpy.data.objects.new("Cut", me); scene.collection.objects.link(ob)
    return ob


def set_cut_verts(t01):
    n = len(CUT_VERTS)
    f = (t01 % 1.0) * n
    i = int(f) % n; j = (i + 1) % n; a = f - int(f)
    v = (CUT_VERTS[i] * (1 - a) + CUT_VERTS[j] * a).astype(np.float32)
    CUT_OBJ.data.vertices.foreach_set("co", v.ravel()); CUT_OBJ.data.update()


# ---------------------------------------------------------------- camera + lights
# STYLE = studio (soft photographic softboxes) | hipct (HiP-CT synchrotron look:
# telephoto + DoF, pitch-black world, chiaroscuro 3-point with a strong back/rim
# phase-contrast light). hipct forces Cycles (SSS).
STYLE = os.environ.get("STYLE", "studio").lower()
LIGHT_SCALE = float(os.environ.get("LIGHT_SCALE", "1.0"))

cam_d = bpy.data.cameras.new("C"); cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.01; cam_d.clip_end = 100
if STYLE == "hipct":
    cam_d.lens = 90                              # telephoto -> flattened macro-tomography look
    cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 2.8
else:
    cam_d.lens = 70
cam = bpy.data.objects.new("C", cam_d); scene.collection.objects.link(cam); scene.camera = cam
CAM_DIST = RADIUS * (4.7 if STYLE == "hipct" else 3.7)   # a bit more margin (apex/base were clipping)
CAM_ELEV = math.radians(8)


def place_cam(az_deg):
    az = math.radians(az_deg)
    loc = Vector((CENTER.x + CAM_DIST * math.cos(CAM_ELEV) * math.sin(az),
                  CENTER.y - CAM_DIST * math.cos(CAM_ELEV) * math.cos(az),
                  CENTER.z + CAM_DIST * math.sin(CAM_ELEV)))
    cam.location = loc
    cam.rotation_euler = (CENTER - loc).to_track_quat("-Z", "Y").to_euler()
    if STYLE == "hipct":
        cam_d.dof.focus_distance = (CENTER - loc).length    # focus on the heart centre


def add_light(name, loc, energy, size, color, spread_deg=150):
    ld = bpy.data.lights.new(name, "AREA"); ld.shape = "SQUARE"; ld.size = size
    ld.energy = energy * LIGHT_SCALE; ld.color = color
    if hasattr(ld, "spread"): ld.spread = math.radians(spread_deg)
    o = bpy.data.objects.new(name, ld); o.location = Vector(loc)
    o.rotation_euler = (CENTER - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)


S = RADIUS
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if STYLE == "hipct":
    # chiaroscuro: warm key at 45deg, intense cool BACK/RIM light behind the subject
    # (phase-contrast edge catch), faint dark-red fill so shadows don't clip to black
    # NOTE: anterior camera (az 180) sits at +Y, so the front/camera side is +Y and
    # "behind the subject" is -Y. Key rakes the front from +Y left-up (45 deg);
    # BackRim sits at -Y (behind) for the phase-contrast edge; fill is a weak front-right.
    add_light("Key",     (CENTER.x - 2.2 * S,  1.8 * S, CENTER.z + 2.0 * S),  45 * S * S, 1.7 * S, (1.0, 0.72, 0.38), 90)
    add_light("BackRim", (CENTER.x + 0.0 * S, -3.4 * S, CENTER.z + 0.8 * S), 180 * S * S, 3.4 * S, (0.92, 0.95, 1.0), 60)
    add_light("Fill",    (CENTER.x + 2.6 * S,  1.0 * S, CENTER.z + 0.0 * S),   2 * S * S, 4.5 * S, (0.30, 0.05, 0.12), 150)
    bg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bg.inputs["Strength"].default_value = 0.0      # pitch black
else:
    # big soft softboxes, dim
    add_light("Key",  (CENTER.x - 2.2 * S, -2.4 * S, CENTER.z + 2.2 * S), 70 * S * S, 5.0 * S, (1.0, 0.97, 0.92))
    add_light("Fill", (CENTER.x + 2.8 * S, -1.6 * S, CENTER.z + 0.6 * S), 28 * S * S, 6.0 * S, (0.93, 0.96, 1.0))
    add_light("Rim",  (CENTER.x + 0.4 * S,  2.8 * S, CENTER.z + 1.8 * S), 90 * S * S, 4.0 * S, (1.0, 0.92, 0.86))
    add_light("Scrim", (CENTER.x, -3.2 * S, CENTER.z + 0.4 * S), 16 * S * S, 9.0 * S, (1.0, 0.98, 0.96))
    bg.inputs["Color"].default_value = (0.016, 0.016, 0.02, 1.0)
    bg.inputs["Strength"].default_value = 0.12


# ---------------------------------------------------------------- engine
def _enable_cycles_gpu():
    """Enable a GPU backend only if one is actually registered. This Blender 4.5
    install has broken/empty GPU compute (corrupt CUDA cubin, no OptiX backend),
    so this returns False and we fall back to CPU. Set CYCLES_GPU=1 to force-try."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    backends = list(prefs.bl_rna.properties["compute_device_type"].enum_items.keys())
    if not backends and os.environ.get("CYCLES_GPU", "0") != "1":
        print("[engine] no working Cycles GPU backend -> CPU")
        return False
    for dt in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dt
        except Exception:
            continue
        prefs.refresh_devices()
        gpus = [d for d in prefs.devices if d.type in ("OPTIX", "CUDA")]
        if gpus and (dt in backends or os.environ.get("CYCLES_GPU") == "1"):
            for d in prefs.devices:
                d.use = (d.type != "CPU")
            print(f"[engine] Cycles GPU via {dt}: {[d.name for d in gpus]}")
            return True
    print("[engine] GPU enable failed -> CPU")
    return False


def setup_engine():
    use_cycles = (ENGINE == "CYCLES") or (STYLE == "hipct")   # HiP-CT SSS needs Cycles
    if use_cycles:
        scene.render.engine = "CYCLES"
        if _enable_cycles_gpu():
            scene.cycles.device = "GPU"
        scene.cycles.samples = SAMPLES * 2
        scene.cycles.use_denoising = True
    else:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        ee = scene.eevee
        ee.taa_render_samples = max(16, SAMPLES)
        for attr, val in [("use_raytracing", True), ("use_shadows", True), ("use_gtao", True)]:
            if hasattr(ee, attr): setattr(ee, attr, val)
    scene.render.resolution_x = scene.render.resolution_y = RES
    scene.render.film_transparent = (os.environ.get("TRANSPARENT", "0") == "1")   # alpha background
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA" if scene.render.film_transparent else "RGB"


setup_engine()


def render_to(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------- story (choreographed video) helpers
def _fibre_material(emit):
    z0, z1 = float(allv[:, 2].min()), float(allv[:, 2].max())
    m = bpy.data.materials.new("FibStory"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = z0; mr.inputs["From Max"].default_value = z1
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.12, 0.10, 0.78, 1); e[1].position = 1.0; e[1].color = (0.98, 0.72, 0.14, 1)
    ramp.color_ramp.elements.new(0.5).color = (0.10, 0.70, 0.55, 1)
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    emn = nt.nodes.new("ShaderNodeEmission"); nt.links.new(ramp.outputs["Color"], emn.inputs["Color"])
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.35
    f1 = nt.nodes.new("ShaderNodeMath"); f1.operation = 'MULTIPLY'; f1.inputs[1].default_value = 0.85
    nt.links.new(lw.outputs["Facing"], f1.inputs[0])
    fa = nt.nodes.new("ShaderNodeMath"); fa.operation = 'ADD'; fa.inputs[1].default_value = 0.15
    nt.links.new(f1.outputs["Value"], fa.inputs[0])
    fade = nt.nodes.new("ShaderNodeValue"); fade.outputs[0].default_value = 0.0
    f2 = nt.nodes.new("ShaderNodeMath"); f2.operation = 'MULTIPLY'
    nt.links.new(fa.outputs["Value"], f2.inputs[0]); nt.links.new(fade.outputs[0], f2.inputs[1])
    f3 = nt.nodes.new("ShaderNodeMath"); f3.operation = 'MULTIPLY'; f3.inputs[1].default_value = emit
    nt.links.new(f2.outputs["Value"], f3.inputs[0]); nt.links.new(f3.outputs["Value"], emn.inputs["Strength"])
    nt.links.new(emn.outputs["Emission"], out.inputs["Surface"])
    return m, fade


FIB = {}   # deform state: base_raw tract points, nv (nearest heart vertex), to_world, mesh


def build_fibre_tubes(coverage="all", every=5, radius=0.004, emit=1.6, inset=0.985):
    """Fibre tracts as a deformable mesh (verts+edges) -> Geometry-Nodes tubes, so the
    tracts can follow the beat (each vertex rides its nearest heart vertex via nv)."""
    slp = os.path.join(BEAT_DIR, f"streamlines_{coverage}.npz")
    if not os.path.exists(slp):
        return None, None
    sl = np.load(slp)
    P = sl["points"].astype(np.float64); offs = sl["offsets"]; NV = sl["nv"].astype(np.int64)
    kp, knv, edges = [], [], []
    base = 0
    for l in range(0, len(offs) - 1, every):
        a, b = int(offs[l]), int(offs[l + 1])
        if b - a < 2:
            continue
        kp.append(P[a:b]); knv.append(NV[a:b]); n = b - a
        edges.append(np.column_stack([np.arange(base, base + n - 1), np.arange(base + 1, base + n)]))
        base += n
    base_raw = np.concatenate(kp, 0); nv = np.concatenate(knv, 0); edges = np.concatenate(edges, 0)
    cc = np.array([CENTER.x, CENTER.y, CENTER.z])

    def to_world(raw):
        w = (raw - gc) @ R.T * scale
        return (cc + (w - cc) * inset).astype(np.float32)

    me = bpy.data.meshes.new("FibMesh")
    me.vertices.add(len(base_raw)); me.vertices.foreach_set("co", to_world(base_raw).ravel())
    me.edges.add(len(edges)); me.edges.foreach_set("vertices", edges.astype(np.int32).ravel())
    me.update()
    ob = bpy.data.objects.new("Fibres", me); scene.collection.objects.link(ob)
    fibmat, fade = _fibre_material(emit); me.materials.append(fibmat)
    ng = bpy.data.node_groups.new("TubeGN", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = ng.nodes.new("NodeGroupInput"); go = ng.nodes.new("NodeGroupOutput")
    m2c = ng.nodes.new("GeometryNodeMeshToCurve")
    circ = ng.nodes.new("GeometryNodeCurvePrimitiveCircle")
    circ.inputs["Resolution"].default_value = 6; circ.inputs["Radius"].default_value = radius
    c2m = ng.nodes.new("GeometryNodeCurveToMesh")
    sm = ng.nodes.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value = fibmat
    ng.links.new(gi.outputs[0], m2c.inputs["Mesh"])
    ng.links.new(m2c.outputs["Curve"], c2m.inputs["Curve"])
    ng.links.new(circ.outputs["Curve"], c2m.inputs["Profile Curve"])
    ng.links.new(c2m.outputs["Mesh"], sm.inputs["Geometry"])
    ng.links.new(sm.outputs["Geometry"], go.inputs[0])
    md = ob.modifiers.new("Tubes", 'NODES'); md.node_group = ng
    FIB.update(me=me, base_raw=base_raw, nv=nv, to_world=to_world)
    return ob, fade


def set_fibre_frame(t01):
    """Deform the fibre tracts to beat timestep t01 (each vertex rides its nearest heart vertex)."""
    if not FIB:
        return
    f = (t01 % 1.0) * K; i = int(f) % K; j = (i + 1) % K; a = f - int(f)
    disp = ((FULL[i] * (1 - a) + FULL[j] * a) - FULL[0])[FIB["nv"]]
    FIB["me"].vertices.foreach_set("co", FIB["to_world"](FIB["base_raw"] + disp).ravel())
    FIB["me"].update()


def heart_alpha_node():
    """Grab the heart hero-material's Principled node so its Alpha can be animated
    (translucent while fibres show, opaque otherwise); enable EEVEE alpha blend."""
    mat = HEART.data.materials[0]
    try: mat.blend_method = 'BLEND'
    except Exception: pass
    return next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)


CUT_STATE = []   # (object, cut_vidx) per depth, so each can beat


def build_cut_depth_objs(mat_key):
    """Cut meshes at every depth (topo_cut_NN.npz), hidden by default; each can be
    deformed to a beat frame via set_cut_obj_frame (the cross-section keeps beating)."""
    import glob as _g
    files = sorted(_g.glob(os.path.join(BEAT_DIR, "topo_cut_[0-9][0-9].npz")))
    p0 = FULL[0]; objs = []
    shared_mat = make_material(mat_key)                 # one material shared by all depths
    for f in files:
        ct = np.load(f); cf = ct["faces"].astype(np.int32); cvidx = ct["cut_vidx"]
        v = ((((p0[cvidx] - gc) @ R.T) * scale)).astype(np.float32)
        me = bpy.data.meshes.new(os.path.basename(f))
        me.vertices.add(len(v)); me.vertices.foreach_set("co", v.ravel())
        nf = len(cf); me.loops.add(nf * 3); me.polygons.add(nf)
        me.loops.foreach_set("vertex_index", cf.ravel())
        me.polygons.foreach_set("loop_start", np.arange(0, nf * 3, 3, dtype=np.int32))
        me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
        me.update(calc_edges=True)
        bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
        me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32)); me.update()
        me.materials.append(shared_mat)
        ob = bpy.data.objects.new(me.name, me); scene.collection.objects.link(ob)
        ob.hide_render = True; ob.hide_viewport = True; objs.append(ob); CUT_STATE.append((ob, cvidx))
    return objs


def set_cut_obj_frame(idx, t01):
    ob, cvidx = CUT_STATE[idx]
    f = (t01 % 1.0) * K; i = int(f) % K; j = (i + 1) % K; a = f - int(f)
    pts = (FULL[i] * (1 - a) + FULL[j] * a)[cvidx]
    ob.data.vertices.foreach_set("co", (((pts - gc) @ R.T) * scale).astype(np.float32).ravel())
    ob.data.update()


# ---------------------------------------------------------------- modes
if MODE == "materials":
    set_frame_verts(0.0)
    place_cam(START_AZ)                       # anterior view
    for key in MAT_BUILDERS:
        set_heart_material(key)
        render_to(os.path.join(OUT_DIR, f"material_{key}.png"))
        print(f"[materials] {key}")
    print("MATERIALS DONE ->", OUT_DIR)

elif MODE == "cut_still":
    if not HAS_CUT:
        raise SystemExit("no topo_cut.npz / *_full.npz — run extract_cut.py first")
    HEART.hide_render = True
    CUT_OBJ = build_cut(); set_cut_verts(0.0)
    place_cam(START_AZ)
    render_to(os.path.join(OUT_DIR, f"cut_still_{MATERIAL}.png"))
    print("CUT STILL DONE ->", OUT_DIR)

elif MODE == "turntable":
    set_frame_verts(0.0)
    n = 8
    for k in range(n):
        az = START_AZ + k * (360.0 / n)
        place_cam(az)
        render_to(os.path.join(OUT_DIR, f"turntable_{k:02d}_az{int(az)%360:03d}.png"))
        print(f"[turntable] view {k} az={int(az)%360}")
    print("TURNTABLE DONE ->", OUT_DIR)

elif MODE == "still":
    az = float(REST[0]) if len(REST) > 0 else START_AZ
    fi = int(REST[1]) if len(REST) > 1 else 0
    set_frame_verts(fi / max(1, K)); place_cam(az)
    render_to(os.path.join(OUT_DIR, f"still_az{int(az)%360:03d}_f{fi:02d}.png"))
    print("STILL DONE")

elif MODE == "story":
    # heart -> fibres fade in -> orbit -> beat (fibres follow it) -> fibres fade out ->
    # progressive cut, with the beat continuing (cross-section beats) through to the end.
    FIB_OB, FADE = build_fibre_tubes()
    HALPHA = heart_alpha_node()
    CUTS = build_cut_depth_objs(MATERIAL); ND = len(CUTS)
    # 'hold' keeps the half-cut cross-section beating at the end (beat continues through it)
    D = {"appear": 0.6, "fibin": 1.4, "orbit": 6.0, "beatout": 2.0, "beat": 2.5, "cut": 3.5, "hold": 4.0}
    t0 = {}; acc = 0.0
    for k in ["appear", "fibin", "orbit", "beatout", "beat", "cut", "hold"]:
        t0[k] = acc; acc += D[k]
    TOTAL = acc; NFR = int(round(FPS * TOTAL)); BEAT_PERIOD = float(os.environ.get("BEAT_PERIOD", "0.9"))
    outdir = os.path.join(OUT_DIR, f"story_{MATERIAL}"); os.makedirs(outdir, exist_ok=True)
    print(f"[story] {NFR} frames, {TOTAL:.1f}s, {ND} cut depths, material={MATERIAL}, engine={ENGINE}")
    set_fibre_frame(0.0)
    for fr in range(NFR):
        t = fr / FPS
        # fibre fade + heart translucency
        if t < t0["fibin"]:
            fade = 0.0
        elif t < t0["orbit"]:
            fade = (t - t0["fibin"]) / D["fibin"]
        elif t < t0["beatout"]:
            fade = 1.0
        elif t < t0["beat"]:
            fade = 1.0 - (t - t0["beatout"]) / D["beatout"]
        else:
            fade = 0.0
        if FADE: FADE.outputs[0].default_value = fade
        if HALPHA and "Alpha" in HALPHA.inputs:
            HALPHA.inputs["Alpha"].default_value = 1.0 - 0.55 * fade
        if FIB_OB:
            fh = (fade <= 0.001)
            FIB_OB.hide_render = fh; FIB_OB.hide_viewport = fh   # skip GN-tube eval when hidden
        # beat starts at beatout and continues to the end
        beating = t >= t0["beatout"]
        beat_u = (t - t0["beatout"]) / BEAT_PERIOD if beating else 0.0
        in_cut = t >= t0["cut"]
        # heart surface (hidden during the cut); fibres follow the beat while visible
        HEART.hide_render = in_cut
        if not in_cut:
            set_frame_verts(beat_u)
        if fade > 0.001 and beating:
            set_fibre_frame(beat_u)
        # camera
        if t < t0["orbit"]:
            az = START_AZ
        elif t < t0["beatout"]:
            az = START_AZ + 360.0 * ((t - t0["orbit"]) / D["orbit"])
        else:
            az = START_AZ
        place_cam(az)
        # cut phase: deepen through the depths, active depth keeps beating
        if in_cut:
            di = min(ND - 1, int((t - t0["cut"]) / D["cut"] * ND))
            for j, ob in enumerate(CUTS):
                h = (j != di)
                ob.hide_render = h; ob.hide_viewport = h        # only the active depth is evaluated
            set_cut_obj_frame(di, beat_u)
        else:
            for ob in CUTS:
                ob.hide_render = True; ob.hide_viewport = True
        render_to(os.path.join(outdir, f"f_{fr:04d}.png"))
        if fr % 15 == 0:
            print(f"[story] {fr+1}/{NFR}", flush=True)
    print("STORY FRAMES DONE ->", outdir)

else:  # video
    NFR = int(round(FPS * ORBIT_SECONDS))
    outdir = os.path.join(OUT_DIR, "frames_video")
    os.makedirs(outdir, exist_ok=True)
    print(f"[video] {NFR} frames @ {FPS}fps, {ORBIT_SECONDS}s, {BEATS} beats, {ENGINE} {RES}p")
    for fr in range(NFR):
        u = fr / NFR
        set_frame_verts(u * BEATS)
        place_cam(START_AZ + 360.0 * u)
        render_to(os.path.join(outdir, f"f_{fr:04d}.png"))
        if fr % 10 == 0: print(f"[video] {fr+1}/{NFR}", flush=True)
    print("VIDEO FRAMES DONE ->", outdir)
