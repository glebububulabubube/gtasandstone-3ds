#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пробник DFF: дерево чанков + угадывание размера фрейма + структура геометрии."""
import struct, sys

RW_ID = {
    0x0001: ('Struct', 1), 0x0002: ('String', 0), 0x0003: ('Extension', 0),
    0x0006: ('Texture', 0), 0x0007: ('Material', 0), 0x0008: ('MatList', 0),
    0x000E: ('FrameList', 0), 0x000F: ('Geometry', 0), 0x0010: ('Clump', 0),
    0x0011: ('Atomic', 0), 0x0012: ('GeometryList', 0),
    0x0116: ('Skin', 0), 0x01E5: ('HAnim', 0),
}

def walk(d, p, end, depth, out):
    while p + 12 <= end:
        typ, size, ver = struct.unpack_from('<III', d, p)
        name, is_struct = RW_ID.get(typ, ('X%04X' % typ, 0))
        out.append(f'{"  "*depth}{p:>7} {name:<12} size={size:<8} ver=0x{ver:08X}')
        body = p + 12
        if typ == 0x0001 or is_struct:
            pass
        elif typ in (0x0010, 0x000F, 0x000E, 0x0007):
            walk(d, body, body + size, depth + 1, out)
        if size == 0:
            return p + 12
        p = body + size
    return p

def probe(path):
    d = open(path, 'rb').read()
    print('FILE', path, 'len', len(d))
    typ, size, ver = struct.unpack_from('<III', d, 0)
    print('root type=0x%04X size=%d ver=0x%08X' % (typ, size, ver))

    out = []
    walk(d, 0, len(d), 0, out)
    # только первую часть (до первого нулевого/мусорного)
    for line in out[:60]:
        print(line)

    # Scan для plugin-чанков по всему файлу
    for sig, nm in [(b'\x16\x01\x00\x00', 'Skin'), (b'\xe5\x01\x00\x00', 'HAnim'), (b'\x0e\x00\x00\x00', 'FrameList')]:
        pos = 0; n = 0
        while True:
            i = d.find(sig, pos)
            if i < 0: break
            n += 1; pos = i + 1
        print('  scan', nm, ':', n, 'вхождений')

    # FrameList: найдём первую запись 0x0E с правдоподобным размером
    for i in range(len(d) - 4):
        t, s, v = struct.unpack_from('<III', d, i)
        if t == 0x000E and 0 < s < 50000 and v == 0x1803FFFF:
            fb = i + 12
            nf = struct.unpack_from('<I', d, fb)[0]
            if 1 <= nf <= 200:
                print('  FrameList на', i, 'numFrames =', nf, 'размер тела =', s)
                for fs in (48, 56, 80):
                    need = 4 + fs * nf
                    if need > s + 2:
                        print('    size', fs, 'не влезает'); continue
                    vals = []
                    ok = True
                    for k in range(min(nf, 4)):
                        base = fb + 4 + k * fs
                        # перевод: 9-я..11-я float матрицы = позиция? в RW матрица 3x4: pos в 3-х последних float
                        t9 = struct.unpack_from('<9f', d, base)
                        if any(abs(x) > 500 for x in t9):
                            ok = False; break
                        px = t9[3] * 0 + struct.unpack_from('<3f', d, base + 36)[0] if fs >= 48 else 0
                        vals.append((round(struct.unpack_from('<3f', d, base + 36)[0], 2) if fs >= 48 else None))
                    print('    frameSize', fs, 'ok=', ok, 'pos первых:', vals[:4])
                break

probe(sys.argv[1])