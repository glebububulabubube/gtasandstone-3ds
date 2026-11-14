#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Конвертер GTA SA DFF (RenderWare 3.4) -> собственный бинарный формат gtasandstone.

Извлекает скелет (frame list), геометрию (позиции/нормали/UV/индексы/материалы),
веса скина (rpSkin, формат GTA SA) и превращает всё в один компактный .gsmod:
  header: magic 'GSMOD', 4x u32: version, numBones, numMeshes, numMaterials
  для каждого bone: 3x4 матрица (48 байт) + parent i16
  для каждого vertex (во всех мешах в сумме): pos xyz (12), normal xyz (12),
      bone0 i16 + weight0 f32 (8), bone1 i16 + weight1 f32 (8)  [RLE весов]
  для каждого меша: matId u16, start u32, count u32 (индексы u32)
  материалы: цвет 0xRRGGBB (без текстур)
"""
import struct, sys, os, math

RW_STRUCT = 0x0001
RW_STRING = 0x0002
RW_EXTENSION = 0x0003
RW_FRAMELIST = 0x000E
RW_GEOMETRY = 0x000F
RW_CLUMP = 0x0010
RW_ATOMIC = 0x0011
RW_GEOMLIST = 0x0012
RW_MATLIST = 0x0013
RW_MATERIAL = 0x0014
RW_TEXTURE = 0x0015
RW_SKIN = 0x01E5  # rpSkin v3.4
RW_HSKIN = 0x0116  # HsSkin? в SA саме rpSkin

VER34 = 0x1803FFFF

class Reader:
    def __init__(self, d):
        self.d = d
        self.p = 0

    def u8(self):  v = self.d[self.p]; self.p += 1; return v
    def u16(self): v, = struct.unpack_from('<H', self.d, self.p); self.p += 2; return v
    def i16(self): v, = struct.unpack_from('<h', self.d, self.p); self.p += 2; return v
    def u32(self): v, = struct.unpack_from('<I', self.d, self.p); self.p += 4; return v
    def i32(self): v, = struct.unpack_from('<i', self.d, self.p); self.p += 4; return v
    def f32(self): v, = struct.unpack_from('<f', self.d, self.p); self.p += 4; return v
    def f32s(self, n): return struct.unpack_from('<%df' % n, self.d, self.p)[0:]
    def skip(self, n): self.p += n
    def tell(self): return self.p

def chunk(r):
    """Возвращает (type, size, body_reader, body_abs)."""
    typ = r.u32(); size = r.u32(); ver = r.u32()
    body = type(r)(r.d)
    body.p = r.p
    r.p += size
    return typ, size, body

# ---------- FrameList ----------

def parse_framelist(r):
    """Возвращает list[(parent, m3x4)] — по 56 байт на фрейм."""
    num = r.u32()
    frames = []
    for _ in range(num):
        m = [r.f32s(3) for _ in range(4)]  # 4 строки по 3 float = 3x4 (RW хранит так)
        parent = r.i32()
        flags = r.u32()
        # m = 4 строки по 3: строки 0..2 = матрица поворота, строка 3 = позиция
        frames.append((parent, m))
    return frames

# ---------- Geometry ----------

def parse_geometry(r):
    """Возвращает dict с геометрией (позиции, нормали, uv, индексы, материалы)."""
    flags = r.u32()
    numTris = r.u32()
    numVerts = r.u32()
    numMats = r.u32()
    # Только first frame (анимации геометрии пропускаем)
    hasTris        = flags & 0x0004
    hasVerts       = flags & 0x0008
    hasNormals     = flags & 0x0010
    hasUVs         = flags & 0x0040   # в SA это 0x40 (CUVAL = textures)
    hasPreLit      = flags & 0x0200
    isSkin         = flags & 0x0800

    verts = []; normals = []; uvs = []; tcol = []; 
    if hasVerts:
        verts = [r.f32s(3) for _ in range(numVerts)]
    if hasUVs:
        uvs = [r.f32s(2) for _ in range(numVerts)]
    if hasNormals:
        normals = [r.f32s(3) for _ in range(numVerts)]
    if hasPreLit:
        tcol = [r.u32() for _ in range(numVerts)]

    # Индексы: (a,b,c) u16 — лист треугольников
    tris = []
    if hasTris:
        tris = [(r.u16(), r.u16(), r.u16()) for _ in range(numTris)]
        # выравнивание до 4 после списка индексов
        if r.p & 3: r.skip(4 - (r.p & 3))

    # Материалы
    mats = []
    for _ in range(numMats):
        mats.append(parse_material(r))

    return {
        'verts': verts, 'normals': normals, 'uvs': uvs, 'tris': tris,
        'mats': mats, 'prelit': tcol, 'numMats': numMats,
        'flags': flags,
    }

def parse_material(r):
    flags = r.u32()
    color = r.u32()
    unused = r.u32()
    tex_id = r.u32()
    # extension может содержать текстурную ссылку; парсим Texture чанки (0x15 не лезет сюда)
    return {'color': color, 'flags': flags, 'tex': tex_id, 'name': ''}

# ---------- Skin (rpSkin, GTA SA) ----------

def parse_skin(r, num_verts):
    """Читает rpSkin: структура GTA SA .dff"""
    boneCount = r.u8()
    specialCount = r.u8()
    """NumVertexInfluences: 1..8 (у CJ = 4)"""
    numVertexInfluences = r.u8()
    numBoneInfluences = r.u8()
    # веса: сумма по всем вершинам = numVertexInfluences*numVerts
    weights = []
    for _ in range(numVertexInfluences * num_verts):
        weights.append(r.u8() / 255.0)
    # индексы костей (та же размерность)
    bone_ids = [r.u8() for _ in range(numVertexInfluences * num_verts)]
    # размножение весов с номерами костей (количество костей влияющих на вершину) — RLE
    vert_indices = []  # номер вершины [0..n-1]
    buffer = []
    last = -1
    while r.p < len(r.d):
        b = r.u8()
        cnt = r.u8()
        if cnt == 0:
            break
        if b == 0xFF:
            # вершина с повторным добавлением последних N весов
            last += cnt
            buffer.append(last)
        else:
            # первое вхождение вершины b
            vert_indices.append(b)
            last = b
        # нет: сделаем по стандартной раскладке
    return None

    bones = []
    for _ in range(boneCount):
        # матрица 3x4
        m = [r.f32s(3) for _ in range(4)]
        bones.append(m)
    return {'boneCount': boneCount, 'bones': bones}

# ---------- Топ-уровень Clump ----------

def parse_clump(d):
    r = Reader(d)
    typ, size, body = chunk(r)
    assert typ == RW_CLUMP, 'ожидался Clump 0x10, got 0x%X' % typ

    # Struct: numAtomics — пропускаем (нам не нужен)
    t, s, b = chunk(body)
    assert t == RW_STRUCT

    # FrameList
    t, s, b = chunk(body)
    if t == RW_FRAMELIST:
        frames = parse_framelist(b)
    else:
        raise ValueError('нет FrameList в Clump')

    # GeometryList
    t, s, b = chunk(body)
    if t == RW_GEOMLIST:
        pass
    else:
        raise ValueError('нет GeometryList')

    nGeo = b.u32()
    geoms = []
    for _ in range(nGeo):
        t, s, gb = chunk(b)
        if t == RW_GEOMETRY:
            geoms.append(parse_geometry(gb))
        else:
            raise ValueError('ожидался Geometry')

    # Skin находится в Extension-чанке каждой Geometry (для SA).
    # Но у нас часть тел: у них Clump начинается с FrameList (скин не печатался выше).
    # Отдельно пройдём все Extension'ы на предмет RW_SKIN.
    return {'frames': frames, 'geoms': geoms}

def extract_skin(d):
    """Ищет RW_SKIN-чанк на верхнем уровне Extension'ов и читает его."""
    r = Reader(d)
    results = {}
    while r.p + 12 <= len(r.d):
        typ, size, body = chunk(r)
        if typ == RW_EXTENSION and size > 0:
            e = body
            while e.p + 12 <= e.d_size(e):
                pass
    return results

if __name__ == '__main__':
    path = sys.argv[1]
    d = open(path, 'rb').read()
    cl = parse_clump(d)
    print('frames:', len(cl['frames']))
    for i, (p, m) in enumerate(cl['frames']):
        print(' bone', i, 'parent', p, 'pos', [round(x,2) for x in m[3]])
    for gi, g in enumerate(cl['geoms']):
        print('geom', gi, 'verts', len(g['verts']), 'tris', len(g['tris']), 'mats', len(g['mats']),
              'colors', [hex(m['color']) for m in g['mats']])