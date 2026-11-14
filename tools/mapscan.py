#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сканер карты GTA SA: парсит IPL/IDE и оценивает объём данных района.

1. Читает все *.ipl из data/maps (рекурсивно), парсит inst-секции:
   id, name, interior, x, y, z, qx, qy, qz, qw, lodId
2. Читает все *.ide: objs/tobj -> id -> (dfn, txd)
3. По боксу (cx,cy,radius) собирает нужные DFF и TXD, сверяет с gta3.img.
Печатает статистику: сколько моделей, текстур, суммарный объём.
"""
import struct, glob, os, sys, math

GTA3 = r'C:\Users\Пользователь\Desktop\models\gta3.img'

def parse_ipl(path):
    insts = []
    try:
        s = open(path, encoding='utf-8', errors='replace').read()
    except Exception:
        return insts
    in_inst = False
    for ln in s.splitlines():
        t = ln.split('#')[0].strip()
        if not t:
            continue
        low = t.lower()
        if low in ('inst', 'cars', 'pickups', 'cull', 'paths', 'enex', 'grge',
                   'jump', 'tcyc', 'zone', 'occ', 'mult', 'end'):
            in_inst = (low == 'inst')
            continue
        if not in_inst:
            continue
        parts = [x.strip() for x in t.split(',')]
        if len(parts) < 11:
            continue
        try:
            iid = int(parts[0])
            x = float(parts[3]); y = float(parts[4]); z = float(parts[5])
            qx = float(parts[6]); qy = float(parts[7])
            qz = float(parts[8]); qw = float(parts[9])
            lod = int(parts[10]) if parts[10] else -1
        except ValueError:
            continue
        insts.append(dict(id=iid, name=parts[1], x=x, y=y, z=z,
                          qx=qx, qy=qy, qz=qz, qw=qw, lod=lod))
    return insts

def parse_ide(path):
    out = {}
    try:
        s = open(path, encoding='utf-8', errors='replace').read()
    except Exception:
        return out
    in_objs = False
    for ln in s.splitlines():
        t = ln.split('#')[0].strip()
        if not t:
            continue
        low = t.lower()
        if low in ('objs', 'tobj', 'cars', 'peds', 'weap', 'hier', '2dfx', 'end'):
            in_objs = (low in ('objs', 'tobj'))
            continue
        if not in_objs:
            continue
        parts = [x.strip() for x in t.split(',')]
        if len(parts) >= 3:
            try:
                iid = int(parts[0])
            except ValueError:
                continue
            out[iid] = (parts[1], parts[2])
    return out

def img_index(path):
    f = open(path, 'rb')
    hdr = f.read(8)
    count = struct.unpack_from('<I', hdr, 4)[0]
    f.seek(8)
    names = {}
    for i in range(count):
        rec = f.read(32)
        off, size, name = struct.unpack_from('<II24s', rec, 0)
        nm = name.split(b'\0')[0].decode('ascii', 'replace')
        if nm:
            names[nm.lower()] = (off * 2048, size * 2048)
    f.close()
    return names

def main():
    cx, cy, radius = 2500.0, -1680.0, 300.0
    if len(sys.argv) >= 4:
        cx = float(sys.argv[1]); cy = float(sys.argv[2]); radius = float(sys.argv[3])

    print('== Парсинг IPL ==')
    all_inst = []
    ipl_files = glob.glob(r'C:\Users\Пользователь\Desktop\files gta sa\data\maps\**\*.ipl',
                          recursive=True)
    print('IPL файлов:', len(ipl_files))
    for p in ipl_files:
        all_inst += parse_ipl(p)
    print('всего inst:', len(all_inst))

    print('\n== Парсинг IDE ==')
    ide_map = {}
    for p in glob.glob(r'C:\Users\Пользователь\Desktop\files gta sa\data\maps\**\*.ide',
                       recursive=True):
        ide_map.update(parse_ide(p))
    print('IDE записей:', len(ide_map))

    print('\n== Окно: центр (%.0f, %.0f), радиус %d ==' % (cx, cy, radius))
    win = [i for i in all_inst
           if abs(i['x'] - cx) <= radius and abs(i['y'] - cy) <= radius]
    print('объектов в окне:', len(win))

    # уникальные id
    ids = sorted(set(i['id'] for i in win))
    dffs = set(); txds = set()
    for iid in ids:
        v = ide_map.get(iid)
        if v:
            dffs.add(v[0].lower()); txds.add(v[1].lower())
    print('уникальных id:', len(ids), 'dff:', len(dffs), 'txd:', len(txds))

    idx = img_index(GTA3)
    print('\ngta3.img записей:', len(idx))

    print('\n-- DFF в gta3.img --')
    total_dff = 0
    miss = []
    for d in sorted(dffs):
        key = d + '.dff'
        e = idx.get(key)
        if e:
            total_dff += e[1]
            print('  %-32s %8d' % (d, e[1]))
        else:
            miss.append(d)
    print('DFF суммарно: %.1f KB' % (total_dff / 1024.0))
    if miss:
        print('НЕ найдены DFF:', miss)

    print('\n-- TXD в gta3.img --')
    total_txd = 0
    miss_t = []
    for t in sorted(txds):
        key = t + '.txd'
        e = idx.get(key)
        if e:
            total_txd += e[1]
            print('  %-32s %8d' % (t, e[1]))
        else:
            miss_t.append(t)
    print('TXD суммарно: %.1f KB' % (total_txd / 1024.0))
    if miss_t:
        print('НЕ найдены TXD:', miss_t)

if __name__ == '__main__':
    main()