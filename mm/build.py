# Mermaid Squad - Roblox-style story built from code.
# blender -b --factory-startup --python build.py -- MODE OUT [start end]
import bpy, bmesh, math, sys, os, random
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index('--') + 1:]
MODE = argv[0]; OUT = os.path.abspath(argv[1])
RNG = (int(argv[2]), int(argv[3])) if len(argv) > 3 else None
HERE = os.path.dirname(os.path.abspath(__file__))
FACEDIR = os.path.join(HERE, 'faces') if os.path.isdir(os.path.join(HERE, 'faces')) else HERE
FPS = 30; T_END = 42.48; NF = int(round(T_END * FPS))
R = math.radians

# ---------------- helpers ----------------
def lin1(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def lin(h, a=1.0):
    h = h.lstrip('#'); return tuple(lin1(int(h[i:i+2], 16) / 255) for i in (0, 2, 4)) + (a,)

MATS = {}
def mat(h, rough=0.6, emit=0.0, alpha=1.0, name=None):
    key = (h, rough, emit, alpha)
    if key in MATS: return MATS[key]
    m = bpy.data.materials.new(name or 'm_' + h)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(h)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = 0.25
    if emit:
        b.inputs['Emission Color'].default_value = lin(h)
        b.inputs['Emission Strength'].default_value = emit
    if alpha < 1: b.inputs['Alpha'].default_value = alpha
    if emit:
        try: m.emission_sampling = 'NONE'
        except Exception:
            try: m.cycles.emission_sampling = 'NONE'
            except Exception: pass
    MATS[key] = m; return m

def new_obj(name, mesh, parent=None, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, mesh); bpy.context.scene.collection.objects.link(o)
    o.parent = parent; o.location = loc; return o

def empty(name, parent=None, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(o)
    o.parent = parent; o.location = loc; return o

def box(name, size, center, m, parent=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + center[0], v.co.y * size[1] + center[1], v.co.z * size[2] + center[2]))
    bm.to_mesh(me); bm.free(); me.materials.append(m)
    return new_obj(name, me, parent)

def prim(kind, name, m, parent=None, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), **kw):
    getattr(bpy.ops.mesh, 'primitive_' + kind + '_add')(**kw)
    o = bpy.context.object; o.name = name
    o.data.materials.append(m)
    if kind in ('uv_sphere', 'cone', 'torus', 'cylinder'):
        for p in o.data.polygons: p.use_smooth = kind != 'cylinder' or True
    o.parent = parent; o.location = loc; o.scale = scale; o.rotation_euler = rot
    return o

def ease_back(x, s=2.2):
    x = max(0.0, min(1.0, x)); x -= 1
    return x * x * ((s + 1) * x + s) + 1
def smooth(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)

# ---------------- scene ----------------
sc = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = int(os.environ.get('HQ_SAMPLES', '6'))
sc.cycles.use_denoising = os.environ.get('HQ_DENOISE') == '1'
if sc.cycles.use_denoising:
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'; sc.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
sc.cycles.max_bounces = 2; sc.cycles.use_light_tree = False; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1
sc.cycles.transmission_bounces = 2; sc.cycles.transparent_max_bounces = 8
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.cycles.blur_glossy = 1.0; sc.cycles.sample_clamp_indirect = 1.5; sc.cycles.sample_clamp_direct = 3
sc.render.resolution_x = int(os.environ.get('HQ_W', '432')); sc.render.resolution_y = int(os.environ.get('HQ_H', '768')); sc.render.resolution_percentage = 100
sc.render.fps = FPS; sc.frame_start = 0; sc.frame_end = NF - 1
sc.render.use_motion_blur = False
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
sc.render.image_settings.file_format = 'PNG'
sc.render.use_persistent_data = True

# world: sky gradient B8D9FF horizon -> 3378F7 overhead
w = bpy.data.worlds.new('sky'); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
ramp = nt.nodes.new('ShaderNodeValToRGB'); bg = nt.nodes.new('ShaderNodeBackground'); wo = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(tc.outputs['Generated'], sep.inputs[0]); nt.links.new(sep.outputs['Z'], ramp.inputs[0])
ramp.color_ramp.elements[0].position = 0.5; ramp.color_ramp.elements[0].color = lin('#B8D9FF')
ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = lin('#3378F7')
nt.links.new(ramp.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.9
nt.links.new(bg.outputs[0], wo.inputs[0])

sun_d = bpy.data.lights.new('sun', 'SUN'); sun_d.energy = 3.5; sun_d.angle = R(3); sun_d.color = (1.0, 0.95, 0.85)
sun = new_obj('sun', sun_d); sun.rotation_euler = Euler((R(90 - 42), 0, R(-28)))

# ---------------- faces ----------------
FACE_NAMES = ['smile', 'happy', 'angry', 'scared', 'shock', 'determined', 'choke', 'openwide', 'eat']
IMGS = {n: bpy.data.images.load(os.path.join(FACEDIR, n + '.png')) for n in FACE_NAMES}

def face_material(name, skin_hex, imgs, mode='head'):
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; Lk = m.node_tree.links
    b = N['Principled BSDF']; b.inputs['Roughness'].default_value = 0.6; b.inputs['Specular IOR Level'].default_value = 0.2
    tc = N.new('ShaderNodeTexCoord'); sp = N.new('ShaderNodeSeparateXYZ'); Lk.new(tc.outputs['Object'], sp.inputs[0])
    if mode == 'head':
        negy = N.new('ShaderNodeMath'); negy.operation = 'MULTIPLY'; negy.inputs[1].default_value = -1
        Lk.new(sp.outputs['Y'], negy.inputs[0])
        at = N.new('ShaderNodeMath'); at.operation = 'ARCTAN2'
        Lk.new(sp.outputs['X'], at.inputs[0]); Lk.new(negy.outputs[0], at.inputs[1])
        u = N.new('ShaderNodeMath'); u.operation = 'MULTIPLY_ADD'; u.inputs[1].default_value = 1 / R(130); u.inputs[2].default_value = 0.5
        Lk.new(at.outputs[0], u.inputs[0])
        v = N.new('ShaderNodeMath'); v.operation = 'MULTIPLY_ADD'; v.inputs[1].default_value = 1 / 1.22; v.inputs[2].default_value = 0.5
        Lk.new(sp.outputs['Z'], v.inputs[0])
    else:  # plane in XZ, size 1
        u = N.new('ShaderNodeMath'); u.operation = 'ADD'; u.inputs[1].default_value = 0.5; Lk.new(sp.outputs['X'], u.inputs[0])
        v = N.new('ShaderNodeMath'); v.operation = 'ADD'; v.inputs[1].default_value = 0.5; Lk.new(sp.outputs['Z'], v.inputs[0])
    cmb = N.new('ShaderNodeCombineXYZ'); Lk.new(u.outputs[0], cmb.inputs[0]); Lk.new(v.outputs[0], cmb.inputs[1])
    col = N.new('ShaderNodeRGB'); col.outputs[0].default_value = lin(skin_hex)
    cur_c = col.outputs[0]; asum = None; weights = {}
    for k, img in imgs.items():
        tx = N.new('ShaderNodeTexImage'); tx.image = img; tx.extension = 'CLIP'; tx.interpolation = 'Linear'
        Lk.new(cmb.outputs[0], tx.inputs[0])
        wv = N.new('ShaderNodeValue'); wv.outputs[0].default_value = 0.0; weights[k] = wv
        mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
        Lk.new(tx.outputs['Alpha'], mul.inputs[0]); Lk.new(wv.outputs[0], mul.inputs[1])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'
        Lk.new(mul.outputs[0], mx.inputs['Factor']); Lk.new(cur_c, mx.inputs[6]); Lk.new(tx.outputs['Color'], mx.inputs[7])
        cur_c = mx.outputs[2]
        if mode != 'head':
            if asum is None: asum = mul.outputs[0]
            else:
                ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; Lk.new(asum, ad.inputs[0]); Lk.new(mul.outputs[0], ad.inputs[1]); asum = ad.outputs[0]
    Lk.new(cur_c, b.inputs['Base Color'])
    if mode != 'head': Lk.new(asum, b.inputs['Alpha'])
    return m, weights


# ---------------- character ----------------
class Char:
    def __init__(s, name, skin, torso, arms, legs, shoes, hair, style):
        s.root = empty(name)
        s.body = empty(name + '_body', s.root, (0, 0, 2))
        box(name + '_torso', (2, 1, 2), (0, 0, 1), mat(torso), s.body)
        s.sh = {}
        for side, x in (('L', -1.5), ('R', 1.5)):
            p = empty(name + '_arm' + side, s.body, (x, 0, 1.95))
            box(name + '_armm' + side, (1, 1, 2), (0, 0, -0.95), mat(arms), p)
            box(name + '_hand' + side, (1.0, 1.0, 0.45), (0, 0, -1.75), mat(skin), p)
            s.sh['arm' + side] = p
            h = empty(name + '_leg' + side, s.root, (x / 3, 0, 2))
            box(name + '_legm' + side, (1, 1, 1.62), (0, 0, -0.81), mat(legs), h)
            box(name + '_shoe' + side, (1.02, 1.04, 0.38), (0, -0.01, -1.81), mat(shoes), h)
            s.sh['leg' + side] = h
        s.head = empty(name + '_headp', s.body, (0, 0, 2.0))
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.62, depth=1.22)
        hd = bpy.context.object; hd.name = name + '_head'; hd.parent = s.head; hd.location = (0, 0, 0.66)
        for p in hd.data.polygons: p.use_smooth = True
        bv = hd.modifiers.new('bev', 'BEVEL'); bv.width = 0.22; bv.segments = 5; bv.limit_method = 'ANGLE'
        fm, s.fw = face_material(name + '_face', skin, IMGS, 'head'); hd.data.materials.append(fm)
        hm = mat(hair, 0.5)
        if style == 'bun':
            prim('uv_sphere', name + '_cap', hm, s.head, (0, 0.06, 1.12), (0.7, 0.7, 0.42), segments=24, ring_count=12)
            prim('uv_sphere', name + '_bun', hm, s.head, (0, 0.05, 1.55), (0.42, 0.42, 0.38), segments=24, ring_count=12)
            box(name + '_hb', (1.3, 0.35, 1.2), (0, 0.5, 0.75), hm, s.head)
            box(name + '_hsl', (0.22, 0.9, 0.9), (-0.66, 0.15, 0.8), hm, s.head)
            box(name + '_hsr', (0.22, 0.9, 0.9), (0.66, 0.15, 0.8), hm, s.head)
        elif style == 'long':
            box(name + '_htop', (1.42, 1.42, 0.36), (0, 0.03, 1.32), hm, s.head)
            box(name + '_hback', (1.45, 0.45, 2.0), (0, 0.52, 0.45), hm, s.head)
            box(name + '_hsl', (0.26, 1.0, 1.9), (-0.7, 0.12, 0.42), hm, s.head)
            box(name + '_hsr', (0.26, 1.0, 1.9), (0.7, 0.12, 0.42), hm, s.head)
            box(name + '_bang', (1.25, 0.2, 0.26), (0, -0.62, 1.2), hm, s.head)
            for sx in (-1, 1):  # bunny ears
                e = empty(name + '_ear%d' % sx, s.head, (0.36 * sx, 0.05, 1.45)); e.rotation_euler = (0, R(-14 * sx), 0)
                box(name + '_earo%d' % sx, (0.34, 0.16, 1.1), (0, 0, 0.55), mat('#FBF3F6', 0.5), e)
                box(name + '_eari%d' % sx, (0.18, 0.18, 0.8), (0, -0.02, 0.55), mat('#FF9EC4', 0.5), e)
            box(name + '_band', (1.46, 0.3, 0.16), (0, 0.0, 1.42), mat('#FBF3F6', 0.5), s.head)
        elif style == 'short':
            box(name + '_htop', (1.48, 1.48, 0.5), (0, 0.02, 1.36), hm, s.head)
            box(name + '_hback', (1.45, 0.38, 0.95), (0, 0.55, 0.95), hm, s.head)
            box(name + '_hsl', (0.22, 1.0, 0.6), (-0.68, 0.1, 1.0), hm, s.head)
            box(name + '_hsr', (0.22, 1.0, 0.6), (0.68, 0.1, 1.0), hm, s.head)
            box(name + '_quiff', (1.0, 0.5, 0.3), (0.15, -0.5, 1.45), hm, s.head)
        else:  # bob
            box(name + '_htop', (1.45, 1.45, 0.42), (0, 0.02, 1.33), hm, s.head)
            box(name + '_hback', (1.45, 0.4, 1.25), (0, 0.55, 0.78), hm, s.head)
            box(name + '_hsl', (0.26, 1.2, 1.05), (-0.7, 0.05, 0.82), hm, s.head)
            box(name + '_hsr', (0.26, 1.2, 1.05), (0.7, 0.05, 0.82), hm, s.head)
            box(name + '_bang', (1.3, 0.22, 0.32), (0, -0.62, 1.18), hm, s.head)
    def set_face(s, f):
        for k, v in s.fw.items(): v.outputs[0].default_value = 1.0 if k == f else 0.0
    def legs(s, on):
        for k in ('legL', 'legR'): s.sh[k].scale = (1, 1, 1) if on else (0.001,) * 3

SKY = Char('sky', '#F3CFB0', '#9FD3F2', '#9FD3F2', '#2E9BD6', '#1E1E1E', '#3A2620', 'long')
box('sky_vest', (2.06, 1.06, 1.2), (0, 0, 1.2), mat('#2A2A30'), SKY.body)
RUBY = Char('ruby', '#F3CFB0', '#1C1C22', '#1C1C22', '#1E1E1E', '#121212', '#E3262E', 'bob')
RSKIRT = box('ruby_skirt', (2.12, 1.12, 0.8), (0, 0, 1.7), mat('#F6E3EA'), RUBY.root)
box('ruby_trim', (2.08, 1.06, 0.18), (0, 0, 1.25), mat('#E8B33A', 0.35), RUBY.body)
box('ruby_cap', (1.5, 1.5, 0.3), (0, 0.0, 1.5), mat('#E3262E', 0.5), RUBY.head)
MAX = Char('max', '#EFC6A3', '#3FC1B0', '#3FC1B0', '#5A7FB8', '#F2F2F2', '#FF4F9A', 'short')
box('max_tee', (0.8, 1.04, 1.8), (0, 0, 1.0), mat('#F7F7F7'), MAX.body)
for i, (x, z) in enumerate([(-0.75, 1.5), (0.7, 0.6), (-0.6, 0.4), (0.75, 1.6)]):
    box('max_flower%d' % i, (0.34, 1.04, 0.34), (x, 0, z), mat('#FF5C8A'), MAX.body)
NAINA = Char('naina', '#F3CFB0', '#A3A3AA', '#A3A3AA', '#22306E', '#F2F2F2', '#231A16', 'bun')
box('naina_lan', (0.25, 1.04, 1.6), (0, 0, 1.15), mat('#1E1E1E'), NAINA.body)
CH = {'SKY': SKY, 'RUBY': RUBY, 'MAX': MAX, 'NAINA': NAINA}

# ---------------- mermaid tails ----------------
def tail(name, col):
    rt = empty(name)
    m = mat(col, 0.22, 0.12)
    bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=0.3, radius2=1.18, depth=1.95)
    c = bpy.context.object; c.name = name + '_b'; c.data.materials.append(m); c.parent = rt
    c.location = (0, 0, 1.2); c.scale = (1.0, 0.68, 1.0)
    for p in c.data.polygons: p.use_smooth = True
    box(name + '_belt', (2.3, 1.5, 0.28), (0, 0, 2.12), mat(col, 0.3, 0.35), rt)
    fm = mat(col, 0.25, 0.3)
    for sx in (-1, 1):
        prim('uv_sphere', name + '_fin%d' % sx, fm, rt, (0.7 * sx, -0.1, 0.22), (1.35, 0.6, 0.22), (0, R(-26 * sx), R(-10 * sx)), segments=24, ring_count=12)
    prim('uv_sphere', name + '_knot', fm, rt, (0, 0, 0.3), (0.45, 0.35, 0.3), segments=16, ring_count=8)
    for k in range(3):
        prim('torus', name + '_sh%d' % k, mat('#FFFFFF', 0.2, 0.8, 0.5), rt, (0, 0, 1.75 - k * 0.5), (1, 0.68, 1), (0, 0, 0),
             major_radius=1.0 - k * 0.2, minor_radius=0.035, major_segments=40, minor_segments=6)
    return rt
TCOL = {'SKY': '#1E9FD8', 'RUBY': '#F01F86', 'MAX': '#A63CE0', 'NAINA': '#F4A3C8'}
TAIL = {k: tail('tail_' + k, v) for k, v in TCOL.items()}
SKY_TAIL = TAIL['SKY']; SKY_TAIL.parent = SKY.root
# folded stack on Sky's chest
STACK = {}
for i, k in enumerate(['NAINA', 'MAX', 'RUBY']):
    e = empty('stack_' + k, SKY.body, (0, -0.62 - i * 0.14, 0.9 + i * 0.12)); STACK[k] = e
    m = mat(TCOL[k], 0.22, 0.2)
    box('stk_%s' % k, (2.5, 0.12, 1.1), (0, 0, 0), m, e)
    for sx in (-1, 1):
        prim('uv_sphere', 'stkf_%s%d' % (k, sx), m, e, (1.45 * sx, 0, 0.25), (0.6, 0.08, 0.3), (0, R(30 * sx), 0), segments=16, ring_count=8)
# mermaid doll
DOLL = empty('doll', SKY.body, (1.05, -1.25, 2.55))
box('doll_b', (0.45, 0.3, 0.55), (0, 0, 0.35), mat('#7FD3F5'), DOLL)
prim('cylinder', 'doll_h', mat('#F3CFB0'), DOLL, (0, 0, 0.82), (1, 1, 1), vertices=16, radius=0.2, depth=0.36)
box('doll_hair', (0.48, 0.3, 0.42), (0, 0.06, 0.95), mat('#2BD0E8'), DOLL)
prim('cone', 'doll_t', mat('#1E9FD8', 0.25, 0.3), DOLL, (0, 0, -0.25), (1, 0.7, 1), (R(180), 0, 0), vertices=16, radius1=0.24, radius2=0.08, depth=0.7)
prim('uv_sphere', 'doll_f', mat('#1E9FD8', 0.25, 0.3), DOLL, (0, 0, -0.62), (0.32, 0.08, 0.14), segments=12, ring_count=6)

# ---------------- sets ----------------
CX = 60; OX = -60
box('floor', (220, 60, 0.2), (0, 0, -0.1), mat('#CFCFD2', 0.35))
# yellow room
box('y_wall', (8, 0.4, 16), (-5.2, 3.6, 8), mat('#F5C400'))
box('b_wall', (14, 0.4, 16), (5.8, 3.8, 8), mat('#3FA9E0'))
box('y_side', (0.5, 2.6, 16), (-0.9, 2.3, 8), mat('#E2B300'))
for i in range(9): box('tile%d' % i, (0.05, 30, 0.02), (-8 + i * 2.2, -8, 0.01), mat('#B9B9BE'))
# curtain room
box('c_wall', (30, 0.4, 16), (CX, 4.2, 8), mat('#F2EEF5'))
for i in range(40):
    box('pleat%d' % i, (0.38, 0.5, 13), (CX - 13 + i * 0.66, 3.6 + 0.12 * (i % 2), 7.5), mat('#F6F2FA' if i % 2 else '#E6DCEE', 0.7))
box('c_glow', (30, 0.3, 0.6), (CX, 3.2, 13.6), mat('#E070E0', 0.5, 6.0))
box('c_glow2', (30, 0.3, 0.5), (CX, 3.2, 0.3), mat('#E070E0', 0.5, 2.5))
# office
box('o_wall', (30, 0.4, 16), (OX, 4.2, 8), mat('#F4F1EE'))
box('o_door', (3.4, 0.2, 7.2), (OX - 1.5, 4.0, 3.6), mat('#C9A8E8', 0.5, 0.6))
box('o_frame', (3.9, 0.3, 7.6), (OX - 1.5, 4.08, 3.8), mat('#DCD6CF'))
box('o_panel', (2.4, 0.2, 4.2), (OX - 4.8, 4.0, 3.6), mat('#F28A2E'))
box('o_win', (4.0, 0.2, 7.0), (OX + 4.2, 4.0, 4.2), mat('#CFE6F5', 0.2, 0.5))
box('o_wframe', (4.4, 0.3, 7.4), (OX + 4.2, 4.08, 4.2), mat('#3A3A40'))
prim('cylinder', 'plant_pot', mat('#7A5A40'), None, (OX - 8.2, 2.6, 0.7), (1, 1, 1), vertices=16, radius=0.6, depth=1.4)
prim('uv_sphere', 'plant', mat('#3F8F3A'), None, (OX - 8.2, 2.6, 2.6), (1.2, 1.2, 1.6), segments=16, ring_count=8)
for nm, x in (('ry', 0), ('rc', CX), ('ro', OX)):
    ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = 900; ld.size = 12
    new_obj(nm + 'l', ld, None, (x, -10, 12)).rotation_euler = (R(40), 0, 0)
pk = bpy.data.lights.new('pinkc', 'AREA'); pk.energy = 500; pk.size = 20; pk.color = (1, 0.6, 1)
new_obj('pinkcl', pk, None, (CX, 2.5, 13)).rotation_euler = (R(-160), 0, 0)

# like icon
LIKE = empty('like')
prim('cylinder', 'like_d', mat('#E8262E', 0.4, 1.2), LIKE, (0, 0, 0), (1, 1, 1), (R(90), 0, 0), vertices=32, radius=0.9, depth=0.15)
box('like_t1', (0.5, 0.2, 0.75), (0.15, -0.12, -0.12), mat('#FFFFFF', 0.4, 2.0), LIKE)
box('like_t2', (0.22, 0.2, 0.55), (-0.05, -0.12, 0.42), mat('#FFFFFF', 0.4, 2.0), LIKE)
box('like_t3', (0.22, 0.2, 0.7), (-0.42, -0.12, -0.12), mat('#FFFFFF', 0.4, 2.0), LIKE)

def pool(n, name, kind, m):
    out = []
    for i in range(n):
        if kind == 'sphere': o = prim('uv_sphere', name + str(i), m, None, (0, 0, -500), segments=12, ring_count=6)
        else:
            bpy.ops.mesh.primitive_circle_add(vertices=5, radius=1, fill_type='TRIANGLE_FAN'); o = bpy.context.object; o.name = name + str(i)
            for k, v in enumerate(o.data.vertices):
                if k > 0 and k % 2 == 0: pass
            o.data.materials.append(m); o.rotation_euler = (R(90), 0, 0)
        out.append(o)
    return out
PUFF = pool(9, 'puff', 'sphere', mat('#FFFFFF', 0.5, 1.3, 0.72))
PUFF2 = pool(9, 'puffb', 'sphere', mat('#FFFFFF', 0.5, 1.3, 0.72))
SPARK = pool(14, 'spark', 'sphere', mat('#FFE14D', 0.3, 8.0))
def hide(o): o.location = (0, 0, -500); o.scale = (0.001,) * 3

# ---------------- poses ----------------
P = {
 'idle': dict(armL=(0, 0, 0), armR=(0, 0, 0), legL=(0, 0, 0), legR=(0, 0, 0), head=(0, 0, 0), body=(0, 0, 0)),
 'give': dict(armL=(R(-60), 0, R(15)), armR=(R(-60), 0, R(-15)), head=(R(4), 0, 0)),
 'grab': dict(armL=(R(-90), 0, R(10)), armR=(R(-90), 0, R(-10)), body=(R(6), 0, 0)),
 'bend': dict(armL=(R(-55), 0, R(8)), armR=(R(-55), 0, R(-8)), head=(R(10), 0, 0), body=(R(32), 0, 0)),
 'hop':  dict(armL=(R(-150), R(25), 0), armR=(R(-150), R(-25), 0), head=(R(-8), 0, 0)),
 'pose': dict(armL=(R(-10), R(32), 0), armR=(R(-165), R(-15), 0), head=(R(-6), R(8), 0)),
 'cross': dict(armL=(R(-78), 0, R(48)), armR=(R(-70), 0, R(-48)), head=(R(-5), 0, 0)),
 'facepalm': dict(armL=(R(-158), 0, R(32)), armR=(R(-158), 0, R(-32)), head=(R(12), 0, 0), body=(R(5), 0, 0)),
 'shrug': dict(armL=(R(-25), R(55), 0), armR=(R(-25), R(-55), 0), head=(0, R(12), 0)),
 'doll': dict(armL=(R(-25), R(15), 0), armR=(R(-115), 0, R(-18)), head=(R(-4), 0, R(10))),
 'sad':  dict(armL=(R(-8), 0, R(-4)), armR=(R(-8), 0, R(4)), head=(R(18), 0, 0), body=(R(6), 0, 0)),
 'cheer': dict(armL=(R(-165), R(-25), 0), armR=(R(-165), R(25), 0), head=(R(-10), 0, 0)),
 'thumbs': dict(armL=(R(-10), R(25), 0), armR=(R(-125), 0, R(-15)), head=(R(-6), 0, 0)),
}
KEYS = ['armL', 'armR', 'legL', 'legR', 'head', 'body']
def pose_vals(n):
    d = dict(P['idle']); d.update(P[n]); return d
TL = {
 'SKY': [(0, 'idle', 'happy', 0), (0.5, 'give', 'smile', R(-20)), (1.4, 'idle', 'happy', 0), (3.6, 'give', 'smile', R(-20)), (4.7, 'idle', 'happy', 0),
         (6.8, 'give', 'smile', R(-20)), (7.9, 'idle', 'happy', 0), (28.03, 'sad', 'scared', 0), (29.98, 'sad', 'scared', R(-25)),
         (32.3, 'doll', 'eat', 0), (34.78, 'doll', 'scared', 0), (37.12, 'idle', 'shock', R(-20)), (38.0, 'idle', 'happy', 0),
         (39.6, 'cheer', 'happy', 0), (40.6, 'thumbs', 'happy', 0), (41.6, 'cheer', 'happy', 0)],
 'RUBY': [(0, 'idle', 'smile', R(25)), (0.55, 'grab', 'happy', R(25)), (1.1, 'bend', 'determined', 0), (1.75, 'hop', 'happy', 0), (2.35, 'pose', 'happy', 0),
          (2.9, 'hop', 'happy', 0), (10.17, 'pose', 'smile', 0), (12.7, 'idle', 'smile', R(15)), (13.9, 'idle', 'shock', R(30)), (15.5, 'pose', 'smile', 0),
          (18.2, 'idle', 'shock', R(-30)), (19.6, 'cross', 'angry', 0), (23.3, 'bend', 'angry', 0), (24.2, 'cross', 'angry', 0), (28.03, 'idle', 'smile', 0),
          (31.8, 'idle', 'shock', R(-35)), (34.78, 'facepalm', 'scared', 0), (36.0, 'shrug', 'scared', 0), (37.12, 'idle', 'smile', 0), (37.6, 'bend', 'happy', 0),
          (38.4, 'idle', 'happy', 0), (39.6, 'cheer', 'happy', 0), (40.6, 'thumbs', 'happy', 0), (41.6, 'cheer', 'happy', 0)],
 'MAX': [(0, 'idle', 'smile', 0), (3.6, 'idle', 'happy', R(25)), (3.95, 'grab', 'happy', R(25)), (4.3, 'bend', 'determined', 0), (4.9, 'pose', 'happy', 0),
         (6.0, 'hop', 'happy', 0), (10.17, 'idle', 'smile', 0), (13.2, 'shrug', 'shock', 0), (13.5, 'bend', 'angry', 0), (14.2, 'shrug', 'smile', 0),
         (15.5, 'cross', 'smile', 0), (17.6, 'idle', 'shock', R(25)), (19.0, 'cross', 'smile', 0), (23.2, 'idle', 'shock', R(-25)), (24.2, 'cross', 'smile', 0),
         (28.03, 'idle', 'smile', 0), (31.8, 'idle', 'shock', R(30)), (34.78, 'facepalm', 'scared', 0), (36.0, 'shrug', 'eat', 0), (37.12, 'idle', 'smile', 0),
         (37.6, 'bend', 'happy', 0), (38.7, 'idle', 'happy', 0), (39.6, 'cheer', 'happy', 0), (40.6, 'thumbs', 'happy', 0), (41.6, 'cheer', 'happy', 0)],
 'NAINA': [(0, 'idle', 'smile', 0), (6.7, 'idle', 'happy', R(25)), (7.05, 'grab', 'happy', R(25)), (7.5, 'bend', 'determined', 0), (8.1, 'pose', 'happy', 0),
           (9.6, 'hop', 'happy', 0), (10.17, 'pose', 'smile', 0), (13.2, 'idle', 'shock', R(-25)), (15.0, 'pose', 'smile', 0), (17.4, 'facepalm', 'angry', 0),
           (18.0, 'bend', 'angry', 0), (18.7, 'cross', 'smile', 0), (23.2, 'idle', 'shock', R(-30)), (24.2, 'cross', 'smile', 0), (28.03, 'idle', 'smile', 0),
           (31.8, 'idle', 'shock', R(30)), (34.78, 'facepalm', 'scared', 0), (36.0, 'shrug', 'scared', 0), (37.12, 'idle', 'smile', 0), (37.6, 'bend', 'happy', 0),
           (39.1, 'idle', 'happy', 0), (39.6, 'cheer', 'happy', 0), (40.6, 'thumbs', 'happy', 0), (41.6, 'cheer', 'happy', 0)],
}
def eval_tl(tl, t):
    idx = 0
    for i, k in enumerate(tl):
        if k[0] - 0.07 <= t: idx = i
    cur = tl[idx]; prev = tl[idx - 1] if idx > 0 else cur
    x = ease_back((t - (cur[0] - 0.07)) / 0.14) if idx > 0 else 1.0
    a = pose_vals(prev[1]); b = pose_vals(cur[1])
    out = {k: tuple(a[k][j] + (b[k][j] - a[k][j]) * x for j in range(3)) for k in KEYS}
    return out, cur[2], prev[3] + (cur[3] - prev[3]) * x

import json
_VP = os.path.join(HERE, 'proc.json')
SPEAK = [(p['who'], p['start'], p['start'] + p['dur']) for p in json.load(open(_VP))] if os.path.exists(_VP) else []
def speaking(k, t):
    return any(w == k and a <= t < b for w, a, b in SPEAK)

# tail states
WEAR = {'RUBY': (0.6, 1.4, 23.8, 38.6), 'MAX': (3.95, 4.7, 13.9, 39.0), 'NAINA': (7.05, 7.9, 18.4, 39.4)}
def tstate(k, t):
    g, w, r, w2 = WEAR[k]
    if t < g: return 'stack'
    if t < w: return 'hand'
    if t < r: return 'worn'
    if t < 37.9: return 'floor'
    if t < w2: return 'hand'
    return 'worn'

def lerp(a, b, x): return a + (b - a) * x
def char_pos(k, t):
    """returns (x, y, rotz, hopz) or None if hidden"""
    if t < 10.17:
        if k == 'SKY': return (-2.0, 0, 0, 0)
        spans = {'RUBY': (-1, 0, 2.9, 3.4), 'MAX': (3.0, 3.6, 6.0, 6.5), 'NAINA': (6.1, 6.7, 9.6, 10.17)}[k]
        a, b, c, d = spans
        if t < a or t >= d: return None
        if t < b: x = lerp(11, 2.0, smooth((t - a) / (b - a))); return (x, 0, R(-90), 0.25 * abs(math.sin(t * 14)))
        if t < c: return (2.0, 0, 0, 0)
        x = lerp(2.0, 11, smooth((t - c) / (d - c))); return (x, 0, R(90), 0)
    if t < 28.03:
        if k == 'SKY': return None
        return ({'RUBY': CX - 3.8, 'MAX': CX, 'NAINA': CX + 3.8}[k], 0, 0, 0)
    if k == 'SKY': return (OX + 5.4, 0, 0, 0)
    fx = {'RUBY': OX - 5.4, 'MAX': OX - 1.8, 'NAINA': OX + 1.8}[k]
    if t < 29.98: return None
    st = 29.98 + {'RUBY': 0.25, 'MAX': 0.0, 'NAINA': 0.12}[k]
    k2 = smooth((t - st) / 1.6)
    if k2 < 1: return (lerp(fx - 12, fx, k2), 0, R(90) * (1 - smooth((k2 - 0.8) / 0.2)), 0)
    return (fx, 0, 0, 0)

def hop_amount(k, t):
    sp = {'RUBY': [(1.75, 2.35), (2.9, 3.4)], 'MAX': [(4.9, 6.5)], 'NAINA': [(8.1, 10.17)]}.get(k, [])
    end = (39.6, 42.48)
    for a, b in sp + [end]:
        if a <= t < b: return 0.55 * abs(math.sin((t - a) * math.pi * 2.6))
    return 0

# ---------------- shots ----------------
SH = [
 (0.0, 1.6, (0, -16.5, 5.6), (0, 0, 3.4), 50, 1.2),
 (1.6, 3.2, (1.6, -9.5, 4.8), (1.6, 0, 3.0), 48, 1.0),
 (3.2, 4.9, (0.2, -16, 5.4), (0.2, 0, 3.4), 50, 1.0),
 (4.9, 6.3, (-1.0, -9.5, 5.0), (1.6, 0, 3.4), 46, 0.8),
 (6.3, 8.0, (0.3, -16, 5.4), (0.2, 0, 3.4), 50, 1.0),
 (8.0, 10.17, (2.0, -10, 4.6), (1.9, 0, 3.2), 48, 1.2),
 (10.17, 11.0, (CX, -19, 6), (CX, 0, 3.4), 56, 1.0),
 (11.0, 12.7, (CX - 3.4, -9.5, 5.0), (CX - 3.6, 0, 3.6), 44, 0.8),
 (12.7, 14.4, (CX + 0.3, -10, 4.8), (CX, 0, 3.0), 48, 0.8),
 (14.4, 16.2, (CX, -19, 6), (CX, 0, 3.4), 54, 1.2),
 (16.2, 17.5, (CX + 3.6, -9.5, 5.0), (CX + 3.8, 0, 3.6), 44, 0.6),
 (17.5, 19.6, (CX + 3.0, -11, 4.8), (CX + 3.6, 0, 3.0), 48, 1.0),
 (19.6, 21.5, (CX - 1, -19, 6), (CX, 0, 3.4), 54, 1.0),
 (21.5, 23.2, (CX - 3.2, -9.5, 5.0), (CX - 3.8, 0, 3.6), 44, 0.7),
 (23.2, 25.2, (CX - 3.0, -11, 4.8), (CX - 3.6, 0, 3.0), 48, 1.0),
 (25.2, 26.8, (CX, -19, 6), (CX, 0, 3.4), 54, 1.0),
 (26.8, 28.03, (CX + 1, -14, 5.4), (CX, 0, 3.6), 50, 1.2),
 (28.03, 29.98, (OX + 3.0, -15, 5.0), (OX + 2.6, 0, 2.6), 56, 1.6),
 (29.98, 31.2, (OX - 3, -19, 6), (OX - 3, 0, 3.4), 58, 0.8),
 (31.2, 32.3, (OX - 1.8, -14, 5.2), (OX - 1.8, 0, 3.4), 54, 0.8),
 (32.3, 33.6, (OX + 5.4, -10.5, 5.2), (OX + 5.6, 0, 4.1), 46, 0.6),
 (33.6, 34.78, (OX + 4.0, -8.6, 5.0), (OX + 5.4, 0, 4.3), 38, 0.5),
 (34.78, 36.0, (OX - 1.8, -11.5, 5.2), (OX - 1.8, 0, 3.8), 50, 0.6),
 (36.0, 37.12, (OX - 0.6, -10.5, 5.0), (OX - 1.0, 0, 3.8), 46, 0.6),
 (37.12, 38.6, (OX, -21, 6.4), (OX, 0, 3.0), 62, 1.0),
 (38.6, 40.0, (OX, -18, 5.6), (OX, 0, 3.2), 60, 0.8),
 (40.0, 41.2, (OX + 2, -14, 4.8), (OX + 1, 0, 3.4), 54, 0.8),
 (41.2, 42.48, (OX, -20, 6.4), (OX, 0, 3.4), 62, -1.2),
]
cam_d = bpy.data.cameras.new('cam'); cam_d.sensor_fit = 'VERTICAL'; cam_d.dof.use_dof = False
cam = new_obj('cam', cam_d); sc.camera = cam; cam_d.clip_start = 0.1; cam_d.clip_end = 300
def shot_at(t):
    for i, s in enumerate(SH):
        if s[0] <= t < s[1]: return i, s
    return len(SH) - 1, SH[-1]
def set_cam(t):
    i, (t0, t1, loc, tgt, fov, push) = shot_at(t)
    p = smooth((t - t0) / max(0.01, (t1 - t0) * 0.95))
    loc = Vector(loc); tgt = Vector(tgt); d = (tgt - loc).normalized(); loc = loc + d * push * p
    cam.location = loc; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cam_d.angle = R(fov)
    return i

EVENTS = [(1.4, 'RUBY'), (4.7, 'MAX'), (7.9, 'NAINA'), (13.9, 'MAX'), (18.4, 'NAINA'), (23.8, 'RUBY'),
          (38.6, 'RUBY'), (39.0, 'MAX'), (39.4, 'NAINA')]
def puff_fx(t, pool, evs, cpos):
    act = None
    for te, k in evs:
        if te <= t < te + 0.6: act = (te, k)
    for o in pool: hide(o)
    if not act: return None
    te, k = act; c = cpos(k, te)
    if c is None: return None
    c = Vector(c); dt = t - te; rnd = random.Random(int(te * 100))
    for i, o in enumerate(pool):
        a = i / len(pool) * 2 * math.pi; off = Vector((math.cos(a) * 1.3, rnd.uniform(-0.6, 0.2), math.sin(a) * 1.6))
        g = min(1, dt / 0.12); shrink = 1 - smooth((dt - 0.25) / 0.3)
        r = (0.6 + 0.4 * rnd.random()) * g * shrink
        o.location = c + off * (1 + dt * 1.2); o.scale = (max(r, 0.001),) * 3
    return (te, c)

def update(scene, depsgraph=None):
    f = scene.frame_current; t = f / FPS
    set_cam(t)
    for k, ch in CH.items():
        pp = char_pos(k, t)
        if pp is None:
            ch.root.location = (0, 0, -500); ch.root.scale = (0.001,) * 3; continue
        ch.root.scale = (1, 1, 1)
        x, y, rz, hz0 = pp; hz = hz0 + hop_amount(k, t)
        ch.root.location = (x, y, hz); ch.root.rotation_euler = (0, 0, rz)
        pv, face, hturn = eval_tl(TL[k], t)
        ex = {}
        walking = (k != 'SKY') and (rz != 0) and hz0 == 0 and t > 29.9 and t < 32.0
        if walking or (t < 10.17 and k != 'SKY' and rz != 0 and tstate(k, t) != 'worn'):
            sw = math.sin(t * 2 * math.pi * 2.2) * R(28)
            ex['legL'] = (sw, 0, 0); ex['legR'] = (-sw, 0, 0); ex['armL'] = (-sw, 0, 0); ex['armR'] = (sw, 0, 0)
        if k == 'SKY' and 32.3 <= t < 34.78:
            ex['head'] = (0, R(6) * math.sin(t * 7), R(10) * math.sin(t * 3.1)); ex['body'] = (0, R(4) * math.sin(t * 3.1), 0)
        idle_sway = 0.04 * math.sin(t * 2 * math.pi * 0.8 + len(k))
        for kk in ('armL', 'armR', 'legL', 'legR'):
            v = pv[kk]; d = ex.get(kk, (0, 0, 0)); ch.sh[kk].rotation_euler = (v[0] + d[0], v[1] + d[1], v[2] + d[2])
        hv = pv['head']; d = ex.get('head', (0, 0, 0)); ch.head.rotation_euler = (hv[0] + d[0], hv[1] + d[1], hturn + d[2])
        bv_ = pv['body']; d = ex.get('body', (0, 0, 0)); ch.body.rotation_euler = (bv_[0] + d[0], bv_[1] + d[1], bv_[2] + d[2] + idle_sway * 0.3)
        ch.body.location = (0, 0, 2 + 0.05 * math.sin(t * 5 + len(k)))
        if speaking(k, t) and face in ('smile', 'happy', 'determined', 'angry', 'shock', 'scared'):
            if int(t / 0.11) % 2 == 0: face = 'eat' if face in ('smile', 'happy') else ('openwide' if face != 'scared' else 'scared')
        ch.set_face(face)
        worn = (k == 'SKY') or tstate(k, t) == 'worn'
        ch.legs(not worn)
        if k == 'RUBY': RSKIRT.scale = (0.001,) * 3 if worn else (1, 1, 1)
    # tails
    for k in ('RUBY', 'MAX', 'NAINA'):
        tr = TAIL[k]; st = tstate(k, t); ch = CH[k]; pp = char_pos(k, t)
        STACK[k].scale = (1, 1, 1) if st == 'stack' else (0.001,) * 3
        tr.parent = None
        if st == 'worn' and pp is not None:
            tr.location = ch.root.location; tr.rotation_euler = ch.root.rotation_euler; tr.scale = (1, 1, 1)
        elif st == 'hand' and pp is not None:
            bpy.context.view_layer.update()
            c = ch.root.matrix_world @ Vector((0, -1.7, 1.2))
            tr.location = c; tr.rotation_euler = (R(8), 0, ch.root.rotation_euler.z); tr.scale = (0.75,) * 3
        elif st == 'floor':
            if t < 28.03: base = {'RUBY': CX - 3.8, 'MAX': CX, 'NAINA': CX + 3.8}[k]
            else: base = {'RUBY': OX - 5.4, 'MAX': OX - 1.8, 'NAINA': OX + 1.8}[k]
            tr.location = (base + 0.3, -2.6, 0.62); tr.rotation_euler = (0, R(-90), R(8)); tr.scale = (0.8,) * 3
        else:
            hide(tr)
    SKY_TAIL.scale = (1, 1, 1) if SKY.root.scale[0] > 0.5 else (0.001,) * 3
    DOLL.scale = (1, 1, 1) if 32.3 <= t < 34.78 else (0.001,) * 3
    def cpos(k, te):
        pp = char_pos(k, te)
        return None if pp is None else (pp[0], -0.6, 2.4)
    evA = [e for i, e in enumerate(EVENTS) if i % 2 == 0]; evB = [e for i, e in enumerate(EVENTS) if i % 2 == 1]
    a1 = puff_fx(t, PUFF, evA, cpos); a2 = puff_fx(t, PUFF2, evB, cpos)
    act = a1 or a2; rnd = random.Random(f)
    for i, o in enumerate(SPARK):
        if act:
            te, c = act; dt = t - te; a = i / len(SPARK) * 6.283 + dt * 3
            o.location = c + Vector((math.cos(a), -0.9, math.sin(a))) * (0.6 + 3.2 * smooth(dt / 0.6)); o.scale = (0.14 * (1 - smooth((dt - 0.35) / 0.25)) + 0.001,) * 3
        else: hide(o)
    if t >= 41.0:
        k2 = ease_back((t - 41.0) / 0.2); LIKE.location = (OX + 3.6, -5, 8.2); LIKE.scale = (max(k2, 0.001) * 1.4,) * 3
        LIKE.rotation_euler = (0, 0, R(6) * math.sin(t * 9))
    else: hide(LIKE)

bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(update)

os.makedirs(OUT, exist_ok=True)
if MODE == 'stills':
    for i, s in enumerate(SH):
        f = int(((s[0] + s[1]) / 2) * FPS)
        if RNG and not (RNG[0] <= i <= RNG[1]): continue
        sc.frame_set(f); update(sc)
        sc.render.filepath = os.path.join(OUT, 'shot_%02d.png' % i)
        bpy.ops.render.render(write_still=True); print('STILL', i, f, flush=True)
elif MODE == 'frames':
    a, b = RNG if RNG else (0, NF - 1)
    for f in range(a, b + 1):
        p = os.path.join(OUT, 'f_%04d.png' % f)
        if os.path.exists(p): continue
        sc.frame_set(f); update(sc)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True); print('FRAME', f, flush=True)
