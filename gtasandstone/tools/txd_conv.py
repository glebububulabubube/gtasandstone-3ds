#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Парсер GTA SA TXD (RenderWare 3.4, native D3D8 текстуры) -> RGBA + JSON-опись.

Формат (из librw d3d8.cpp readNativeTexture):
  TexDictionary(0x16)
    Struct(0x01) { u32 version=0x00020001, u32 numTextures }
    Texture(0x06) x N
      Struct(0x01) {
        u32 platform (D3D8=8)
        u32 filterAddressing
        char name[32], mask[32]
        u32 format
        i32 hasAlpha
        u16 width, u16 height
        u8 depth, u8 numLevels, u8 type, u8 compression
        [palette: PAL4 -> 4*32, PAL8 -> 4*256]
        for each level: u32 size + data
      }

Выводит: work/txd_out/<name>.rgba (сырые RGBA) + txd_textures.json
"""
import struct, sys, os, json

RW_TEXDICT = 0x0016
RW_TEXTURE_NATIVE = 0x0015   # ID_TEXTURENATIVE (нативные текстуры внутри TXD)
RW_STRUCT  = 0x0001

RAS_PAL4 = 0x4000
RAS_PAL8 = 0x2000
RAS_MIPMAP = 0x8000
RAS_AUTOMIPMAP = 0x1000

# битовые глубины (d3d8)
D3DFMT_R5G6B5  = 0x00000017
D3DFMT_A8R8G8B8 = 0x00000015
D3DFMT_A1R5G5B5 = 0x00000016
D3DFMT_A4R4G4B4 = 0x00000018
D3DFMT_A8       = 0x00000019
D3DFMT_DXT1     = 0x31545844
D3DFMT_DXT2     = 0x32545844
D3DFMT_DXT3     = 0x33545844
D3DFMT_DXT4     = 0x34545844
D3DFMT_DXT5     = 0x35545844
D3DFMT_L8       = 0x00000032

def decode_rgb565(pix):
    r = (pix >> 11) & 0x1F; g = (pix >> 5) & 0x3F; b = pix & 0x1F
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255)

def decode_argb1555(pix):
    a = (pix >> 15) & 1; r = (pix >> 10) & 0x1F; g = (pix >> 5) & 0x1F; b = pix & 0x1F
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255 if a else 0)

def decode_argb8888(pix):
    return (pix & 0xFF, (pix >> 8) & 0xFF, (pix >> 16) & 0xFF, (pix >> 24) & 0xFF)

def decode_argb4444(pix):
    a = (pix >> 12) & 0xF; r = (pix >> 8) & 0xF; g = (pix >> 4) & 0xF; b = pix & 0xF
    return (r << 4 | r, g << 4 | g, b << 4 | b, a << 4 | a)

# ---------- DXT ----------

def _expand565(pix):
    r = ((pix >> 11) & 0x1F) << 3; r |= r >> 5
    g = ((pix >> 5) & 0x3F) << 2; g |= g >> 6
    b = (pix & 0x1F) << 3; b |= b >> 5
    return r, g, b

def _lerp(c0, c1, t):
    return (c0[0] + (c1[0] - c0[0]) * t,
            c0[1] + (c1[1] - c0[1]) * t,
            c0[2] + (c1[2] - c0[2]) * t)

def decode_dxt1_block(data, off, w, h, x0, y0, out, w_out):
    c0 = struct.unpack_from('<H', data, off)[0]
    c1 = struct.unpack_from('<H', data, off + 2)[0]
    col0 = _expand565(c0); col1 = _expand565(c1)
    palette = [col0, col1]
    if c0 > c1:
        palette += [_lerp(col0, col1, 1/3), _lerp(col0, col1, 2/3)]
    else:
        palette += [_lerp(col0, col1, 1/2), (0, 0, 0)]
    bits = struct.unpack_from('<I', data, off + 4)[0]
    for by in range(min(4, h - y0)):
        for bx in range(min(4, w - x0)):
            idx = (bits >> (2 * (by * 4 + bx))) & 3
            r, g, b = palette[idx]
            out[((y0 + by) * w_out + x0 + bx) * 4:(y0 + by) * w_out * 4 + (x0 + bx + 1) * 4] = bytes((r, g, b, 255))

def decode_dxt3_block(data, off, w, h, x0, y0, out, w_out):
    alphas = struct.unpack_from('<8H', data, off)
    c0 = struct.unpack_from('<H', data, off + 8)[0]
    c1 = struct.unpack_from('<H', data, off + 10)[0]
    col0 = _expand565(c0); col1 = _expand565(c1)
    palette = [col0, col1, _lerp(col0, col1, 1/3), _lerp(col0, col1, 2/3)]
    bits = struct.unpack_from('<I', data, off + 12)[0]
    for by in range(min(4, h - y0)):
        for bx in range(min(4, w - x0)):
            idx = (bits >> (2 * (by * 4 + bx))) & 3
            alpha = ((alphas[by * 4 + bx] >> (4 * bx)) & 0xF) * 17
            r, g, b = palette[idx]
            out[((y0 + by) * w_out + x0 + bx) * 4:(y0 + by) * w_out * 4 + (x0 + bx + 1) * 4] = bytes((r, g, b, alpha))

def decode_dxt5_block(data, off, w, h, x0, y0, out, w_out):
    a0 = data[off]; a1 = data[off + 1]
    abits = struct.unpack_from('<6I', data, off + 2)[0] if False else 0
    abits = int.from_bytes(data[off + 2:off + 8], 'little')
    pal = [a0, a1]
    if a0 > a1:
        pal += [int((6*a0 + 1*a1) / 7), int((5*a0 + 2*a1) / 7), int((4*a0 + 3*a1) / 7),
                int((3*a0 + 4*a1) / 7), int((2*a0 + 5*a1) / 7), int((1*a0 + 6*a1) / 7)]
    else:
        pal += [int((4*a0 + 1*a1) / 5), int((3*a0 + 2*a1) / 5), int((2*a0 + 3*a1) / 5),
                int((1*a0 + 4*a1) / 5), 0, 255]
    c0 = struct.unpack_from('<H', data, off + 8)[0]
    c1 = struct.unpack_from('<H', data, off + 10)[0]
    col0 = _expand565(c0); col1 = _expand565(c1)
    cpal = [col0, col1, _lerp(col0, col1, 1/3), _lerp(col0, col1, 2/3)]
    cbits = struct.unpack_from('<I', data, off + 12)[0]
    for by in range(min(4, h - y0)):
        for bx in range(min(4, w - x0)):
            ci = (cbits >> (2 * (by * 4 + bx))) & 3
            ai = (abits >> (3 * (by * 4 + bx))) & 7
            r, g, b = cpal[ci]
            out[((y0 + by) * w_out + x0 + bx) * 4:(y0 + by) * w_out * 4 + (x0 + bx + 1) * 4] = bytes((r, g, b, pal[ai]))

def decode_dxt(data, fmt, w, h, out):
    bpp = 8 if fmt in (D3DFMT_DXT1, (D3DFMT_DXT1 if False else 448581921)) else 16
    # DXT1 = 315458644 (0x31545844); две случайные константы выше неверны — потчуем явно
    if fmt == 0x31545844:
        bpp = 8
    elif fmt in (0x33545844, 0x35545844, 0x34545844):
        bpp = 16
    else:
        bpp = 16
    bw = (w + 3) // 4; bh = (h + 3) // 4
    for by in range(bh):
        for bx in range(bw):
            off = (by * bw + bx) * bpp
            x0, y0 = bx * 4, by * 4
            try:
                if fmt == 0x31545844:
                    decode_dxt1_block(data, off, w, h, x0, y0, out, w)
                elif fmt == 0x33545844:
                    decode_dxt3_block(data, off, w, h, x0, y0, out, w)
                elif fmt in (0x35545844, 0x34545844):
                    decode_dxt5_block(data, off, w, h, x0, y0, out, w)
            except Exception:
                pass

def decode_uncompressed(data, fmt, w, h, out):
    # data — без размера, ровно w*h*2 или w*h*4
    n = w * h
    for i in range(n):
        if fmt == D3DFMT_R5G6B5:
            c = decode_rgb565(struct.unpack_from('<H', data, i * 2)[0])
        elif fmt == D3DFMT_A1R5G5B5:
            c = decode_argb1555(struct.unpack_from('<H', data, i * 2)[0])
        elif fmt == D3DFMT_A4R4G4B4:
            c = decode_argb4444(struct.unpack_from('<H', data, i * 2)[0])
        elif fmt == D3DFMT_A8R8G8B8:
            c = decode_argb8888(struct.unpack_from('<I', data, i * 4)[0])
        else:
            c = (255, 0, 255, 255)
        out[i * 4:i * 4 + 4] = bytes(c)

def parse_txd(path):
    d = open(path, 'rb').read()
    p = 0
    typ, size, ver = struct.unpack_from('<III', d, p); p += 12
    assert typ == RW_TEXDICT
    t2, s2, v2 = struct.unpack_from('<III', d, p); p += 12
    # Struct: u16 numTextures, u16 deviceId
    count, device_id = struct.unpack_from('<HH', d, p); p += s2
    print(f'{os.path.basename(path)}: txd ver=0x{RW_TEXDICT:02X} textures={count} device={device_id}')
    result = []
    for i in range(count):
        t3, s3, v3 = struct.unpack_from('<III', d, p)
        if t3 != RW_TEXTURE_NATIVE:
            p += 12 + s3; continue
        body_start = p + 12
        # внутри TextureNative: Struct
        t4, s4, v4 = struct.unpack_from('<III', d, body_start)
        b = body_start + 12
        platform, = struct.unpack_from('<I', d, b); b += 4
        filterAdd, = struct.unpack_from('<I', d, b); b += 4
        name = d[b:b+32].split(b'\0')[0].decode('ascii', 'replace'); b += 32
        mask = d[b:b+32].split(b'\0')[0].decode('ascii', 'replace'); b += 32
        fmt, hasAlpha = struct.unpack_from('<Ii', d, b); b += 8
        width, height = struct.unpack_from('<HH', d, b); b += 4
        depth, numLevels, type_, comp = d[b:b+4]; b += 4
        print(f'  [{i}] {name!r} {width}x{height} fmt=0x{fmt:08X} alpha={hasAlpha} levels={numLevels} comp={comp}')
        entries = {'name': name, 'width': width, 'height': height, 'format': fmt,
                   'hasAlpha': hasAlpha, 'levels': []}
        # палитра (нативные паллетные форматы D3D8: PAL4 -> 4*32 байта, PAL8 -> 4*256)
        pallen_entries = 0
        if fmt & RAS_PAL4:
            pallen_entries = 32
        elif fmt & RAS_PAL8:
            pallen_entries = 256
        pal = None
        if pallen_entries:
            pal = list(d[b:b + 4 * pallen_entries]); b += 4 * pallen_entries
        for lvl in range(numLevels):
            size_lvl = None
            if not (fmt & (RAS_PAL4 | RAS_PAL8)):
                size_lvl, = struct.unpack_from('<I', d, b); b += 4
            lw, lh = max(1, width >> lvl), max(1, height >> lvl)
            data = d[b:b + size_lvl]; b += size_lvl
            out = bytearray(lw * lh * 4)
            if pallen_entries:
                # PAL4 -> 0.5 Б/пиксель, PAL8 -> 1 Б/пиксель (индекс + палитра уже прочитана)
                if pallen_entries == 32:
                    for y in range(lh):
                        for x in range(lw):
                            idx = (data[(y * lw + x) // 2] >> (4 * (x % 2))) & 0xF
                            c = pal[idx * 4:idx * 4 + 4]
                            out[(y * lw + x) * 4:(y * lw + x) * 4 + 4] = bytes((c[0], c[1], c[2], c[3]))
                else:
                    for y in range(lh):
                        for x in range(lw):
                            idx = data[y * lw + x]
                            c = pal[idx * 4:idx * 4 + 4]
                            out[(y * lw + x) * 4:(y * lw + x) * 4 + 4] = bytes((c[0], c[1], c[2], c[3]))
            else:
                # Формат определяется по размеру уровня (надёжнее, чем биты fmt):
                #   w*h*4  -> RGBA8888
                #   w*h*2  -> RGB565 / ARGB1555 / RGBA4444
                #   w*h/2  -> DXT1
                #   w*h    -> DXT3/DXT5
                px = lw * lh
                if size_lvl >= px * 4:
                    decode_uncompressed(data, D3DFMT_A8R8G8B8, lw, lh, out)
                elif size_lvl >= px * 2:
                    # двухбайтовые: попробуем RGB565 (наиболее частый у карт SA)
                    decode_uncompressed(data, D3DFMT_R5G6B5, lw, lh, out)
                elif size_lvl >= px:
                    # 1 Б/п: DXT3 или DXT5 — пробуем DXT5 (alpha)
                    decode_dxt(data, D3DFMT_DXT5, lw, lh, out)
                else:
                    decode_dxt(data, D3DFMT_DXT1, lw, lh, out)
            entries['levels'].append({'w': lw, 'h': lh, 'data': bytes(out)})
        result.append(entries)
        p = body_start + s3
    return result

def main():
    workdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work')
    outdir = os.path.join(workdir, 'txd_out')
    os.makedirs(outdir, exist_ok=True)
    txds = ['player_face.txd', 'player_feet.txd', 'player_legs.txd', 'player_torso.txd', 'hands.txd']
    all_tex = []
    for fn in txds:
        texs = parse_txd(os.path.join(workdir, fn))
        for t in texs:
            all_tex.append(t)
            base = t['name'].replace(' ', '_').replace('/', '_')
            lvl = t['levels'][0]
            with open(os.path.join(outdir, base + '.rgba'), 'wb') as f:
                f.write(lvl['data'])
            print(f'    -> {base}.rgba {lvl["w"]}x{lvl["h"]}')
    with open(os.path.join(outdir, 'textures.json'), 'w', encoding='utf-8') as f:
        json.dump([{'name': t['name'], 'w': t['levels'][0]['w'], 'h': t['levels'][0]['h'],
                    'file': t['name'].replace(' ', '_').replace('/', '_') + '.rgba'} for t in all_tex],
                  f, ensure_ascii=False, indent=1)
    print('total textures:', len(all_tex))

if __name__ == '__main__':
    main()