"""JMCC cover-art renders: five HCM glass hearts over a "digital world" floor.

Usage:
    blender --background --factory-startup --python cover_render.py -- <comp> [floor=<kind>] [test|4k]

    comp  : vshape | arc | tree | mirror
    floor : none | grid | femesh | tree

`tree` draws the Curran cluster branches over whichever floor is chosen, so both
`tree floor=grid` and `tree floor=tree` are valid.

The five hearts are rendered identically (same glass, same lights, same scale) so
the only thing that varies between them is anatomy -- the paper's point being that
anatomy is *not* what reshapes the sensitivity profiles.
"""
import bpy
import bmesh
import sys
import os
import math
import numpy as np
from mathutils import Vector, Matrix

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
COMP = "vshape"
FLOOR = "grid"
ELEV = 35.0      # camera elevation above the floor plane, degrees (tree/arc)
for a in ARGS:
    if a.startswith("floor="):
        FLOOR = a.split("=", 1)[1]
    elif a.startswith("elev="):
        ELEV = float(a.split("=", 1)[1])
    elif a in ("vshape", "arc", "tree", "mirror"):
        COMP = a
DRAW_TREE = (COMP == "tree")   # branches are an overlay, independent of the floor kind
TEST = "test" in ARGS
FOURK = "4k" in ARGS
print(f"=== COVER: comp={COMP} floor={FLOOR} ===")

SCIBLEND = (os.environ.get("SCIBLEND_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "meshes", "sciblend"))
OUTDIR = (os.environ.get("OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
COVERDIR = os.path.join(OUTDIR, "cover")

# Figure 1 / graphical-abstract mesh green -- the paper's own visual signature.
FIG_GREEN = (0.10, 0.95, 0.28)
WARM_WHITE = (1.0, 0.85, 0.7)
MIRROR_TARGET_TRIS = 1400   # coarse enough that the facets read as a discretisation


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


def make_flesh(name):
    """Fresh myocardium, matching beat_video/render_beat_video.py's realistic_fresh:
    subsurface-scattering tissue with a wet pericardial coat."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")

    def _set(k, v):
        if k in b.inputs:
            b.inputs[k].default_value = v

    _set("Base Color", (0.40, 0.052, 0.045, 1.0))
    _set("Roughness", 0.34)
    _set("Specular IOR Level", 0.6)
    _set("Subsurface Weight", 0.22)
    _set("Subsurface Radius", (0.34, 0.12, 0.08))
    _set("Subsurface Scale", 0.10)
    _set("Coat Weight", 0.25)
    _set("Coat Roughness", 0.22)
    # fine surface relief so the tissue does not read as plastic
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (7.0, 7.0, 7.0)
    tex = nt.nodes.new("ShaderNodeTexNoise")
    if "Detail" in tex.inputs:
        tex.inputs["Detail"].default_value = 8.0
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.12
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(b.outputs["BSDF"], o.inputs["Surface"])
    return m


def _radial_fade(nt, cz, radius):
    """1 near (0,cz) in the XZ plane, 0 by `radius` -- keeps the floor from
    hitting a hard far edge and reads as fog."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    subz = nt.nodes.new("ShaderNodeMath"); subz.operation = "SUBTRACT"; subz.inputs[1].default_value = cz
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = radius
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    mr.clamp = True
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], subz.inputs[0])
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(subz.outputs["Value"], comb.inputs["Z"])
    nt.links.new(comb.outputs["Vector"], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], mr.inputs["Value"])
    return mr.outputs["Result"], sep


def _dark_base(nt, reflect=0.55, rough=0.045, see_through=0.0, blur=0.0):
    """Dark-glass floor: a plain glossy lobe (so reflections read clearly rather
    than the few-percent Fresnel a dielectric gives at this angle), optionally
    mixed with Transparent so a mesh sitting below the plane shows through."""
    try:
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    except RuntimeError:                      # older node id
        gl = nt.nodes.new("ShaderNodeBsdfAnisotropic")
    gl.inputs["Color"].default_value = (reflect, reflect, reflect * 1.06, 1.0)
    gl.inputs["Roughness"].default_value = rough
    out = gl.outputs["BSDF"]
    if see_through > 0.0:
        if blur > 0.0:
            # Refraction at IOR 1.0 passes straight through without displacing the
            # image, but its roughness scatters it -- so whatever sits below the
            # plane arrives diffused, like a reflection in imperfect dark glass.
            tr = nt.nodes.new("ShaderNodeBsdfRefraction")
            tr.inputs["IOR"].default_value = 1.0
            tr.inputs["Roughness"].default_value = blur
        else:
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = see_through
        nt.links.new(out, mix.inputs[1])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[2])
        out = mix.outputs["Shader"]
    return out


def make_mesh_ghost(name, color, fill=1.05, wire_strength=1.7, wire_size=1.0,
                    body_alpha=0.45, yfade=None):
    """Downsampled-model look, tuned to read as a *reflection* rather than an object
    parked under the floor: soft wide wires at low contrast over a chamber-tinted
    body, the whole thing dissolving with depth (`yfade=(y_at_plane, y_deepest)`)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    fe = nt.nodes.new("ShaderNodeEmission")
    fe.inputs["Color"].default_value = (*color, 1.0)
    fe.inputs["Strength"].default_value = fill
    body = nt.nodes.new("ShaderNodeMixShader")
    body.inputs["Fac"].default_value = body_alpha
    nt.links.new(fe.outputs["Emission"], body.inputs[1])
    nt.links.new(tr.outputs["BSDF"], body.inputs[2])
    we = nt.nodes.new("ShaderNodeEmission")
    we.inputs["Color"].default_value = (*WARM_WHITE, 1.0)
    we.inputs["Strength"].default_value = wire_strength
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True
    wf.inputs["Size"].default_value = wire_size
    inner = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs["Fac"], inner.inputs["Fac"])
    nt.links.new(body.outputs["Shader"], inner.inputs[1])
    nt.links.new(we.outputs["Emission"], inner.inputs[2])
    out = inner.outputs["Shader"]
    if yfade is not None:
        # dissolve toward transparent with depth, so it loses itself in the surface
        # instead of ending in a hard silhouette
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = yfade[1]   # deepest
        mr.inputs["From Max"].default_value = yfade[0]   # at the plane
        mr.inputs["To Min"].default_value = 1.0          # -> fully transparent
        mr.inputs["To Max"].default_value = 0.0          # -> full ghost
        mr.clamp = True
        fade = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["Y"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], fade.inputs["Fac"])
        nt.links.new(out, fade.inputs[1])
        nt.links.new(tr.outputs["BSDF"], fade.inputs[2])
        out = fade.outputs["Shader"]
    nt.links.new(out, o.inputs["Surface"])
    return m


def make_grid_floor_mat(name, cell=0.10, lw=0.0011, cz=0.05, radius=1.5, strength=0.22,
                        see_through=0.0, blur=0.0, refl_rough=0.045):
    """Dark glossy plane with a regular square grid of glowing green lines.

    `see_through` mixes in a Transparent BSDF so the mirror composition can show the
    downsampled mesh sitting below the plane, like looking into dark water."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    fade, sep = _radial_fade(nt, cz, radius)

    def axis_line(sock):
        wr = nt.nodes.new("ShaderNodeMath"); wr.operation = "WRAP"
        wr.inputs[1].default_value = cell * 0.5      # Max
        wr.inputs[2].default_value = -cell * 0.5     # Min
        ab = nt.nodes.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"
        lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"
        lt.inputs[1].default_value = lw
        nt.links.new(sock, wr.inputs[0])
        nt.links.new(wr.outputs["Value"], ab.inputs[0])
        nt.links.new(ab.outputs["Value"], lt.inputs[0])
        return lt.outputs["Value"]

    mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
    nt.links.new(axis_line(sep.outputs["X"]), mx.inputs[0])
    nt.links.new(axis_line(sep.outputs["Z"]), mx.inputs[1])
    fac = nt.nodes.new("ShaderNodeMath"); fac.operation = "MULTIPLY"
    nt.links.new(mx.outputs["Value"], fac.inputs[0])
    nt.links.new(fade, fac.inputs[1])

    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*FIG_GREEN, 1.0)
    em.inputs["Strength"].default_value = strength

    base = _dark_base(nt, rough=refl_rough, see_through=see_through, blur=blur)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(base, mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], o.inputs["Surface"])
    return m


def make_femesh_floor_mat(name, wire=0.0007, cz=0.05, radius=1.5, strength=0.40):
    """Dark glossy plane whose own irregular triangulation glows -- a finite-element
    floor rather than a Tron grid."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    fade, _ = _radial_fade(nt, cz, radius)
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = False
    wf.inputs["Size"].default_value = wire
    fac = nt.nodes.new("ShaderNodeMath"); fac.operation = "MULTIPLY"
    nt.links.new(wf.outputs["Fac"], fac.inputs[0])
    nt.links.new(fade, fac.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*FIG_GREEN, 1.0)
    em.inputs["Strength"].default_value = strength
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(_dark_base(nt), mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], o.inputs["Surface"])
    return m


def make_wireglow(name, color, wire_size=0.6, strength=4.0, pixel=True, yfade=None):
    """`yfade=(y_bright, y_dim)` dims the wires with depth, so the mirrored mesh
    falls off the further it sits below the plane -- the way a reflection does."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = pixel
    wf.inputs["Size"].default_value = wire_size
    mix = nt.nodes.new("ShaderNodeMixShader")
    if yfade is None:
        nt.links.new(wf.outputs["Fac"], mix.inputs["Fac"])
    else:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = yfade[1]   # deepest -> dimmest
        mr.inputs["From Max"].default_value = yfade[0]   # just under the plane -> full
        mr.inputs["To Min"].default_value = 0.12
        mr.inputs["To Max"].default_value = 1.0
        mr.clamp = True
        mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
        nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["Y"], mr.inputs["Value"])
        nt.links.new(wf.outputs["Fac"], mul.inputs[0])
        nt.links.new(mr.outputs["Result"], mul.inputs[1])
        nt.links.new(mul.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], o.inputs["Surface"])
    return m


# ------------------------------------------------------------------ tree data ---
# Branch skeleton traced from the published Curran et al. clustering figure.
# Branch -> phenotype (numbering as labelled on that figure):
#   1 mid-to-apical LVH   2 LVOTO   3 isolated basal LVH
#   4 milder asymmetric LVH   5 undifferentiated (centre)
TREE_PX = [((140, 232), (300, 196)),     # branch 1, far-left arm
           ((300, 196), (470, 238)),     # branch 1 into the junction
           ((350, 158), (415, 215)),     # branch 1 upper fork
           ((470, 238), (600, 238)),     # branch 5, centre segment
           ((478, 240), (355, 445)),     # branch 2, descending left
           ((600, 238), (655, 450)),     # branch 3, descending right
           ((600, 238), (700, 192)),     # branch 4 rises
           ((700, 192), (960, 237))]     # branch 4 right arm (see note below)
# Branch 4 runs 535 px from its junction in the source figure against branch 1's
# 330 px, which strands heart 4 out on its own. Truncated along its own direction
# to 960 px so the two outer hearts sit at matching distances from the centre.
TREE_TIPS_PX = {1: (140, 232), 2: (355, 445), 3: (655, 450), 4: (960, 237), 5: (535, 238)}
TREE_CX, TREE_CY, TREE_PXSCALE = 550.0, 300.0, 597.5   # bbox centre of the traced tree
# Deliberately anisotropic. The published tree is ~4.5:1 wide-to-deep, which in a
# square frame crowds all five hearts onto one thin band where they hide the
# branches. Stretching depth far harder than width pulls branches 2 and 3 forward
# off the spine and separates the hearts without pushing 1 and 4 out of frame.
TREE_SX, TREE_SZ = 0.74, 1.45
# Branches 2 and 3 are the only ones running toward the camera, so scaling the
# positive-z side alone shortens exactly those two without touching the spine.
FORE_SHORTEN = 0.62


def tree_xz(px):
    """Figure pixels -> floor XZ, centred on the tree's own bounding box.
    Figure-down maps toward the camera (+Z), so branches 2 and 3 come forward."""
    z = (px[1] - TREE_CY) / TREE_PXSCALE * TREE_SZ
    if z > 0.0:
        z *= FORE_SHORTEN
    return ((px[0] - TREE_CX) / TREE_PXSCALE * TREE_SX, z)


# ---------------------------------------------------------------- composition ---
TARGET_SIZE = 0.15
HEART_FILE = {1: 4, 2: 2, 3: 3, 4: 1, 5: 5}   # position -> .blend (position 1 = hero)
HEARTS = [1, 2, 3, 4, 5]
SNAP = False        # rest each heart on the floor instead of floating it
HERO_WIRE = True    # wireframe accent on heart 1 (a focal point, but it singles one out)
GLARE_THRESHOLD = 1.0
LENS = 30.0
CAM_ROLL = 0.0
FADE_CZ, FADE_R = 0.05, 1.5
GRID_CELL = 0.075
WORLD_POS = None    # world-space XZ layout; when None, IMG image-space placement is used
SEE_THROUGH = 0.0   # floor transparency, so a mesh below the plane shows through
FLOOR_BLUR = 0.0    # scatter on that transmission -> what shows through arrives diffused
FLOOR_ROUGH = 0.045  # glossy roughness of the floor: low = mirror, higher = soft reflections
FLESH = False       # realistic myocardium instead of coloured glass
DIGITAL_HEARTS = []     # hearts whose reflection is replaced by a downsampled model
DIGITAL_STYLE = "green"  # "green" wireframe ghost, or "chambers" white-wire + chamber tint

# The elevated, slightly-down camera and the brighter rig originally written for the
# tree layout: shared by every floor-standing composition.
TREE_CAM = (Vector((0.0, 0.42, 0.92)), Vector((0.0, 0.02, 0.02)))
TREE_LIGHTS = [("Key", (-0.55, 0.80, 0.70), (0, 0.05, 0.05), 2.2, 75.0, (1.00, 0.93, 0.86)),
               ("Fill", (0.70, 0.30, 0.70), (0, 0.05, 0.05), 2.0, 45.0, (0.98, 0.98, 1.00)),
               ("Back", (0.00, 0.50, -0.55), (0, 0.10, 0.05), 1.4, 22.0, (0.78, 0.86, 1.00))]

if COMP == "vshape":
    TARGET_SIZE = 0.14
    LEAN = {i: -30 for i in HEARTS}
    IMG = {1: (0.00, -0.16, 0.27),
           2: (-0.27, 0.10, 0.31), 3: (0.27, 0.10, 0.31),
           4: (-0.36, 0.40, 0.38), 5: (0.36, 0.40, 0.38)}
    # Shallow downward pitch: the horizon lands ~1/4 above centre, so the glowing
    # ground sits in the lower band and the top of the frame stays black for the
    # masthead. Placement is image-space, so the V reads the same as the original.
    CAM_LOC = Vector((0.0, 0.10, 0.47)); CAM_TARGET = Vector((0.0, 0.044, 0.07))
    FOCUS, FSTOP = 0.31, 18.0
    FLOOR_GAP = 0.055
    FADE_CZ, FADE_R = 0.15, 0.80
    LIGHTS = [("Key", (-0.30, 0.40, 0.55), (0, 0.05, 0.15), 1.7, 12.0, (1.00, 0.93, 0.86)),
              ("Fill", (0.40, 0.00, 0.55), (0, 0.05, 0.15), 1.5, 7.0, (0.98, 0.98, 1.00)),
              ("Back", (0.00, 0.35, -0.15), (0, 0.10, 0.10), 0.9, 2.5, (0.78, 0.86, 1.00))]
elif COMP == "arc":
    # five peers standing side by side, world-space so they share the tree's viewpoint
    TARGET_SIZE = 0.248
    LENS = 30.0
    LEAN = {i: 0 for i in HEARTS}
    HEART_FILE = {i: i for i in HEARTS}
    # X is spaced for even *on-screen* clearance, not even world spacing. Three things
    # break the naive layout: the inner hearts sit further from the camera so uniform
    # world spacing renders them crowded; the five anatomies genuinely differ in
    # projected width (166/133/122/135/165 px measured); and each heart's centroid sits
    # off its own placement point by up to 12 px. Solved back from a floor=none render
    # for 26 px gaps throughout and a 7% trim margin.
    # Arc depth kept shallow on purpose: a steeper sweep drops the end hearts away
    # diagonally, so their silhouette clearance grows to ~2.7x the inner pairs and the
    # row reads as "three plus two" however even the column gaps are made.
    # Final offsets tuned against measured *silhouette* clearance, not bounding-box
    # gaps: even column gaps still left the end pairs ~1.6x looser than the inner ones.
    WORLD_POS = {1: (-0.352, 0.24), 2: (-0.205, 0.08), 3: (-0.006, 0.0),
                 4: (0.193, 0.08), 5: (0.343, 0.24)}
    # same orbit rig as the tree: ELEV (degrees above the floor) drives the camera
    # JMCC sets the artwork in its own window below the masthead rather than
    # overlaying type on it, so no headroom needs reserving: fill the square.
    _CDIST = 0.845
    _e = math.radians(ELEV)
    CAM_TARGET = Vector((0.0, 0.030, 0.12))
    CAM_LOC = CAM_TARGET + Vector((0.0, math.sin(_e), math.cos(_e))) * _CDIST
    LIGHTS = TREE_LIGHTS
    FOCUS, FSTOP = _CDIST, 20.0
    SNAP = True
    HERO_WIRE = False   # five peers: singling one out contradicts the paper's claim
    FLOOR_GAP = 0.0
    FADE_CZ, FADE_R = 0.05, 1.6
    GRID_CELL = 0.10
    FLOOR_ROUGH = 0.16  # softer than a mirror: reflections read as sheen, not copies
elif COMP == "mirror":
    # one flesh heart on the plane; its "reflection" is a downsampled mesh below it
    TARGET_SIZE = 0.38
    LENS = 30.0
    HEARTS = [1]
    LEAN = {1: 0}
    WORLD_POS = {1: (0.0, 0.0)}
    CAM_LOC = Vector((0.0, 0.26, 0.86)); CAM_TARGET = Vector((0.0, -0.03, 0.00))
    LIGHTS = TREE_LIGHTS
    FOCUS, FSTOP = 0.90, 20.0
    SNAP = True
    HERO_WIRE = False
    FLESH = True
    SEE_THROUGH = 0.88   # look down into the plane to the mesh underneath
    DIGITAL_HEARTS = [1]
    DIGITAL_STYLE = "green"
    FLOOR_GAP = 0.0
    FADE_CZ, FADE_R = 0.05, 1.30
    GRID_CELL = 0.10
else:  # tree -- hearts stand at the tips of their own cluster branch
    TARGET_SIZE = 0.26
    LENS = 30.0
    LEAN = {i: 0 for i in HEARTS}
    HEART_FILE = {i: i for i in HEARTS}   # each heart on its own branch
    # Orbit at a fixed distance; ELEV (degrees above the floor) is the sweep knob.
    _CDIST = 1.12
    _e = math.radians(ELEV)
    CAM_TARGET = Vector((0.0, 0.02, 0.00))
    CAM_LOC = CAM_TARGET + Vector((0.0, math.sin(_e), math.cos(_e))) * _CDIST
    LIGHTS = TREE_LIGHTS
    FOCUS, FSTOP = _CDIST, 20.0
    SNAP = True
    HERO_WIRE = False
    FLOOR_GAP = 0.0
    FADE_CZ, FADE_R = 0.05, 1.7
    GRID_CELL = 0.10
    DIGITAL_HEARTS = list(HEARTS)   # every heart reflects as its computational model
    DIGITAL_STYLE = "chambers"
    SEE_THROUGH = 0.52         # veil the models in the surface rather than showing them plainly
    FLOOR_BLUR = 0.17          # and scatter them, so they read as reflections

# Camera basis, built explicitly from world up. Vector.to_track_quat("-Z", "Y")
# returns a 180-degree-rolled frame when the view direction points downwards,
# which silently puts world-down at the top of the image (and the floor with it).
CAM_F = (CAM_TARGET - CAM_LOC).normalized()
CAM_R = CAM_F.cross(Vector((0.0, 1.0, 0.0))).normalized()
CAM_U = CAM_R.cross(CAM_F)
if CAM_ROLL:
    _r = math.radians(CAM_ROLL)
    CAM_R, CAM_U = (CAM_R * math.cos(_r) + CAM_U * math.sin(_r),
                    -CAM_R * math.sin(_r) + CAM_U * math.cos(_r))
CAM_MAT = Matrix.Translation(CAM_LOC) @ Matrix(((CAM_R.x, CAM_U.x, -CAM_F.x),
                                                (CAM_R.y, CAM_U.y, -CAM_F.y),
                                                (CAM_R.z, CAM_U.z, -CAM_F.z))).to_4x4()


def i2w(h, v, depth):
    return np.array(CAM_LOC + depth * CAM_F + (h * depth) * CAM_R + (v * depth) * CAM_U)


if COMP == "tree":
    POS = {i: np.array([tree_xz(TREE_TIPS_PX[i])[0], 0.0, tree_xz(TREE_TIPS_PX[i])[1]]) for i in HEARTS}
elif WORLD_POS is not None:
    POS = {i: np.array([WORLD_POS[i][0], 0.0, WORLD_POS[i][1]]) for i in HEARTS}
else:
    POS = {i: i2w(*IMG[i]) for i in HEARTS}
CAM_LOC_NP = np.array([float(CAM_LOC.x), float(CAM_LOC.y), float(CAM_LOC.z)])

# ---------------------------------------------------------------------- build ---
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

if FLESH:
    flesh_mat = make_flesh("Myocardium")
    red_mat = blue_mat = grey_mat = flesh_mat
else:
    # G/B floor raised from (0.012, 0.02): transmission multiplies the base colour
    # per bounce, so near-zero G/B collapses deep reds to a pure primary far outside
    # CMYK -- it would print as a flat slab. This keeps the darkest reds in gamut.
    red_mat = make_glass("RedGlass", (0.56, 0.075, 0.065))
    blue_mat = make_glass("BlueGlass", (0.02, 0.05, 0.55))
    grey_mat = make_glass("GreyGlass", (0.70, 0.70, 0.74), rough=0.04, trans=0.80)

worlds = {}
faces_by_h = {}
midx_by_h = {}
for i in HEARTS:
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
    midx = lut[np.clip(mode, 0, mx)]

    c_local = (coords.min(0) + coords.max(0)) / 2.0
    s = TARGET_SIZE / float((coords.max(0) - coords.min(0)).max())
    view = (coords - c_local) @ R.T                       # [left, up, ant]
    P = POS[i]

    to_cam = CAM_LOC_NP - P; to_cam[1] = 0.0
    if np.linalg.norm(to_cam) < 1e-4:
        to_cam = np.array([0.0, 0.0, -1.0])
    t_ant = to_cam / np.linalg.norm(to_cam)               # anterior faces the camera
    t_up = np.array([0.0, 1.0, 0.0])
    t_left = np.cross(t_up, t_ant)
    b = math.radians(LEAN[i])
    t_ant2 = t_ant * math.cos(b) + t_up * math.sin(b)
    t_up2 = t_up * math.cos(b) - t_ant * math.sin(b)
    view = view @ np.column_stack([t_left, t_up2, t_ant2]).T
    worlds[i] = view * s + P
    faces_by_h[i] = faces
    midx_by_h[i] = midx

# floor height + optional snap
low = min(float(worlds[i][:, 1].min()) for i in HEARTS)
FLOOR_Y = low - FLOOR_GAP
print(f"[geom] lowest heart y={low:.4f}  floor y={FLOOR_Y:.4f}  camera y={float(CAM_LOC.y):.4f}")
if SNAP:
    for i in HEARTS:
        worlds[i][:, 1] += (FLOOR_Y - float(worlds[i][:, 1].min()))

for i in HEARTS:
    me = build_world(f"Heart_{i}", worlds[i], faces_by_h[i], midx_by_h[i])
    me.materials.append(red_mat); me.materials.append(blue_mat); me.materials.append(grey_mat)
    ob = bpy.data.objects.new(f"Heart_{i}", me); scene.collection.objects.link(ob)
    if i in DIGITAL_HEARTS:
        # its real reflection would compete with the model standing in for it
        ob.visible_glossy = False

# The "reflections": each heart mirrored through the floor plane, then decimated
# hard so the coarse model reads as the computational twin of the anatomy above.
# chambers need a few more triangles than the plain green ghost to stay legible
tgt = 2600 if DIGITAL_STYLE == "chambers" else MIRROR_TARGET_TRIS
if DIGITAL_STYLE == "chambers" and DIGITAL_HEARTS:
    # one depth ramp shared by all of them: every heart is snapped to the same plane
    _deep = min(2.0 * FLOOR_Y - float(worlds[k][:, 1].max()) for k in DIGITAL_HEARTS)
    ghosts = [make_mesh_ghost(nm, col, yfade=(FLOOR_Y, _deep)) for nm, col in
              (("GhostRed", (0.62, 0.06, 0.07)),
               ("GhostBlue", (0.07, 0.12, 0.62)),
               ("GhostGrey", (0.62, 0.62, 0.66)))]
else:
    ghosts = None
for k in DIGITAL_HEARTS:
    w = worlds[k]; f = faces_by_h[k]
    mir = w.copy(); mir[:, 1] = 2.0 * FLOOR_Y - mir[:, 1]
    mdepth = float(mir[:, 1].min())
    if ghosts is not None:
        mme = build_world(f"Mirror_mesh_{k}", mir, f, midx_by_h[k])
        for g in ghosts:
            mme.materials.append(g)
    else:
        mme = build_world(f"Mirror_mesh_{k}", mir, f)
        mme.materials.append(make_wireglow(f"MirrorWire_{k}", FIG_GREEN, wire_size=0.9,
                                           strength=2.2, pixel=True,
                                           yfade=(FLOOR_Y, mdepth)))
    mob = bpy.data.objects.new(f"Mirror_mesh_{k}", mme); scene.collection.objects.link(mob)
    dec = mob.modifiers.new("Decimate", "DECIMATE")
    dec.ratio = min(1.0, tgt / max(1, len(f)))
if DIGITAL_HEARTS:
    print(f"[digital] hearts={DIGITAL_HEARTS} style={DIGITAL_STYLE} target~{tgt} tris")

if not DIGITAL_HEARTS and HERO_WIRE:
    # position-1 hero keeps the LV wireframe accent from the contest renders
    w = worlds[1]; f = faces_by_h[1]
    lvm = (midx_by_h[1] == 0)
    lvf = f[lvm]; lvu = np.unique(lvf)
    rmp = np.full(lvu.max() + 1, -1, dtype=np.int32); rmp[lvu] = np.arange(lvu.size, dtype=np.int32)
    lvw = w[lvu]; c0 = lvw.mean(0); lvw = c0 + (lvw - c0) * 1.004
    ovme = build_world("LV_wire", lvw, rmp[lvf])
    ovme.materials.append(make_wireglow("LV_WireGlow", WARM_WHITE, wire_size=0.6, strength=2.5))
    ov = bpy.data.objects.new("LV_wire", ovme); scene.collection.objects.link(ov)
    dec = ov.modifiers.new("Decimate", "DECIMATE"); dec.ratio = min(1.0, 6000 / max(1, len(rmp[lvf])))

# ---------------------------------------------------------------------- floor ---
if FLOOR != "none":
    L = 9.0    # large enough that the plane's own edge never enters frame
    if FLOOR == "femesh":
        n = 90
        g = np.linspace(-1.7, 1.7, n + 1)
        gx, gz = np.meshgrid(g, g, indexing="ij")
        rng = np.random.default_rng(7)
        cell = g[1] - g[0]
        jit = rng.uniform(-0.34, 0.34, size=(n + 1, n + 1, 2)) * cell
        jit[0, :] = jit[-1, :] = jit[:, 0] = jit[:, -1] = 0.0
        gx = gx + jit[:, :, 0]; gz = gz + jit[:, :, 1]
        verts = np.stack([gx.ravel(), np.full(gx.size, FLOOR_Y), gz.ravel()], axis=1)
        idx = np.arange((n + 1) * (n + 1)).reshape(n + 1, n + 1)
        a = idx[:-1, :-1].ravel(); bb = idx[1:, :-1].ravel()
        c = idx[1:, 1:].ravel(); d = idx[:-1, 1:].ravel()
        tris = np.concatenate([np.stack([a, bb, c], 1), np.stack([a, c, d], 1)], axis=0)
        fme2 = build_world("Floor", verts, tris)
        fme2.materials.append(make_femesh_floor_mat("FloorFE", cz=FADE_CZ, radius=FADE_R))
    else:
        fpts = [(-L, FLOOR_Y, -L), (L, FLOOR_Y, -L), (L, FLOOR_Y, L), (-L, FLOOR_Y, L)]
        fme2 = bpy.data.meshes.new("Floor"); fme2.from_pydata(fpts, [], [(0, 3, 2, 1)]); fme2.update()
        if FLOOR == "grid":
            fme2.materials.append(make_grid_floor_mat("FloorGrid", cell=GRID_CELL, cz=FADE_CZ,
                                                      radius=FADE_R, see_through=SEE_THROUGH,
                                                      blur=FLOOR_BLUR, refl_rough=FLOOR_ROUGH))
        else:  # tree -- dark plane, branches drawn on top
            fmat = bpy.data.materials.new("FloorDark"); fmat.use_nodes = True
            nt = fmat.node_tree; nt.nodes.clear()
            o = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(_dark_base(nt, see_through=SEE_THROUGH), o.inputs["Surface"])
            fme2.materials.append(fmat)
    fob = bpy.data.objects.new("Floor", fme2); scene.collection.objects.link(fob)

    if DRAW_TREE:
        halfw = 0.007 if FLOOR == "grid" else 0.006
        vts = []; tris = []
        for p0, p1 in TREE_PX:
            x0, z0 = tree_xz(p0); x1, z1 = tree_xz(p1)
            dx, dz = x1 - x0, z1 - z0
            ln = math.hypot(dx, dz)
            nx, nz = -dz / ln * halfw, dx / ln * halfw
            k = len(vts)
            y = FLOOR_Y + 0.0015
            vts += [[x0 + nx, y, z0 + nz], [x1 + nx, y, z1 + nz],
                    [x1 - nx, y, z1 - nz], [x0 - nx, y, z0 - nz]]
            tris += [[k, k + 1, k + 2], [k, k + 2, k + 3]]
        tme = build_world("Tree", np.array(vts), np.array(tris))
        tmat = bpy.data.materials.new("TreeGlow"); tmat.use_nodes = True
        nt = tmat.node_tree; nt.nodes.clear()
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*FIG_GREEN, 1.0)
        # brighter than the grid so the branches stay legible on top of it
        em.inputs["Strength"].default_value = 2.4 if FLOOR == "grid" else 0.9
        nt.links.new(em.outputs["Emission"], o.inputs["Surface"])
        tme.materials.append(tmat)
        tob = bpy.data.objects.new("Tree", tme); scene.collection.objects.link(tob)

# --------------------------------------------------------------------- camera ---
cd = bpy.data.cameras.new("Cam"); cd.lens = LENS
cd.sensor_fit = "VERTICAL"; cd.sensor_height = 36.0; cd.clip_start = 0.005; cd.clip_end = 100
cd.dof.use_dof = True; cd.dof.focus_distance = FOCUS; cd.dof.aperture_fstop = FSTOP
cam = bpy.data.objects.new("Cam", cd); cam.matrix_world = CAM_MAT
scene.collection.objects.link(cam); scene.camera = cam

for nm, loc, tgt, size, energy, col in LIGHTS:
    ld = bpy.data.lights.new(nm, "AREA"); ld.shape = "SQUARE"; ld.size = size; ld.energy = energy
    ld.color = col
    o = bpy.data.objects.new(nm, ld); o.location = Vector(loc)
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    o.visible_camera = False    # keep the sky pure black even if a lamp is in frame
    o.visible_glossy = False    # no broad lamp sheen on the floor -- only heart reflections
    scene.collection.objects.link(o)

world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.03, 0.03, 0.05, 1); bg.inputs["Strength"].default_value = 0.03

# --------------------------------------------------------------------- render ---
def _enable_gpu():
    """Prefer OptiX/CUDA; fall back to CPU rather than failing a long render."""
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = backend
            except (TypeError, ValueError):
                continue
            devs = prefs.get_devices_for_type(backend)
            gpus = [d for d in devs if getattr(d, "type", "") == backend]
            if not gpus:
                continue
            for d in devs:                      # GPU only: adding the CPU can slow OptiX
                d.use = (getattr(d, "type", "") == backend)
            return backend, [d.name for d in gpus]
    except Exception as exc:
        print("[gpu] setup failed:", exc)
    return None, []


scene.render.engine = "CYCLES"
_backend, _gpus = (None, []) if "cpu" in ARGS else _enable_gpu()
if _backend:
    scene.cycles.device = "GPU"
    print(f"[gpu] {_backend}: {', '.join(_gpus)}")
else:
    scene.cycles.device = "CPU"
    print("[gpu] no GPU backend available -> CPU")
scene.cycles.samples = 512 if FOURK else (32 if TEST else 96)
scene.cycles.use_denoising = True
scene.cycles.transmission_bounces = 16; scene.cycles.max_bounces = 24
scene.cycles.caustics_reflective = True; scene.cycles.caustics_refractive = True
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8" if FOURK else "16"
if FOURK:
    scene.render.image_settings.color_mode = "RGB"
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - High Contrast"
except Exception:
    pass
scene.use_nodes = True
cn = scene.node_tree; cn.nodes.clear()
rl = cn.nodes.new("CompositorNodeRLayers")
cp = cn.nodes.new("CompositorNodeComposite")
gl = cn.nodes.new("CompositorNodeGlare")
gl.glare_type = "FOG_GLOW"; gl.quality = "HIGH"; gl.threshold = GLARE_THRESHOLD; gl.size = 7
cn.links.new(rl.outputs["Image"], gl.inputs["Image"])
cn.links.new(gl.outputs["Image"], cp.inputs["Image"])

scene.render.resolution_x = scene.render.resolution_y = (4096 if FOURK else (512 if TEST else 1024))
sub = "4k" if FOURK else ("test" if TEST else "preview")
outdir = os.path.join(COVERDIR, sub)
os.makedirs(outdir, exist_ok=True)
tag = f" - e{int(round(ELEV))}" if COMP in ("tree", "arc") else ""
scene.render.filepath = os.path.join(outdir, f"cover - {COMP} - {FLOOR}{tag}.png")
print("Rendering ->", scene.render.filepath)
bpy.ops.render.render(write_still=True)
print(f"COVER DONE: {COMP} / {FLOOR}")
