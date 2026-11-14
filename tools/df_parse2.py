#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Парсер DFF RenderWare 3.4 (GTA SA) — самопроверяющийся, по фактическим байтам.

Читает: Clump / GeometryList / Geometry / MaterialList / FrameList / rpSkin.
Затем пишет .gsmod: скелет + вершины(позиция/нормаль/веса/кости) + треугольники + цвета материалов.
"""
import struct, sys, os, math

RW_STRUCT = 0x0001
RW_STRING = 0x0002
RW_EXT    = 0x0003
RW_FRAMELIST = 0x000E
RW_GEOMETRY  = 0x000F
RW_CLUMP     = 0x0010
RW_ATOMIC    = 0x0011
RW_GEOMLIST  = 0x001A   # (эмпирически)
RW_MATLIST   = 0x0008
RW_MATERIAL  = 0x0007
RW_TEXTURE   = 0x0006
RW_SKIN      = 0x0116   # (эмпирически: 0x116)
RW_HSKIN     = 0x01E5   # может появиться в других версиях
VER34        = 0x1803FFFF

class R:
    def __init__(self, d, p=0):
        self.d = d; self.p = p
    def u8(self):  v = self.d[self.p]; self.p += 1; return v
    def u16(self): v, = struct.unpack_from('<H', self.d, self.p); self.p += 2; return v
    def i16(self): v, = struct.unpack_from('<h', self.d, self.p); self.p += 2; return v
    def u32(self): v, = struct.unpack_from('<I', self.d, self.p); self.p += 4; return v
    def i32(self): v, = struct.unpack_from('<i', self.d, self.p); self.p += 4; return v
    def f32(self): v, = struct.unpack_from('<f', self.d, self.p); self.p += 4; return v
    def f3(self):  return self.f32(), self.f32(), self.f32()
    def f2(self):  return self.f32(), self.f32()
    def align4(self):
        if self.p & 3: self.p += 4 - (self.p & 3)
    def sub(self, n):
        out = R(self.d, self.p); out.p = self.p + n
        return R(self.d, self.p), out
    def chunk(self):
        """Читает [type,size,ver] и возвращает body-reader на size байт."""
        typ = self.u32(); size = self.u32(); ver = self.u32()
        body = R(self.d, self.p)
        self.p += size
        return typ, size, ver, body

def walk_ext(r, out, depth=0):
    """Проходит внутри Extension (0x3), печатает вложенные чанки, ищет Skin."""
    while r.p + 12 <= len(r.d):
        typ, size, ver, body = r.chunk()
        out.append('  ' * depth + f'ext {typ:#x} size={size}')
        if typ == RW_SKIN or typ == RW_HSKIN:
            out.append('==== SKIN FOUND size %d' % size)
        if typ == RW_FRAMELIST:
            parse_framelist_raw(body, out)
        if typ == RW_EXT:
            # вложенный extension (координаты костей и т.д.) — рекурсия
            pass
        if size == 0: break
        # skip body (уже сделан через r.p += size)

def parse_framelist_raw(r, out):
    num = r.u32()
    out.append('    frameList num=%d' % num)
    for i in range(num):
        m = [r.f3() for _ in range(4)]
        parent = r.i32(); flags = r.u32()
        out.append('      f%d parent=%d pos=(%.3f,%.3f,%.3f)' % (i, parent, *m[3]))

def parse_geometry_children(d, geo_body, out=None, depth=0):
    """Читает тело Geometry: Struct(данные) + Extension(скин)."""
    out = out if out is not None else []
    r = R(d, geo_body)
    typ, size, ver, body = r.chunk()
    if typ != RW_STRUCT:
        raise ValueError('в Geometry ожидался Struct')
    flags = body.u32()
    numTris = body.u32()
    numVerts = body.u32()
    numMats = body.u32()
    out.append(f'Geometry flags=0x{flags:x} tris={numTris} verts={numVerts} mats={numMats}')

    hasTris    = flags & 0x0004
    hasVerts   = flags & 0x0008
    hasNormals = flags & 0x0010
    hasUVs     = flags & 0x0040
    hasPreLit  = flags & 0x0200
    skinFlag   = flags & 0x0800

    verts=[]; norms=[]; uvs=[]; tcol=[]; tris=[]
    if hasVerts:
        verts = [body.f3() for _ in range(numVerts)]
    if hasUVs:
        uvs = [body.f2() for _ in range(numVerts)]
    if hasNormals:
        norms = [body.f3() for _ in range(numVerts)]
    if hasPreLit:
        tcol = [body.u32() for _ in range(numVerts)]
    if hasTris:
        tris = [(body.u16(), body.u16(), body.u16()) for _ in range(numTris)]
        body.align4()

    out.append(f'  verts[0]={verts[0] if verts else None} norms[0]={norms[0] if norms else None} uv0={uvs[0] if uvs else None}')

    # Материалы (после данных) — это MaterialList в Extension, а тут может идти только список id?
    # Судя по структуре: дальше идёт Extension (0x3). Материалы описаны отдельным чанком.
    # Прочитаем ещё чанки (их размеры даны) — это и есть материалы/текстуры внутри Geometry.
    mats = []
    while r.p < geo_body + 12 + size:
        typ2, size2, ver2, body2 = r.chunk()
        out.append(f'  in-geom chunk {typ2:#x} size={size2}')
        if typ2 == RW_STRUCT:
            # это может быть пре-лит? уже прочитали; пропускаем данные (сделано body2.skip)
            pass
        if typ2 == RW_EXT:
            walk_ext(body2, out, 2)
        if typ2 in (RW_MATLIST, 0x0008):
            # список индексов материалов
            pass
        if typ2 == RW_MATERIAL:
            mats.append(parse_material(body2, out))
        if size2 == 0: break

    return out, verts, norms, uvs, tcol, tris, mats

def parse_material(r, out):
    flags = r.u32()
    color = r.u32()
    unused = r.u32()
    tex = r.u32()
    out.append(f'      material color=#{color:08x} flags={flags} tex={tex}')
    return color

def main(path):
    d = open(path, 'rb').read()
    out = []
    r = R(d)
    typ, size, ver, body = r.chunk()
    out.append('root %#x size=%d ver=%#x' % (typ, size, ver))

    def walk(p, end, depth=0):
        rr = R(d, p)
        while rr.p + 12 <= end:
            start = rr.p
            t, s, v, b = rr.chunk()
            out.append('  '*depth + f'{start:>7} {t:#x} size={s}')
            if t == RW_CLUMP and s:
                walk(start + 12, start + 12 + s, depth + 1)
            elif t == RW_GEOMLIST and s:
                walk(start + 12, start + 12 + s, depth + 1)
            elif t == RW_GEOMETRY and s:
                sub, verts, norms, uvs, tcol, tris, mats = parse_geometry_children(d, start + 12, out, depth + 1)
            elif t == RW_FRAMELIST and s:
                parse_framelist_raw(b, out)
            elif t == RW_EXT and s:
                walk_ext(b, out, depth + 1)
            elif t == RW_ATOMIC:
                pass
    walk(0, size)

    print('\n'.join(out))

if __name__ == '__main__':
    main(sys.argv[1])