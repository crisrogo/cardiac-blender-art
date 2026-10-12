"""
"The realistic look", shared by render_realism.py and render_ep_video.py (FINISH=realistic).

Wet fresh-specimen tissue in Cycles: one dark red-pink palette for the whole
myocardium (atria and ventricles alike), pale great vessels, darker inner surfaces;
random-walk subsurface scattering; a water-film clear coat whose own micro-bump
breaks the highlights into glints; and, when the case has the real myofibre field
(fibres.npz, from the .lon), an anisotropic sheen and fine striations along it.
Lit by a soft studio rig (big key, generous fill, gentle rim).

Nothing here adds geometry: only shading on the mesh the caller builds. Every
procedural pattern is read at the `rest` attribute (the frame-0 position) so it
sticks to the tissue while the mesh deforms, and the fibre detail needs the
`fiber_tan` attribute -- add both with `add_attributes`.
"""
import bpy
import math
import numpy as np
from mathutils import Vector

# sRGB (light, mid, dark) palettes, mottled through a 3-stop ramp
MYOCARDIUM = ((0.70, 0.30, 0.31), (0.56, 0.18, 0.21), (0.40, 0.09, 0.12))
VESSELS = ((0.84, 0.62, 0.56), (0.76, 0.50, 0.46), (0.62, 0.36, 0.34))
INNER = ((0.52, 0.14, 0.14), (0.40, 0.08, 0.09), (0.28, 0.04, 0.05))
MYO_TAGS, VESSEL_TAGS = (1, 2, 3, 4), (5, 6)           # LV, RV, LA, RA | aorta, PA


def srgb(c):
    c = np.asarray(c, float)
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)) + (1.0,)


def _set(b, name, val):
    if name in b.inputs:
        b.inputs[name].default_value = val


def _attr(nt, name):
    a = nt.nodes.new("ShaderNodeAttribute"); a.attribute_name = name
    return a.outputs["Vector"]


def _vmath(nt, op, a, b=None, scale=None):
    n = nt.nodes.new("ShaderNodeVectorMath"); n.operation = op
    for i, x in enumerate((a, b)):
        if x is not None:
            nt.links.new(x, n.inputs[i])
    if scale is not None:
        n.inputs["Scale"].default_value = scale
    return n.outputs["Value" if op == "DOT_PRODUCT" else "Vector"]


def _noise(nt, scale, detail=4.0, rough=0.55, vec=None):
    """Noise read at `vec`, by default the frame-0 position (sticks to the tissue)."""
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    tex.inputs["Roughness"].default_value = rough
    nt.links.new(vec if vec is not None else _attr(nt, "rest"), tex.inputs["Vector"])
    return tex.outputs["Fac"]


def _striations(nt, cells=14.0, freq=120.0):
    """Fine streaks along the myofibres (fiber_tan). The rest position is split
    into Voronoi cells (~1/cells wide); inside each, a noise is read at the
    cell-local position with its component along the fibre removed, so it is
    constant along the fibre. Cell-local (not object) coordinates keep that
    projection from swirling as the fibre direction turns over the heart."""
    p = _vmath(nt, "SCALE", _attr(nt, "rest"), scale=cells)
    vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 1.0
    nt.links.new(p, vor.inputs["Vector"])
    loc = _vmath(nt, "SUBTRACT", p, vor.outputs["Position"])
    t = _vmath(nt, "NORMALIZE", _attr(nt, "fiber_tan"))
    along = nt.nodes.new("ShaderNodeVectorMath"); along.operation = "SCALE"
    nt.links.new(t, along.inputs[0]); nt.links.new(_vmath(nt, "DOT_PRODUCT", loc, t), along.inputs["Scale"])
    perp = _vmath(nt, "SUBTRACT", loc, along.outputs["Vector"])
    q = _vmath(nt, "ADD", _vmath(nt, "SCALE", perp, scale=freq / cells),
               _vmath(nt, "SCALE", vor.outputs["Color"], scale=37.0))         # decorrelate the cells
    return _noise(nt, 1.0, detail=1.5, rough=0.5, vec=q)


def _ramp(nt, fac, stops):
    n = nt.nodes.new("ShaderNodeValToRGB")
    els = n.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (pos, col) in zip(els, stops):
        e.position = pos; e.color = srgb(col)
    nt.links.new(fac, n.inputs["Fac"])
    return n.outputs["Color"]


def _bump(nt, height, strength, dist=0.01, normal=None):
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = dist
    nt.links.new(height, bp.inputs["Height"])
    if normal is not None:
        nt.links.new(normal, bp.inputs["Normal"])
    return bp.outputs["Normal"]


def specimen(nt, palette, fibres, sss=0.55, muscle=True, striate=0.3):
    """Build the tissue into node tree `nt` (Principled + Material Output).
    Returns (principled, tissue colour socket); the caller may re-link Base Color
    (e.g. to mix an activation wave over the tissue colour) or add emission.
    fibres: whether the mesh carries the real `fiber_tan`; muscle=False skips the
    fibre sheen/striations (vessels, inner surfaces)."""
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    light, mid, dark = palette
    mixf = nt.nodes.new("ShaderNodeMath"); mixf.operation = "MULTIPLY_ADD"     # big + 0.3 fine
    nt.links.new(_noise(nt, 38.0, detail=6.0), mixf.inputs[0]); mixf.inputs[1].default_value = 0.3
    nt.links.new(_noise(nt, 2.2, detail=3.0), mixf.inputs[2])
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = 0.15
    nt.links.new(mixf.outputs[0], sub.inputs[0])
    col = _ramp(nt, sub.outputs[0], [(0.32, dark), (0.50, mid), (0.66, light)])
    nt.links.new(col, b.inputs["Base Color"])
    _set(b, "Roughness", 0.42)
    _set(b, "Subsurface Weight", sss); _set(b, "Subsurface Radius", (1.0, 0.32, 0.20))
    _set(b, "Subsurface Scale", 0.035)
    _set(b, "Specular IOR Level", 0.5)
    _set(b, "Coat Weight", 1.0); _set(b, "Coat Roughness", 0.06); _set(b, "Coat IOR", 1.33)
    relief = _bump(nt, _noise(nt, 14.0, detail=5.0), 0.10, 0.02)              # soft tissue relief
    if muscle and fibres:
        _set(b, "Anisotropic", 0.45)
        nt.links.new(_attr(nt, "fiber_tan"), b.inputs["Tangent"])
        if striate > 0:
            relief = _bump(nt, _striations(nt), striate, 0.004, normal=relief)
    nt.links.new(relief, b.inputs["Normal"])
    film = _bump(nt, _noise(nt, 90.0, detail=2.0), 0.05, 0.004, normal=relief)   # beaded water film
    nt.links.new(film, b.inputs["Coat Normal"])
    return b, col


def make_specimen(name, palette, fibres, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.node_tree.nodes.clear()
    specimen(m.node_tree, palette, fibres, **kw)
    return m


def add_attributes(me, rest, fiber=None):
    """`rest` (frame-0 positions, as the mesh is built) and, if given, `fiber_tan`
    (per-vertex myofibre direction in the same frame as the mesh)."""
    a = me.attributes.new("rest", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", np.asarray(rest, np.float32).ravel())
    if fiber is not None:
        t = np.asarray(fiber, np.float64)
        t = t / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
        a = me.attributes.new("fiber_tan", "FLOAT_VECTOR", "POINT")
        a.data.foreach_set("vector", t.astype(np.float32).ravel())


def soft_rig(scene, center, size, cam, scale=1.0):
    """Soft studio lights placed relative to the camera object `cam` (its rotation
    must be set): a big warm key top-left, a generous fill front-right, a gentle
    cool rim behind-right, a faint top strip. Black world. "Front" is the
    horizontal direction of the image's bottom edge, so the rig keeps its place
    on screen even when the camera looks straight down or past the vertical."""
    m = cam.rotation_euler.to_matrix()
    r = Vector((m[0][0], m[1][0], m[2][0])).normalized()            # screen-right
    up = Vector((m[0][1], m[1][1], m[2][1]))                        # screen-up
    f = Vector((-up.x, -up.y, 0))
    if f.length < 1e-3:                                             # level camera: use the view axis
        f = Vector((m[0][2], m[1][2], 0))
    f.normalize()
    S = size

    def light(name, fw, rt, up, energy, sx, sy, color, spread):
        ld = bpy.data.lights.new(name, "AREA"); ld.shape = "RECTANGLE"
        ld.size, ld.size_y = sx * S, sy * S
        ld.energy = energy * S * S * scale; ld.color = color; ld.spread = math.radians(spread)
        o = bpy.data.objects.new(name, ld)
        o.location = center + f * (fw * S) + r * (rt * S) + Vector((0, 0, up * S))
        o.rotation_euler = (center - o.location).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(o)

    light("Key", 0.6, -0.8, 1.4, 16.0, 1.8, 1.2, (1.0, 0.95, 0.89), 90)
    light("Fill", 1.2, 0.9, 0.8, 5.0, 2.0, 2.0, (1.0, 0.94, 0.90), 120)
    light("Rim", -1.2, 0.8, 1.6, 10.0, 0.8, 1.0, (0.88, 0.93, 1.0), 45)
    light("Top", -0.1, 0.1, 1.8, 1.5, 1.6, 0.3, (1.0, 1.0, 1.0), 90)
    world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1); bg.inputs["Strength"].default_value = 0.0


def setup_cycles(scene, samples, transparent=False):
    """Cycles on the GPU when one is there (OptiX, then CUDA; CYCLES_GPU=0 forces
    the CPU), denoised, AgX Base Contrast. Same device probe as cover_render.py:
    ask get_devices_for_type() directly -- the compute_device_type enum comes back
    empty under --background --factory-startup."""
    import os
    scene.render.engine = "CYCLES"
    backend = None
    if os.environ.get("CYCLES_GPU", "1") != "0":
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for bk in ("OPTIX", "CUDA"):
                try:
                    prefs.compute_device_type = bk
                except (TypeError, ValueError):
                    continue
                devs = prefs.get_devices_for_type(bk)
                if not any(getattr(d, "type", "") == bk for d in devs):
                    continue
                for d in devs:                  # GPU only: adding the CPU can slow OptiX
                    d.use = (getattr(d, "type", "") == bk)
                backend = bk
                break
        except Exception as exc:
            print("[gpu] setup failed:", exc)
    scene.cycles.device = "GPU" if backend else "CPU"
    print(f"[engine] Cycles on {backend or 'CPU'}")
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8; scene.cycles.glossy_bounces = 4
    scene.cycles.caustics_reflective = False; scene.cycles.caustics_refractive = False
    scene.render.film_transparent = transparent
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Base Contrast"
