#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проходится по DFF и печатает дерево RW-чанков с позициями."""
import struct, sys

RW_VERS = {
    0x00010000: '1.0', 0x00020000: '2.0', 0x00030000: '3.0',
    0x1003FFFF: '3.1', 0x1003FF00: '3.1', 0x1803FFFF: '3.4',
    0x9C020000: '3.8', 0x9C020100: '3.8',
}

def chunk_name(t):
    return {
        0x0001: 'Struct', 0x0002: 'String', 0x0003: 'Extension',
        0x000F: 'FrameList', 0x0010: 'Geometry', 0x0011: 'GeometryList',
        0x0012: 'MaterialList', 0x0013: 'Material', 0x0014: 'Texture',
        0x0015: 'Clump', 0x0016: 'Atomic', 0x0017: 'PlaneSection',
        0x0018: 'World', 0x0019: 'Spline', 0x001A: 'MatrixList',
        0x001B: 'FrameList(rtAnim)', 0x001C: 'GeometryAnim',
        0x001D: 'Animation', 0x001E: 'Skin',
        0x0022: 'HAnim',
    }.get(t, 'Chunk%04X' % t)

def walk(data, depth=0, base=0):
    p = 0
    while p + 12 <= len(data):
        typ, size, ver = struct.unpack_from('<III', data, p)
        print('  '*depth + f'{base+p:>7} {chunk_name(typ):<22} size={size:>7} ver=0x{ver:08X} ({RW_VERS.get(ver,"?")})')
        body = p + 12
        if typ == 0x0001:  # Struct
            walk_struct(data, body, size, depth)
        elif typ == 0x0015:
            walk(data, base + body, depth+1)
        p = body + size

def walk_struct(data, body, size, depth):
    # специфично: печатаем первые слова для диагностики
    n = min(size, 32)
    words = struct.unpack_from('<%dI' % (n//4), data, body)
    print('  '*(depth+1) + 'struct words: ' + ' '.join(hex(w) for w in words) + (' ...' if size > n else ''))

for path in sys.argv[1:]:
    print('='*70)
    print('FILE', path)
    walk(open(path, 'rb').read())