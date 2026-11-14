#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Конвертер частей тела CJ (GTA SA DFF, RenderWare 3.4) -> .gsmod.

Каждый DFF — Clump(0x10): Struct, FrameList(0x0E) [Struct{numFrames,frames[56]},
и внутри расширения — имена костей в чанках 0x0253F2FE (= 'fef25302')],
GeometryList(0x1A): Geometry(0x0F) [Struct{flags,numTris,numVerts,numMorphs,
uvs, tris(8б), morphs}, MatList(0x08), Extension{Skin(0x0116)}].

Выход .gsmod:
  'GSMOD' u32, ver u32=1, numBones u32, numParts u32, totalVerts u32
  ... таблица костей: name[32] (0-filled), parent i16, flags u16
  ... каждая часть: numVerts u32, numTris u32, numMats u16,
      verts[numVerts]: pos 3f, norm 3f, bone0 u16, w0 f32, bone1 u16, w1 f32
      tris[numTris]: 3 x u32
      colors: u32 rgb на материал (вектор части)
"""
import struct, sys, os, json

RW_STRUCT    = 0x0001
RW_STRING    = 0x0002
RW_EXT       = 0x0003
RW_FRAMELIST = 0x000E
RW_GEOMETRY  = 0x000F
RW_CLUMP     = 0x0010
RW_ATOMIC    = 0x0014
RW_GEOMLIST  = 0x001A
RW_MATLIST   = 0x0008
RW_MATERIAL  = 0x0007
RW_TEXTURE   = 0x0006
RW_SKIN      = 0x0116
RW_NAMECHUNK = 0x0253F2FE
RW_HANIM     = 0x01E5

class R:
    def __init__(self, d, p=0):
        self.d = d; self.p = p
    def u8(self):  v = self.d[self.p]; self.p += 1; return v
    def u16(self): v, = struct.unpack_from('<H', self.d, self.p); self.p += 2; return v
    def i16(self): v, = struct.unpack_from('<h', self.d, self.p); self.p += 2; return v
    def u32(self): v, = struct.unpack_from('<I', self.d, self.p); self.p += 4; return v
    def i32(self): v, = struct.unpack_from('<i', self.d, self.p); self.p += 4; return v
    def f32(self): v, = struct.unpack_from('<f', self.d, self.p); self.p += 4; return v
    def f3(self):  return (self.f32(), self.f32(), self.f32())
    def f2(self):  return (self.f32(), self.f32())
    def f4(self):  return (self.f32(), self.f32(), self.f32(), self.f32())
    def align4(self):
        if self.p & 3: self.p += 4 - (self.p & 3)
    def data(self, n):
        out = self.d[self.p:self.p+n]; self.p += n; return out
    def sub(self):
        return R(self.d, self.p)
    def at(self, p):
        return R(self.d, p)
    def chunk(self):
        typ = self.u32(); size = self.u32(); ver = self.u32()
        body = R(self.d, self.p)
        self.p += size
        return typ, size, ver, body

def parse_framelist(r):
    """Тело FrameList: Struct{numFrames, frames[56]} + чанки имён в теле."""
    frames = []
    curs = r.at(r.p)
    t, s, v, b = curs.chunk()
    if t == RW_STRUCT:
        nf = b.u32()
        for _ in range(nf):
            m = [b.f3() for _ in range(4)]
            parent = b.i32()
            flags = b.u32()
            frames.append([parent, m, flags])
    return frames

def extract_names(d):
    """Все чанки 0x0253F2FE (имя кости) в порядке появления в файле."""
    names = []
    i = 0
    while i + 12 <= len(d):
        if d[i:i+4] == b'\xfe\xf2\x53\x02':
            size = struct.unpack_from('<I', d, i+4)[0]
            if 0 < size <= 40 and i + 12 + size <= len(d):
                nm = d[i+12:i+12+size].split(b'\0')[0]
                try:
                    s = nm.decode('ascii')
                    if s:
                        names.append(s)
                except Exception:
                    pass
                i += 12 + size
                continue
        i += 2
    # группируем в прогоны (имена идут подряд), берём самый длинный
    runs = []
    cur = []
    for n in names:
        if cur and n == cur[-1]:
            continue
        if cur and n and any(n.startswith(p) for p in cur[-3:]):
            pass
        cur.append(n)
    return names

def parse_skin(r, numVerts):
    hdr = r.data(4)
    numBones, numUsed, numWeights, _ = hdr
    used = list(r.data(numUsed))
    indices = list(r.data(numVerts*4))
    weights = struct.unpack_from('<%df' % (numVerts*4), r.d, r.p); r.p += numVerts*16
    invmats = []
    for _ in range(numBones):
        invmats.append(struct.unpack_from('<16f', r.d, r.p)); r.p += 64
    return {'numBones': numBones, 'used': used, 'indices': indices,
            'weights': weights, 'invmats': invmats}

def parse_material_chunk(r, ver):
    # Тело Material-чанка: Struct{ flags u32, color u32, unused u32, textured u32,
    #   [surfaceProps 3f если ver>=0x30400] }, затем [Texture-чанк], [Extension]
    # Имя текстуры в GTA SA карточных DFF: Texture(0x06) содержит Struct{filterAdd}
    # + String(0x02) name + String(0x02) mask (в CJ текстур нет).
    t, s, v, b = r.chunk()
    if t != RW_STRUCT:
        return (255, 255, 255, None)
    flags = b.u32()
    color = b.u32()
    b.u32()                    # unused
    textured = b.u32()
    if ver >= 0x30400:
        b.f3()                 # surfaceProperties
    texname = None
    if textured and r.p + 12 <= len(r.d):
        tt2, ts2, tv2, tb2 = r.chunk()
        if tt2 == RW_TEXTURE:
            # Struct { u32 filterAddressing }
            if tb2.p + 12 <= tb2.p + ts2:
                ts3, ss3, vs3, bs3 = tb2.chunk()
                if ss3 >= 4:
                    bs3.u32()
                # String-чанки: name, mask
                while bs3.p + 12 <= tb2.p + ts2:
                    tt4, ss4, vs4, bs4 = bs3.chunk()
                    if tt4 == RW_STRING:
                        nm = bs4.data(ss4).split(b'\0')[0]
                        try:
                            nm = nm.decode('ascii')
                        except Exception:
                            nm = ''
                        if nm and not texname:
                            texname = nm
                    if ss4 == 0:
                        break
    r_ = color & 0xFF
    g_ = (color >> 8) & 0xFF
    bl = (color >> 16) & 0xFF
    return (r_, g_, bl, texname)

def parse_material_list(r):
    # MatList(0x08) тело: Struct(0x01){numMats u32, idxs[i32]}, затем чанки Material
    t, s, v, b = r.chunk()
    if t != RW_STRUCT:
        return []
    numMats = b.u32()
    idxs = [b.i32() for _ in range(numMats)]
    objs = {}
    for i in range(numMats):
        tt, ts, tv, tb = r.chunk()
        if tt == RW_MATERIAL:
            objs[i] = parse_material_chunk(tb, tv)
    out = []
    for i in range(numMats):
        j = idxs[i] if idxs[i] >= 0 else i
        out.append(objs.get(j, (255, 255, 255, None)))
    return out

def read_one_geom(body):
    r = body.sub()
    t, s, v, b = r.chunk()
    flags = b.u32()
    numTris = b.u32()
    numVerts = b.u32()
    numMorphs = b.u32()

    numUV = (flags >> 16) & 0xFF
    if numUV == 0:
        numUV = 1 if (flags & 0x04) else (2 if (flags & 0x80) else 0)
    # классические RenderWare-биты (GTA SA):
    #   TEXTURED=0x04, PRELIT=0x08, NORMALS=0x10, TEXTURED2=0x80
    prelit = bool(flags & 0x08)
    hasNorm = bool(flags & 0x10)

    if prelit:
        for _ in range(numVerts): b.u32()
    uvs = []
    for _ in range(numUV):
        uvset = [b.f2() for _ in range(numVerts)]
        if _ == 0:
            uvs = uvset
    tris = []
    for _ in range(numTris):
        w0 = b.u32(); w1 = b.u32()
        tris.append([(w0 >> 16) & 0xFFFF, w0 & 0xFFFF, (w1 >> 16) & 0xFFFF])
    # НЕ выравниваем: в GS files морф-сфера идёт сразу после трисов (без padding).

    pos = []; norm = []
    for _ in range(numMorphs):
        b.f4()
        hasV = b.i32(); hasN = b.i32()
        if hasV: pos = [b.f3() for _ in range(numVerts)]
        if hasN: norm = [b.f3() for _ in range(numVerts)]

    mats = []; skin = None
    while r.p + 12 <= len(r.d):
        t2, s2, v2, b2 = r.chunk()
        if t2 == RW_MATLIST:
            mats = parse_material_list(b2)
        elif t2 == RW_SKIN:
            skin = parse_skin(b2, numVerts)
        elif t2 == RW_EXT:
            e = b2.sub()
            while e.p + 12 <= len(e.d):
                t3, s3, v3, b3 = e.chunk()
                if t3 == RW_SKIN:
                    skin = parse_skin(b3, numVerts)
                if s3 == 0: break
        if s2 == 0: break
    return {'verts': pos, 'normals': norm, 'tris': tris, 'mats': mats, 'uvs': uvs}, skin

def read_part(d):
    r = R(d)
    res = {'frames': None, 'names': [], 'geoms': [], 'skins': []}
    typ, size, ver, body = r.chunk()
    if typ == RW_CLUMP:
        c = body.sub()
        while c.p + 12 <= len(c.d):
            t2, s2, v2, b2 = c.chunk()
            if t2 == RW_FRAMELIST:
                res['frames'] = parse_framelist(b2)
            elif t2 == RW_GEOMLIST:
                gb = b2.sub()
                tg, sg, vg, bg = gb.chunk()
                nGeo = bg.u32()
                for _ in range(nGeo):
                    tg2, sg2, vg2, bg2 = gb.chunk()
                    if tg2 == RW_GEOMETRY:
                        g, sk = read_one_geom(bg2)
                        res['geoms'].append(g)
                        res['skins'].append(sk)
            elif t2 == RW_EXT:
                pass
            if s2 == 0: break
    return res

def mt3x4(m):
    """Матрица 4x4 (16 float) -> 3x4 (12 float: row3 = pos)."""
    # в RW матрица в памяти: row-major 4x4
    return m[0:3] + m[4:7] + m[8:11] + m[12:15]

def collect_vertex_weights(geom_idx, skin, numVerts):
    """Возвращает list[numVerts] of [(boneIdx, w)] (топ-2 веса).

    Индексы костей в rpSkin локальные (0..numBones-1) и соответствуют
    фреймам 1..numBones (фрейм 0 — root-узел клaмпа, не кость).
    В .gsmod храним глобальный индекс фрейма = локальный + 1.
    """
    out = []
    used = skin['used']
    for vi in range(numVerts):
        pairs = []
        for k in range(4):
            b_idx = skin['indices'][vi*4+k]
            w = skin['weights'][vi*4+k]
            if w > 0.001:
                pairs.append((b_idx + 1, w))
        pairs.sort(key=lambda x: -x[1])
        out.append(pairs[:2])
    return out

def main():
    workdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work')
    parts = ['head.dff', 'tshirt.dff', 'hands.dff', 'jeans.dff', 'sneaker.dff']
    # часть -> имя текстуры (в DFF CJ текстур нет; привязка по имени части)
    # руки в GTA SA текстурируются 'torso8bit' (общий тон кожи)
    PART_TEXTURES = ['face', 'torso', 'torso8bit', 'legs', 'foot']
    # загружаем извлечённые текстуры: name -> (w, h, rgba)
    txd_images = {}
    txd_index = os.path.join(workdir, 'txd_out', 'textures.json')
    if os.path.exists(txd_index):
        for t in json.load(open(txd_index, encoding='utf-8')):
            p = os.path.join(workdir, 'txd_out', t['file'])
            if os.path.exists(p):
                txd_images[t['name']] = (t['w'], t['h'], open(p, 'rb').read())
    print('txd images:', sorted(txd_images))
    frames = None
    all_names = []
    parts_out = []
    for fn in parts:
        d = open(os.path.join(workdir, fn), 'rb').read()
        c = read_part(d)
        if frames is None and c['frames']:
            frames = c['frames']
        if not all_names:
            all_names = extract_names(d)
        for g, sk in zip(c['geoms'], c['skins']):
            print('part', fn, 'verts', len(g['verts']), 'tris', len(g['tris']),
                  'mats', g['mats'][:2], 'skin', sk['numBones'] if sk else None)
            parts_out.append((g, sk))

    # текстура для каждой части (по порядку частей)
    part_textures = [PART_TEXTURES[i] for i in range(len(parts_out))]

    nb = len(frames)
    print('\nbones:', nb, 'names found:', len(all_names))
    # отберём первые nb уникальных имен (в порядке появления)
    seen = set()
    names_ordered = []
    for n in all_names:
        if n not in seen:
            seen.add(n)
            names_ordered.append(n)
    print('unique names:', len(names_ordered))
    for i, n in enumerate(names_ordered[:nb]):
        print('  bone', i, '=', n)

    # индексы костей в скине локальные (0..numBones-1) -> соответствуют frames[1..numBones]
    # т.е. скелет: frame0 = root, кость i (скин) = frame i+1
    bone_names = [None]*nb
    for i, n in enumerate(names_ordered[:nb]):
        bone_names[i] = n
    for i in range(nb):
        if bone_names[i] is None:
            bone_names[i] = 'Bone%02d' % i

    # --- сбор вершин ---
    total_verts = 0
    for gi, (g, sk) in enumerate(parts_out):
        total_verts += len(g['verts'])
    print('total verts:', total_verts)

    # --- запись .gsmod (v4: + локальные матрицы костей, скин-индекс = фрейм+1) ---
    out_path = os.path.join(workdir, 'cj.gsmod')
    buf = bytearray()
    buf += b'GSMOD'
    buf += struct.pack('<IIII', 4, nb, len(parts_out), total_verts)

    # кости: имя 32 б + parent i16 + flags u32 + local 3x4 (12 float) + invmat 3x4 (12 float)
    invmats = parts_out[-1][1]['invmats']
    for i in range(nb):
        name_bytes = bone_names[i].encode('ascii', 'replace')[:31]
        nm = name_bytes + b'\0' * (32 - len(name_bytes))
        parent = frames[i][0]
        flags = frames[i][2]
        buf += nm
        buf += struct.pack('<hI', parent, flags)
        # локальная матрица фрейма: 4 строки по 3 float (r0, r1, r2, t)
        flat = [v for row in frames[i][1] for v in row]
        buf += struct.pack('<12f', *flat)
        if i == 0:
            buf += struct.pack('<12f', 1,0,0, 0,1,0, 0,0,1, 0,0,0)
        else:
            m = invmats[i-1]
            buf += struct.pack('<12f', *mt3x4(m))

    tex_names = []   # уникальные имена текстур (по имени части)
    def texid(name):
        if not name:
            return 0xFFFF
        if name not in tex_names:
            tex_names.append(name)
        return tex_names.index(name)

    # части
    for gi, (g, sk) in enumerate(parts_out):
        numV = len(g['verts']); numT = len(g['tris']); numM = len(g['mats'])
        buf += struct.pack('<IHH', numV, numT, numM)
        weights = collect_vertex_weights(gi, sk, numV)
        for vi in range(numV):
            p = g['verts'][vi]
            nrm = g['normals'][vi] if g['normals'] else (0, 1, 0)
            buf += struct.pack('<3f3f', *p, *nrm)
            if g.get('uvs'):
                u, v = g['uvs'][vi]
            else:
                u = v = 0.0
            buf += struct.pack('<2f', u, v)
            wt = weights[vi]
            if len(wt) >= 2:
                b0, w0 = wt[0][0], wt[0][1]
                b1, w1 = wt[1][0], wt[1][1]
            elif len(wt) == 1:
                b0, w0 = wt[0][0], wt[0][1]
                b1, w1 = b0, 0.0
            else:
                b0, w0, b1, w1 = 0, 1.0, 0, 0.0
            buf += struct.pack('<HfHf', b0, w0, b1, w1)
        for tri in g['tris']:
            buf += struct.pack('<III', *tri)
        # материалы: цвет u32 + texid u16 (все материалы части наследуют текстуру части)
        part_tex = part_textures[gi] if PART_TEXTURES else None
        for col in g['mats'] or [(255,255,255,None)] * max(numM,1):
            r_, g_, b_, _ = col
            tid = texid(part_tex)
            buf += struct.pack('<IH', (r_ << 16) | (g_ << 8) | b_, tid)
        # добить недостающие материалы белым с той же текстурой
        for _ in range(max(0, numM - len(g['mats']))):
            buf += struct.pack('<IH', 0xFFFFFF, texid(part_tex))

    # таблица текстур: u32 count, затем для каждой: name[32], w u16, h u16, data w*h*4
    buf += struct.pack('<I', len(tex_names))
    for name in tex_names:
        nb2 = name.encode('ascii', 'replace')[:31]
        buf += nb2 + b'\0' * (32 - len(nb2))
        img = txd_images.get(name)
        if img is None:
            w = h = 1
            data = b'\xFF\x00\xFF\xFF'   # magenta заглушка
        else:
            w, h, data = img
        buf += struct.pack('<HH', w, h)
        buf += data

    open(out_path, 'wb').write(bytes(buf))
    print('\nWROTE', out_path, 'bytes', len(buf))
    print('textures in model:', tex_names)

    # --- проверка: печать скелета с именами ---
    print('\nBones:')
    for i in range(nb):
        print('  %2d %-18s parent=%2d' % (i, bone_names[i], frames[i][0]))

if __name__ == '__main__':
    main()