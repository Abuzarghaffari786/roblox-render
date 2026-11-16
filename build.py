# Fish Bone Rescue - Roblox-style story built from code.
# blender -b --factory-startup --python build.py -- MODE OUT [start end]
import bpy, bmesh, math, sys, os, random
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index('--') + 1:]
MODE = argv[0]; OUT = os.path.abspath(argv[1])
RNG = (int(argv[2]), int(argv[3])) if len(argv) > 3 else None
HERE = os.path.dirname(os.path.abspath(__file__))
FACEDIR = os.path.join(HERE, 'faces') if os.path.isdir(os.path.join(HERE, 'faces')) else HERE
FPS = 30; T_END = 36.4; NF = int(round(T_END * FPS))
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
BIMGS = {n: bpy.data.images.load(os.path.join(FACEDIR, 'bone_' + n + '.png')) for n in ('smirk', 'angry', 'shock')}

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
        hd.scale = (1.0, 1.0, 1.0)
        fm, s.fw = face_material(name + '_face', skin, IMGS, 'head'); hd.data.materials.append(fm)
        hm = mat(hair, 0.5)
        if style == 'bun':
            prim('uv_sphere', name + '_cap', hm, s.head, (0, 0.06, 1.12), (0.7, 0.7, 0.42), segments=24, ring_count=12)
            prim('uv_sphere', name + '_bun', hm, s.head, (0, 0.05, 1.55), (0.42, 0.42, 0.38), segments=24, ring_count=12)
            box(name + '_hb', (1.3, 0.35, 1.2), (0, 0.5, 0.75), hm, s.head)
            box(name + '_hsl', (0.22, 0.9, 0.9), (-0.66, 0.15, 0.8), hm, s.head)
            box(name + '_hsr', (0.22, 0.9, 0.9), (0.66, 0.15, 0.8), hm, s.head)
        else:  # bob
            box(name + '_htop', (1.45, 1.45, 0.42), (0, 0.02, 1.33), hm, s.head)
            box(name + '_hback', (1.45, 0.4, 1.25), (0, 0.55, 0.78), hm, s.head)
            box(name + '_hsl', (0.26, 1.2, 1.05), (-0.7, 0.05, 0.82), hm, s.head)
            box(name + '_hsr', (0.26, 1.2, 1.05), (0.7, 0.05, 0.82), hm, s.head)
            box(name + '_bang', (1.3, 0.22, 0.32), (0, -0.62, 1.18), hm, s.head)
        s.cur_face = None
    def set_face(s, f):
        for k, v in s.fw.items(): v.outputs[0].default_value = 1.0 if k == f else 0.0

LILY = Char('lily', '#F2C9A5', '#F4F4F4', '#E0457B', '#2B2B38', '#1E1E1E', '#8A3FE0', 'bun')
MIA = Char('mia', '#F0C29C', '#E01F3D', '#E01F3D', '#2B5BD7', '#B0122A', '#FF3E9A', 'bob')
# shorts on Mia
box('mia_shorts', (2.06, 1.06, 0.7), (0, 0, 1.75), mat('#C8102E'), MIA.root)

# ---------------- sets ----------------
# ROOM (origin)
box('floor', (60, 60, 0.2), (0, 0, -0.1), mat('#D9D6D0'))
box('wall_pink', (14, 0.4, 14), (-6, 3.5, 7), mat('#F08FAE'))
box('wall_blue', (14, 0.4, 14), (8, 3.5, 7), mat('#3E8EE8'))
box('stripe', (6, 0.42, 1.2), (6, 3.45, 3.0), mat('#E8762B'))
box('curtain', (2.2, 0.5, 14), (7.2, 3.0, 7), mat('#F5F5F5'))
box('pillar', (1.5, 1.5, 14), (-2.2, 3.0, 7), mat('#F4A0BC'))
box('table', (6.4, 2.8, 0.35), (0, -2.0, 2.9), mat('#F1EAD8'))
box('table_front', (6.4, 0.3, 2.9), (0, -3.25, 1.45), mat('#ECE3CC'))
box('chair', (2.6, 0.5, 3.2), (0, 1.1, 3.0), mat('#F2C21B'))
# KITCHEN (x=80)
KX = 80
box('k_wall', (24, 0.4, 14), (KX, 3.6, 7), mat('#E9E9EA'))
for i in range(5): box('k_cab%d' % i, (3.8, 0.5, 4.2), (KX - 9.5 + i * 4.1, 3.2, 9.6), mat('#F4F4F4'))
box('k_niche', (8, 0.3, 3.4), (KX + 1.5, 3.3, 5.2), mat('#7E7E84'))
box('k_counter', (24, 1.6, 3.3), (KX, 2.6, 1.65), mat('#F6F6F6'))
box('k_floor', (30, 30, 0.2), (KX, 0, -0.08), mat('#CFCFD3'))
# THROAT (x=-80) tunnel along +Y
TX = -80; TZ = 7.0
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=7.2, depth=70, location=(TX, 25, TZ), rotation=(R(90), 0, 0))
tun = bpy.context.object; tun.name = 'tunnel'; tun.data.materials.append(mat('#8E1E2A', 0.45))
for p in tun.data.polygons: p.use_smooth = True
for i in range(16):
    prim('torus', 'ring%d' % i, mat('#C9505F' if i % 2 else '#A8303F', 0.4), None, (TX, 2 + i * 3.2, TZ), (1, 1, 1), (R(90), 0, 0),
         major_radius=7.0 - i * 0.18, minor_radius=0.75, major_segments=64, minor_segments=12)
box('t_end', (16, 0.2, 16), (TX, 54, TZ), mat('#120306', 1.0))
box('t_floor', (14, 40, 0.2), (TX, 15, -0.05), mat('#9C2836', 0.5))
pl = bpy.data.lights.new('tl', 'POINT'); pl.energy = 4500; pl.shadow_soft_size = 2.5; pl.color = (1, 0.85, 0.85)
tl = new_obj('tlight', pl, None, (TX, -4, 9))
pl2 = bpy.data.lights.new('tl2', 'POINT'); pl2.energy = 1500; pl2.color = (1, 0.6, 0.6)
new_obj('tlight2', pl2, None, (TX + 3, 6, 11))
kl = bpy.data.lights.new('kl', 'AREA'); kl.energy = 900; kl.size = 10
new_obj('klight', kl, None, (KX, -6, 12)).rotation_euler = (R(30), 0, 0)
rl = bpy.data.lights.new('rl', 'AREA'); rl.energy = 700; rl.size = 10
new_obj('rlight', rl, None, (0, -8, 12)).rotation_euler = (R(35), 0, 0)

# ---------------- props ----------------
def fish(name):
    r = empty(name)
    prim('uv_sphere', name + '_b', mat('#8E9AA6', 0.35), r, (0, 0, 0), (2.2, 0.75, 1.0), segments=32, ring_count=16)
    prim('cone', name + '_t', mat('#7A8794', 0.4), r, (2.6, 0, 0), (0.25, 1.0, 1.1), (0, R(-90), 0), vertices=4, radius1=1, depth=1.2)
    prim('uv_sphere', name + '_e', mat('#FFFFFF'), r, (-1.55, -0.55, 0.3), (0.22, 0.22, 0.22), segments=16, ring_count=8)
    prim('uv_sphere', name + '_p', mat('#111111'), r, (-1.6, -0.68, 0.3), (0.11, 0.11, 0.11), segments=12, ring_count=6)
    box(name + '_fin', (1.2, 0.1, 0.6), (0.2, 0, 1.0), mat('#6F7C88'), r)
    return r
FISH = fish('fish'); FISH2 = fish('fish2'); FS = 0.55

IC = empty('icecream', LILY.body, (0.38, -1.15, 1.95)); IC.rotation_euler = (R(-22), R(-22), 0)
prim('cone', 'ic_cone', mat('#D9A55B'), IC, (0, 0, 0), (1, 1, 1), (R(180), 0, 0), vertices=16, radius1=0.38, depth=1.0)
ICBALL = prim('uv_sphere', 'ic_ball', mat('#FF9CC8', 0.5), IC, (0, 0, 0.6), (0.48, 0.48, 0.45), segments=20, ring_count=10)
BOT = empty('bottle', LILY.body, (0, 0, 0))
prim('cylinder', 'bot_b', mat('#9FDcFF', 0.12, 0, 0.6), BOT, (0, 0, 0.72), (1, 1, 1), (0, 0, 0), vertices=24, radius=0.26, depth=1.05)
prim('cylinder', 'bot_w', mat('#3FA2F0', 0.15, 0, 0.8), BOT, (0, 0, 0.55), (1, 1, 1), (0, 0, 0), vertices=24, radius=0.22, depth=0.6)
prim('cylinder', 'bot_n', mat('#BDE6FF', 0.15, 0, 0.7), BOT, (0, 0, 0.12), (1, 1, 1), (0, 0, 0), vertices=16, radius=0.13, depth=0.24)
prim('cylinder', 'bot_c', mat('#1E6FD9', 0.3), BOT, (0, 0, -0.02), (1, 1, 1), (0, 0, 0), vertices=16, radius=0.14, depth=0.08)
JUG = empty('jug'); JUG.parent = LILY.sh['armR']; JUG.location = (-1.4, 0, -2.6)
prim('cylinder', 'jug_b', mat('#8FD0FF', 0.15, 0, 0.75), JUG, (0, 0, 0), (1, 1, 1), (0, R(90), 0), vertices=24, radius=0.95, depth=2.6)
prim('cylinder', 'jug_n', mat('#5BB8FF', 0.2), JUG, (-1.6, 0, 0), (1, 1, 1), (0, R(90), 0), vertices=16, radius=0.35, depth=0.7)
CHK = empty('chicken'); CHK.parent = MIA.body; CHK.location = (0, -1.6, 0.6)
prim('uv_sphere', 'chk_b', mat('#D9622B', 0.4), CHK, (0, 0, 0), (1.05, 0.8, 0.7), segments=24, ring_count=12)
prim('uv_sphere', 'chk_l1', mat('#C8541F', 0.4), CHK, (0.9, 0, 0.35), (0.6, 0.3, 0.3), segments=12, ring_count=8)
prim('uv_sphere', 'chk_l2', mat('#C8541F', 0.4), CHK, (-0.9, 0, 0.35), (0.6, 0.3, 0.3), segments=12, ring_count=8)
MUG = empty('mug'); MUG.parent = MIA.sh['armR']; MUG.location = (0, -0.3, -2.5)
prim('cylinder', 'mug_b', mat('#F5C518', 0.2, 0.3), MUG, (0, 0, 0), (1, 1, 1), (0, 0, 0), vertices=20, radius=0.5, depth=1.2)
prim('cylinder', 'mug_f', mat('#FFFFFF', 0.4), MUG, (0, 0, 0.65), (1, 1, 1), (0, 0, 0), vertices=20, radius=0.52, depth=0.18)
SAW = empty('saw'); SAW.parent = MIA.sh['armR']; SAW.location = (-0.9, -0.4, -2.3)
box('saw_body', (1.0, 1.4, 0.9), (0, 0, 0), mat('#FF7A00', 0.4), SAW)
box('saw_blade', (0.25, 0.5, 3.0), (0, -0.2, -1.8), mat('#B8BCC4', 0.25), SAW)
SAW.rotation_euler = (R(80), 0, 0)

# bone
BONE = empty('bone')
BTOP = empty('bone_top', BONE, (0, 0, 4.8)); BBOT = empty('bone_bot', BONE, (0, 0, 0))
bm_ = mat('#FAFAF5', 0.35)
prim('cylinder', 'b_spine1', bm_, BBOT, (0, 0, 2.4), (1, 1, 1), vertices=12, radius=0.24, depth=4.8)
prim('cylinder', 'b_spine2', bm_, BTOP, (0, 0, 1.8), (1, 1, 1), vertices=12, radius=0.24, depth=3.6)
for i in range(7):
    z = 0.6 + i * 0.62; ln = 1.5 - abs(i - 3) * 0.12
    par = BBOT
    for sgn in (-1, 1):
        prim('cone', 'rib%d%d' % (i, sgn), bm_, par, (sgn * ln * 0.45, 0, z), (1, 1, 1), (0, sgn * R(-112), 0), vertices=8, radius1=0.13, depth=ln)
for i in range(3):
    for sgn in (-1, 1):
        prim('cone', 'ribt%d%d' % (i, sgn), bm_, BTOP, (sgn * 0.55, 0, 0.4 + i * 0.6), (1, 1, 1), (0, sgn * R(-112), 0), vertices=8, radius1=0.12, depth=1.2)
prim('cone', 'b_hornL', bm_, BTOP, (-0.75, 0, 3.6), (1, 1, 1), (0, R(-35), 0), vertices=10, radius1=0.2, depth=2.4)
prim('cone', 'b_hornR', bm_, BTOP, (0.75, 0, 3.6), (1, 1, 1), (0, R(35), 0), vertices=10, radius1=0.2, depth=2.4)
bpy.ops.mesh.primitive_plane_add(size=1.0, rotation=(R(90), 0, 0)); bpl = bpy.context.object; bpl.name = 'bone_face'
bpy.ops.object.transform_apply(rotation=True)
bfm, BFW = face_material('bone_face', '#FAFAF5', BIMGS, 'plane'); bpl.data.materials.append(bfm)
bpl.parent = BTOP; bpl.location = (0, -0.32, 1.9); bpl.scale = (1.5, 1, 1.5)
def bone_face(k):
    for n, v in BFW.items(): v.outputs[0].default_value = 1.0 if n == k else 0.0

# FX pools
def pool(n, name, kind, m, sc_):
    out = []
    for i in range(n):
        if kind == 'sphere':
            o = prim('uv_sphere', '%s%d' % (name, i), m, None, (0, 0, -500), (sc_,) * 3, segments=16, ring_count=8)
        elif kind == 'star':
            me = bpy.data.meshes.new('%s%d' % (name, i)); bmm = bmesh.new(); pts = []
            for k in range(10):
                rr = 1.0 if k % 2 == 0 else 0.45; a = k * math.pi / 5
                pts.append(bmm.verts.new((math.sin(a) * rr, 0, math.cos(a) * rr)))
            f = bmm.faces.new(pts); bmesh.ops.extrude_face_region(bmm, geom=[f])
            for v in bmm.verts:
                if abs(v.co.y) < 1e-6 and v not in pts: pass
            bmm.to_mesh(me); bmm.free(); me.materials.append(m)
            o = new_obj('%s%d' % (name, i), me, None, (0, 0, -500)); o.scale = (sc_,) * 3
        else:
            o = box('%s%d' % (name, i), (1, 1, 1), (0, 0, 0), m); o.location = (0, 0, -500); o.scale = (sc_,) * 3
        out.append(o)
    return out
PUFF = pool(9, 'puff', 'sphere', mat('#FFFFFF', 0.5, 1.3, 0.72), 1)
STARS = pool(7, 'star', 'star', mat('#FFE14D', 0.4, 2.0), 1)
SMOKE = pool(10, 'smoke', 'sphere', mat('#1E1E22', 0.9), 1)
SPARK = pool(18, 'spark', 'sphere', mat('#FFC233', 0.3, 12.0), 1)
DROPS = pool(26, 'drop', 'sphere', mat('#7CC6FF', 0.15, 0.4, 0.85), 1)
ZAP = pool(14, 'zap', 'box', mat('#5AB4FF', 0.3, 10.0), 1)
ICB = prim('uv_sphere', 'ic_fall', mat('#FF9CC8', 0.5), None, (0, 0, -500), (1.1, 1.1, 1.0), segments=20, ring_count=10)
def hide(o): o.location = (0, 0, -500); o.scale = (0.001,) * 3
def hide_local(o): o.scale = (0.0001,) * 3

# ---------------- poses ----------------
P = {
 'idle':   dict(armL=(0, 0, 0), armR=(0, 0, 0), legL=(0, 0, 0), legR=(0, 0, 0), head=(0, 0, 0), body=(0, 0, 0)),
 'hold':   dict(armL=(R(-80), 0, R(8)), armR=(R(-80), 0, R(-8))),
 'fishhold': dict(armL=(R(-62), 0, R(4)), armR=(R(-62), 0, R(-4))),
 'bite':   dict(armL=(R(-97), 0, R(4)), armR=(R(-97), 0, R(-4)), head=(R(-4), 0, 0), body=(R(-3), 0, 0)),
 'choke':  dict(armL=(R(-150), 0, R(38)), armR=(R(-150), 0, R(-38)), head=(R(14), 0, 0), body=(R(4), 0, 0)),
 'icecream': dict(armL=(R(-55), 0, R(8)), armR=(R(-85), 0, R(-22)), head=(R(-3), 0, 0)),
 'bottle': dict(armL=(R(-30), 0, R(6)), armR=(R(-150), 0, R(-22)), head=(R(-24), 0, 0), body=(R(-5), 0, 0)),
 'jug':    dict(armL=(R(-172), 0, R(10)), armR=(R(-172), 0, R(-10)), head=(R(28), 0, 0), body=(R(10), 0, 0)),
 'reach':  dict(armL=(R(-150), 0, R(38)), armR=(R(-90), 0, R(70)), head=(0, 0, R(-20)), body=(0, 0, R(-8))),
 'hero':   dict(armL=(R(-8), R(30), 0), armR=(R(-8), R(-30), 0), head=(R(-6), 0, 0), body=(R(-5), 0, 0), legL=(0, R(8), 0), legR=(0, R(-8), 0)),
 'drink':  dict(armL=(R(-20), 0, 0), armR=(R(-165), 0, R(-18)), head=(R(26), 0, 0), body=(R(8), 0, 0)),
 'jumpup': dict(armL=(R(-165), R(-25), 0), armR=(R(-165), R(25), 0), head=(R(-8), 0, 0), legL=(R(-25), 0, 0), legR=(R(15), 0, 0)),
 'grab':   dict(armL=(R(-95), 0, R(12)), armR=(R(-95), 0, R(-12)), body=(R(-8), 0, 0)),
 'saw':    dict(armL=(R(-85), 0, R(20)), armR=(R(-90), 0, 0), head=(R(-6), 0, 0), body=(R(-10), 0, 0), legL=(R(-20), 0, 0), legR=(R(15), 0, 0)),
 'carry':  dict(armL=(R(-60), 0, 0), armR=(R(-172), 0, R(-10))),
 'cheer':  dict(armL=(R(-165), R(-25), 0), armR=(R(-165), R(25), 0), head=(R(-10), 0, 0), body=(R(-4), 0, 0)),
 'point':  dict(armL=(R(-8), R(30), 0), armR=(R(-90), 0, 0), head=(R(-4), 0, 0)),
 'cough':  dict(armL=(R(-150), 0, R(38)), armR=(R(-120), 0, R(-30)), head=(R(-18), 0, 0), body=(R(-14), 0, 0)),
 'openwide': dict(armL=(R(-40), 0, R(10)), armR=(R(-40), 0, R(-10)), head=(R(18), 0, 0), body=(R(6), 0, 0)),
}
KEYS = ['armL', 'armR', 'legL', 'legR', 'head', 'body']
def pose_vals(name):
    d = dict(P['idle']); d.update(P[name]); return d

# timelines: (time, pose, face, headturn_z)
LILY_TL = [(0, 'fishhold', 'smile', 0), (0.90, 'bite', 'eat', 0), (2.20, 'choke', 'choke', 0), (4.30, 'choke', 'scared', 0),
    (5.15, 'icecream', 'determined', 0), (5.55, 'icecream', 'eat', 0), (6.00, 'choke', 'choke', 0), (8.65, 'bottle', 'eat', 0), (9.85, 'choke', 'choke', 0),
    (12.30, 'reach', 'shock', 0), (13.90, 'choke', 'choke', 0), (21.75, 'idle', 'scared', R(28)),
    (23.20, 'openwide', 'openwide', 0), (25.0, 'choke', 'choke', 0), (29.50, 'cough', 'shock', 0), (31.4, 'openwide', 'openwide', 0), (31.95, 'idle', 'smile', 0),
    (32.05, 'cheer', 'happy', 0), (33.00, 'idle', 'smile', R(25)), (34.55, 'point', 'happy', R(-15))]
MIA_TL = [(0, 'hold', 'smile', 0), (14.68, 'hero', 'determined', 0), (16.15, 'drink', 'eat', 0), (18.25, 'idle', 'shock', 0),
    (20.55, 'jumpup', 'happy', 0), (21.70, 'idle', 'smile', R(-30)), (23.25, 'jumpup', 'determined', 0),
    (25.10, 'idle', 'determined', 0), (25.40, 'grab', 'angry', 0), (26.80, 'saw', 'determined', 0),
    (30.70, 'carry', 'happy', 0), (32.35, 'hero', 'happy', R(-20)), (33.70, 'point', 'smile', R(-20)), (34.55, 'cheer', 'happy', R(-15))]

def eval_tl(tl, t):
    idx = 0
    for i, k in enumerate(tl):
        if k[0] - 0.07 <= t: idx = i
    cur = tl[idx]; prev = tl[idx - 1] if idx > 0 else cur
    x = ease_back((t - (cur[0] - 0.07)) / 0.14) if idx > 0 else 1.0
    a = pose_vals(prev[1]); b = pose_vals(cur[1])
    out = {}
    for k in KEYS:
        out[k] = tuple(a[k][j] + (b[k][j] - a[k][j]) * x for j in range(3))
    hz = prev[3] + (cur[3] - prev[3]) * x
    face = cur[2] if t >= cur[0] - 0.07 else prev[2]
    return out, face, hz

def apply(ch, pv, hz, extra=None):
    e = extra or {}
    for k in ('armL', 'armR', 'legL', 'legR'):
        v = pv[k]; d = e.get(k, (0, 0, 0))
        ch.sh[k].rotation_euler = (v[0] + d[0], v[1] + d[1], v[2] + d[2])
    hv = pv['head']; d = e.get('head', (0, 0, 0)); ch.head.rotation_euler = (hv[0] + d[0], hv[1] + d[1], hz + d[2])
    bv_ = pv['body']; d = e.get('body', (0, 0, 0)); ch.body.rotation_euler = (bv_[0] + d[0], bv_[1] + d[1], bv_[2] + d[2])
    ch.body.location = (0, 0, 2 + e.get('bob', 0))

# ---------------- shots ----------------
# (t0, t1, cam_loc, target, fov, push, slide)
SH = [
 (0.00, 2.23, (0, -10.5, 6.6), (0.4, 0, 4.3), 46, 1.1, None),
 (2.23, 3.27, (0, -7.6, 5.4), (0, 0, 4.4), 40, 0.7, None),
 (3.27, 4.23, (TX, -7, 5.6), (TX, 8, 5.4), 50, 1.4, None),
 (4.23, 6.03, (0.4, -9.5, 6.4), (0, 0, 4.4), 46, 1.2, None),
 (6.03, 7.43, (TX, -6, 6.2), (TX, 8, 5.8), 48, 1.2, None),
 (7.43, 8.62, (-0.8, -7.4, 5.4), (0, 0, 4.4), 40, 0.7, None),
 (8.62, 9.87, (-6.5, -6.5, 5.3), (0, 0, 5.6), 50, 0.9, None),
 (9.87, 11.30, (TX, -7, 6.0), (TX, 8, 5.6), 54, 1.4, None),
 (11.30, 12.20, (0.7, -7.2, 5.2), (0, 0, 4.5), 40, 0.6, None),
 (12.20, 13.90, (2.0, -10.0, 6.4), (1.0, 0, 4.4), 50, 1.0, None),
 (13.90, 15.88, (KX, -10.5, 4.4), (KX, 0, 3.7), 52, 1.3, None),
 (15.88, 18.25, (KX + 0.5, -7.5, 5.8), (KX, 0, 4.6), 44, 0.6, None),
 (18.25, 19.55, (KX, -10, 4.2), (KX, 0, 3.6), 54, 0.8, None),
 (19.55, 21.75, (KX, -9.0, 3.4), (KX, 0, 2.2), 56, 1.0, 'kdown'),
 (21.75, 23.15, (-2.0, -10.5, 6.6), (1.0, 0, 3.9), 52, 0.0, 'slide'),
 (23.15, 25.05, (3.6, -4.2, 5.0), (1.0, -0.4, 4.4), 40, 0.6, None),
 (25.05, 26.77, (TX, -5, 4.6), (TX, 8, 4.6), 48, 1.0, None),
 (26.77, 27.60, (TX + 0.8, -3.5, 4.4), (TX + 0.8, 8, 4.2), 44, 0.6, None),
 (27.60, 28.33, (0.5, -7.2, 5.2), (0, 0, 4.5), 40, 0.5, None),
 (28.33, 30.10, (TX, -4.5, 4.8), (TX, 8, 4.6), 48, 1.0, None),
 (30.10, 30.70, (0.6, -8.0, 5.2), (0, 0, 4.4), 44, 0.5, None),
 (30.70, 31.60, (TX, -3.5, 3.6), (TX, 8, 4.4), 54, 0.0, None),
 (31.60, 32.38, (2.2, -10.5, 5.4), (1.0, -1.6, 3.9), 46, 0.6, None),
 (32.38, 33.70, (1.8, -11.5, 6.6), (1.8, 0, 4.2), 50, 0.9, None),
 (33.70, 34.40, (3.5, -5.2, 5.0), (3.5, 0.3, 4.7), 36, 0.5, None),
 (34.40, 36.40, (1.4, -12.5, 7.2), (1.2, 0, 4.0), 58, 1.4, None),
]

cam_d = bpy.data.cameras.new('cam'); cam_d.sensor_fit = 'VERTICAL'; cam_d.dof.use_dof = False
cam = new_obj('cam', cam_d); sc.camera = cam
cam_d.clip_start = 0.1; cam_d.clip_end = 300

def shot_at(t):
    for i, s in enumerate(SH):
        if s[0] <= t < s[1]: return i, s
    return len(SH) - 1, SH[-1]

def set_cam(t):
    i, (t0, t1, loc, tgt, fov, push, slide) = shot_at(t)
    p = smooth((t - t0) / max(0.01, (t1 - t0) * 0.9))
    loc = Vector(loc); tgt = Vector(tgt)
    if slide == 'slide': loc = loc + Vector((5.0 * smooth((t - t0) / (t1 - t0)), 0, 0))
    if slide == 'kdown' and t > 19.85:
        k = smooth((t - 19.85) / 0.6); tgt = tgt + Vector((0, 0, -1.4 * k)); loc = loc + Vector((0, 3.5 * k, -1.6 * k))
    d = (tgt - loc).normalized(); loc = loc + d * push * p
    cam.location = loc
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam_d.angle = R(fov)
    return i

def puff_fx(t, events):
    act = None
    for (te, c, s) in events:
        if te <= t < te + 0.62: act = (te, c, s)
    for o in PUFF + STARS: hide(o)
    if not act: return
    te, c, s = act; dt = t - te; rnd = random.Random(int(te * 100))
    for i, o in enumerate(PUFF):
        a = i / 9 * 2 * math.pi; off = Vector((math.cos(a) * 0.9, rnd.uniform(-0.4, 0.4), math.sin(a) * 0.9)) * s
        g = min(1, dt / 0.14); shrink = 1 - smooth((dt - 0.25) / 0.3)
        r = (0.55 + 0.35 * rnd.random()) * s * g * shrink
        if dt > 0.55: r = 0
        o.location = Vector(c) + off * (1 + dt * 1.2); o.scale = (max(r, 0.001),) * 3
    for i, o in enumerate(STARS):
        a = i / 7 * 2 * math.pi + 0.3; k = smooth(dt / 0.6)
        o.location = Vector(c) + Vector((math.cos(a), -0.6, math.sin(a))) * s * (0.3 + 2.4 * k)
        o.rotation_euler = (0, dt * 14 + i, 0); sz = 0.32 * s * (1 - smooth((dt - 0.35) / 0.25))
        o.scale = (max(sz, 0.001),) * 3

# event times (word-keyed, from vo/words.json)
EV_PUFFS = [
 (6.62, (TX, 7.2, 8.6), 1.4),          # ice cream hits bone
 (26.80, (TX + 2.6, 6.8, 3.0), 1.0),   # "Not" chainsaw appears
 (32.36, (3.4, 0.2, 2.6), 1.6),        # "Mia" back to full size
 (34.55, (0.6, -2.0, 4.0), 1.5),       # "fish!" payoff
]

MIA_PITCH = [0.0]
def update(scene, depsgraph=None):
    f = scene.frame_current; t = f / FPS
    si = set_cam(t)
    # ---- Lily ----
    pv, face, hz = eval_tl(LILY_TL, t)
    ex = {'bob': 0.06 * math.sin(t * 2 * math.pi * 0.9)}
    if face == 'choke':
        sh = math.sin(t * 2 * math.pi * 5.5) * R(7); ex['head'] = (0, R(3) * math.sin(t * 31), sh)
        ex['armL'] = (R(4) * math.sin(t * 40), 0, 0); ex['armR'] = (R(4) * math.sin(t * 43), 0, 0)
    if 0.9 <= t < 2.2: ex['head'] = (R(8) * math.sin(t * 2 * math.pi * 4), 0, 0)
    if 8.65 <= t < 9.87: ex['head'] = (R(5) * math.sin(t * 2 * math.pi * 5), 0, 0)
    if 29.5 <= t < 31.0: ex['body'] = (R(10) * abs(math.sin(t * 2 * math.pi * 2.2)), 0, 0)
    if t >= 34.55:
        stg = 0.012 * 1
        ex['head'] = (R(10) * ease_back((t - 34.55 - stg) / 0.14), 0, 0)
    apply(LILY, pv, hz, ex); LILY.set_face(face)
    LILY.root.location = (0, 0, 0)
    LILY.root.rotation_euler = (0, 0, R(90) if 23.15 <= t < 25.05 else 0)
    # ---- fish on table / in hands ----
    if t < 2.23:
        k = min(1.0, ease_back((t - 0.83) / 0.14)) if t > 0.83 else 0
        chomp = 0.06 * abs(math.sin(t * 2 * math.pi * 4)) if t > 0.97 else 0
        FISH.parent = LILY.body
        FISH.location = (0.15, -1.3 + 0.33 * k + chomp, 1.62 + 0.48 * k); FISH.scale = (FS,) * 3
        FISH.rotation_euler = (0, R(-4) * k, 0)
    else: FISH.parent = None; hide(FISH)
    if t >= 34.55:
        k = min(1, (t - 34.55) / 0.14); FISH2.location = (0.6, -2.1, 3.62); FISH2.scale = (FS * k + 0.001,) * 3
        FISH2.rotation_euler = (0, 0, R(-10))
    else: hide(FISH2)
    # ice cream / jug
    if 5.0 <= t < 6.03:
        IC.scale = (1, 1, 1); IC.location = (0.38, -1.15, 1.95)
        if t >= 5.62: ICBALL.scale = (0.4, 0.4, 0.33); ICBALL.location = (0.04, 0.05, 0.5)
        else: ICBALL.scale = (0.48, 0.48, 0.45); ICBALL.location = (0, 0, 0.6)
    else: hide_local(IC)
    hide_local(JUG)
    if 8.62 <= t < 9.87:
        bpy.context.view_layer.update(); hmw = LILY.head.matrix_world
        bim = LILY.body.matrix_world.inverted()
        mouth = bim @ (hmw @ Vector((0, -0.66, 0.40)))
        d = Vector((0.32, -0.42, 0.85)).normalized()
        BOT.location = mouth - d * 0.02 + Vector((0, 0, 0.0)); BOT.scale = (1, 1, 1)
        BOT.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        BOT.rotation_euler.x += R(3) * math.sin(t * 18)
    else: hide_local(BOT)
    # ---- Mia ----
    pv, face, hz = eval_tl(MIA_TL, t)
    ex = {'bob': 0.06 * math.sin(t * 2 * math.pi * 1.1)}
    mloc = (KX, 0, 0); msc = 1.0; mrz = 0
    if 18.25 <= t < 20.3:  # electric flail
        ex['armL'] = (R(-150) + R(28) * math.sin(t * 2 * math.pi * 3.1) - pv['armL'][0], 0, 0)
        ex['armR'] = (R(-150) - R(28) * math.sin(t * 2 * math.pi * 3.1) - pv['armR'][0], 0, 0)
        ex['legL'] = (R(32) * math.sin(t * 2 * math.pi * 3.6), 0, 0); ex['legR'] = (-R(32) * math.sin(t * 2 * math.pi * 3.6), 0, 0)
        ex['head'] = (0, R(6) * math.sin(t * 50), 0)
    if t < 19.45: msc = 1.0
    elif t < 21.75:
        k = smooth((t - 19.45) / 0.75); msc = 1.0 - 0.85 * k
        if t < 20.2: msc *= 1 + 0.06 * math.sin((t - 19.45) * 38) * (1 - k)
        if t >= 20.55:  # boing jump, gravity 78 (scaled)
            dt = t - 20.55; v0 = 78 * 0.33 * 0.5; z = max(0, v0 * dt - 0.5 * 78 * 0.33 * dt * dt)
            mloc = (KX, -0.5, z)
        else: mloc = (KX, -0.5 * min(1, (t - 19.45) / 0.75), 0)
    elif t < 25.05:
        msc = 0.15; base = Vector((2.4, -1.4, 3.08)); mrz = R(-60) if t < 23.15 else R(-100)
        if t < 23.15: mloc = tuple(base)
        else:
            base = Vector((2.9, -0.9, 3.08)); mouth = Vector((0.75, -0.05, 4.45))
            if t < 23.75: mloc = tuple(base)
            elif t < 24.45:
                k = smooth((t - 23.75) / 0.7)
                msc = 0.15 - 0.04 * k; Hh = 6.0 * msc
                bpy.context.view_layer.update(); hm = LILY.head.matrix_world
                mouth = hm @ Vector((0, -0.64, 0.40)); inward = (hm @ Vector((0, 0.2, 0.40)) - mouth).normalized()
                inside = mouth + inward * (Hh + 0.05)
                start_head = base + Vector((0, 0, Hh))
                if k < 0.7:
                    q = k / 0.7; hp = start_head.lerp(mouth - inward * 0.25, q); hp.z += 0.55 * math.sin(math.pi * q)
                else:
                    q = (k - 0.7) / 0.3; hp = (mouth - inward * 0.25).lerp(inside, q)
                pitch = R(-90) * smooth(min(1, k / 0.55))
                # feet (root) trail behind head along body axis
                axis = Vector((-math.sin(-pitch), 0, math.cos(pitch)))
                root = hp - axis * Hh
                mloc = tuple(root); mrz = 0
                MIA_PITCH[0] = pitch
                ex['armL'] = (R(-175) - pv['armL'][0], 0, 0); ex['armR'] = (R(-175) - pv['armR'][0], 0, 0)
            else: mloc = (0, 0, -500)
    elif t < 32.36:
        # throat
        if t < 25.6:
            dt = t - 25.05; z = max(0.0, 12 - 0.5 * 78 * dt * dt); mloc = (TX + 2.6, 6.6, z)
        elif t < 30.7: mloc = (TX + 2.6, 6.6, 0)
        else:
            k = (t - 30.7) / 0.9; mloc = (TX + 0.6, 6.0 - 4.0 * k, 0); mrz = 0
            ph = t * 2 * math.pi * 2.6
            ex['legL'] = (R(45) * math.sin(ph), 0, 0); ex['legR'] = (-R(45) * math.sin(ph), 0, 0)
            ex['armL'] = (-R(40) * math.sin(ph), 0, 0); ex['bob'] = 0.16 * abs(math.sin(ph))
            ex['body'] = (R(-9), 0, 0)
        if 26.8 <= t < 30.1:
            ex['body'] = (R(-10), 0, R(4) * math.sin(t * 60)); ex['armR'] = (R(5) * math.sin(t * 70), 0, 0)
        if 25.4 <= t < 26.8:  # tugging
            ex['body'] = (R(8) * math.sin(t * 2 * math.pi * 3), 0, 0)
        mrz = mrz if t >= 30.7 else R(-35)
    else:
        mloc = (3.6, 0.4, 0); mrz = R(-15)
    MIA.root.location = mloc; MIA.root.scale = (msc,) * 3; MIA.root.rotation_euler = (0, MIA_PITCH[0], mrz); MIA_PITCH[0] = 0
    apply(MIA, pv, hz, ex); MIA.set_face(face)
    # Mia props
    if 13.9 <= t < 14.68: CHK.scale = (1, 1, 1); CHK.parent = MIA.body; CHK.location = (0, -1.6, 0.6)
    elif 13.9 <= t < 18.25:
        CHK.parent = None; CHK.location = (KX - 4.2, 2.2, 3.7); CHK.scale = (1, 1, 1)
    else: hide(CHK)
    if 16.0 <= t < 18.25: MUG.scale = (1, 1, 1); MUG.rotation_euler = (R(-20 - 25 * smooth((t - 16.2) / 1.2)), 0, 0)
    else: hide_local(MUG)
    if 26.8 <= t < 30.7:
        k = min(1, (t - 26.8) / 0.14); SAW.scale = (k + 0.001,) * 3
    else: hide_local(SAW)
    # ---- bone ----
    bface = 'smirk'
    if t >= 25.1: bface = 'angry'
    if t >= 28.4: bface = 'shock'
    bone_face(bface)
    BTOP.location = (0, 0, 4.8); BTOP.rotation_euler = (0, 0, 0)
    if t < 30.7:
        BONE.location = (TX, 8.0, 0); BONE.scale = (1, 1, 1)
        wob = 0
        if 3.27 <= t < 4.23: wob = R(4) * math.sin(t * 2 * math.pi * 3)
        if 6.62 <= t < 7.43: wob = R(10) * math.exp(-(t - 6.62) * 4) * math.sin((t - 6.62) * 40)
        if 25.4 <= t < 26.8: wob = R(6) * math.sin(t * 2 * math.pi * 3)
        if 26.9 <= t < 29.3: wob = R(2) * math.sin(t * 80)
        BONE.rotation_euler = (0, wob, 0)
        if t >= 29.3:
            k = ease_back((t - 29.3) / 0.25, 1.2)
            BTOP.rotation_euler = (0, R(-28) * k, 0); BTOP.location = (-0.6 * k, 0, 4.8 + 0.3 * k)
    elif t < 31.6:
        # carried on Mia's shoulder (horizontal)
        BONE.location = Vector(MIA.root.location) + Vector((1.2, 0, 4.9)); BONE.rotation_euler = (0, R(90), 0); BONE.scale = (0.75,) * 3
    elif t < 32.38:
        if t < 31.72: hide(BONE)
        else:
            dt = t - 31.72; T = 0.38
            p0 = Vector((0.0, -0.9, 4.25)); p1 = Vector((1.9, -2.3, 3.12))
            if dt < T:
                k = dt / T; p = p0.lerp(p1, k); p.z += 1.3 * math.sin(math.pi * k)
                BONE.rotation_euler = (R(20), R(90) + dt * 16, R(25))
            else:
                tb = dt - T; p = p1.copy(); p.z += max(0, 2.2 * tb - 0.5 * 30 * tb * tb)
                BONE.rotation_euler = (0, R(90), R(25))
            BONE.location = p; BONE.scale = (0.14,) * 3
    else: hide(BONE)
    # ---- FX ----
    puff_fx(t, EV_PUFFS)
    rnd = random.Random(f)
    # ice cream ball fall in throat
    if 6.03 <= t < 6.62:
        dt = t - 6.03; ICB.location = (TX + 0.2, 7.4, 14 - 0.5 * 40 * dt * dt + 0.0); ICB.scale = (1.1, 1.1, 1.0)
    else: hide(ICB)
    for i, o in enumerate(DROPS):
        if 9.87 <= t < 11.3:
            ph = (i * 0.37 + (t - 9.87) * 1.8) % 1.0
            o.location = (TX + rnd.uniform(-3.5, 3.5) * 0 + ((i * 1.37) % 7 - 3.5), 6.0 + (i % 5) * 0.5, 15 - ph * 15)
            o.scale = (0.3, 0.3, 0.55)
        else: hide(o)
    for i, o in enumerate(ZAP):
        if 18.25 <= t < 20.25:
            ms = MIA.root.scale[0]
            c = Vector((KX, -0.4, 0)) + Vector((rnd.uniform(-2.2, 2.2), rnd.uniform(-1.0, 0.2), rnd.uniform(0.2, 6.2))) * ms
            o.location = c; o.rotation_euler = (rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
            o.scale = (0.08 * ms, 0.08 * ms, rnd.uniform(0.6, 1.6) * ms)
        else: hide(o)
    for i, o in enumerate(SPARK):
        if 27.05 <= t < 30.1:
            c = Vector((TX + 0.4, 7.4, 4.8))
            k = rnd.random(); a = rnd.uniform(0, 6.3)
            o.location = c + Vector((math.cos(a) * 3 * k, -rnd.uniform(0, 1.5), math.sin(a) * 2.5 * k + 0.5))
            o.scale = (0.09,) * 3
        else: hide(o)
    for i, o in enumerate(SMOKE):
        if 28.6 <= t < 30.1:
            ph = ((t - 28.6) * 0.9 + i / 10) % 1.0
            o.location = (TX + 0.3 + math.sin(i * 2.1) * 1.4, 7.2 - ph * 3, 5.0 + ph * 5 + math.cos(i) * 0.8)
            o.scale = (0.5 + 1.4 * ph,) * 3
        elif 30.1 <= t < 30.7:
            dt = t - 30.1; a = i / 10 * 6.28
            o.location = (0.25 * math.cos(a), -0.8 - dt * 1.6 - (i % 3) * 0.15, 4.4 + 0.35 * math.sin(a) + dt * 1.5)
            o.scale = (min(1, dt / 0.14) * (0.22 + 0.06 * (i % 3)) + 0.001,) * 3
        else: hide(o)

bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(update)

# ---------------- run ----------------
os.makedirs(OUT, exist_ok=True)
if MODE == 'stills':
    for i, s in enumerate(SH):
        f = int(((s[0] + s[1]) / 2) * FPS)
        if RNG and not (RNG[0] <= i <= RNG[1]): continue
        sc.frame_set(f); update(sc)
        sc.render.filepath = os.path.join(OUT, 'shot_%02d.png' % i)
        bpy.ops.render.render(write_still=True)
        print('STILL', i, f, flush=True)
elif MODE == 'frames':
    a, b = RNG if RNG else (0, NF - 1)
    for f in range(a, b + 1):
        p = os.path.join(OUT, 'f_%04d.png' % f)
        if os.path.exists(p): continue
        sc.frame_set(f); update(sc)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print('FRAME', f, flush=True)
elif MODE == 'blend':
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene.blend'))
