#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборщик карты gtasandstone (.gsmap v2): GTA SA → бинарные сектора (геометрия без текстур).

Читает IPL/IDE (data/maps), вытаскивает DFF из gta3.img, конвертирует
каждую модель в компактный меш (позиции+нормали+UV+индексы+цвета материалов),
раскладывает по секторам 200x200 вокруг центра. Текстуры НЕ встраиваются
(этап 1: проверка стриминга и рендера).

Формат .gsmap v2:
  'GSMAP' u32 ver(=2)
  f32 secSize     (200.0)
  f32 originX, originZ
  u32 numSectorsX, numSectorsZ
  u32 numModels
  models[..]:
    u32 numVerts, u32 numTris, u32 numMats
    verts:  pos 3f, norm 3f, uv 2f       (32 байта)
    tris:   3x u32                        (12 байт)
    mats:   color u32 x numMats
  для каждого сектора:
    u32 count
    instances: modelIdx u16, pos 3f, quat(x,y,z,w) 4f
"""
import struct, glob, os, sys, math
from collections import defaultdict

GTA3 = r'C:\Users\Пользователь\Desktop\models\gta3.img'
MAPS = r'C:\Users\Пользователь\Desktop\files gta sa\data\maps'
SEC = 200.0

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsmod_conv import read_part

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
        except ValueError:
            continue
        insts.append(dict(id=iid, x=x, y=y, z=z, qx=qx, qy=qy, qz=qz, qw=qw))
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
            out[iid] = parts[1].lower()
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

def model_mesh(data):
    """DFF -> (verts[(pos,norm,uv)], tris, colors)."""
    c = read_part(data)
    if not c['geoms']:
        return None
    g = c['geoms'][0]
    verts = []
    for i in range(len(g['verts'])):
        p = g['verts'][i]
        n = g['normals'][i] if g['normals'] else (0, 1, 0)
        uv = g['uvs'][i] if g.get('uvs') and i < len(g['uvs']) else (0, 0)
        verts.append((p[0], p[1], p[2], n[0], n[1], n[2], uv[0], uv[1]))
    tris = []
    for t in g['tris']:
        if len(t) == 3:
            tris.append(tuple(t[:3]))
    colors = []
    for m in g['mats']:
        if isinstance(m, (tuple, list)) and len(m) >= 3:
            r_, g_, b_ = m[0], m[1], m[2]
            colors.append((r_ << 16) | (g_ << 8) | b_)
        else:
            colors.append(0xFFFFFF)
    return verts, tris, colors

def main():
    cx, cy, radius = 2500.0, -1680.0, 400.0
    if len(sys.argv) >= 4:
        cx = float(sys.argv[1]); cy = float(sys.argv[2]); radius = float(sys.argv[3])

    print('== IPL/IDE ==')
    all_inst = []
    for p in glob.glob(os.path.join(MAPS, '**', '*.ipl'), recursive=True):
        all_inst += parse_ipl(p)
    ide_map = {}
    for p in glob.glob(os.path.join(MAPS, '**', '*.ide'), recursive=True):
        ide_map.update(parse_ide(p))
    print('inst:', len(all_inst), 'ide:', len(ide_map))

    idx = img_index(GTA3)
    fimg = open(GTA3, 'rb')

    win = [i for i in all_inst if abs(i['x'] - cx) <= radius and abs(i['y'] - cy) <= radius]
    print('в окне:', len(win))

    by_model = defaultdict(list)
    for inst in win:
        name = ide_map.get(inst['id'])
        if name:
            by_model[name].append(inst)

    # сетка
    xs = [i['x'] for i in win]; zs = [i['y'] for i in win]
    origin_x = math.floor(min(xs) / SEC) * SEC
    origin_z = math.floor(min(zs) / SEC) * SEC
    nx = int((max(xs) - origin_x) / SEC) + 1
    nz = int((max(zs) - origin_z) / SEC) + 1
    print('сетка: %dx%d, origin (%.0f, %.0f)' % (nx, nz, origin_x, origin_z))

    # модели -> меши
    models = []
    mesh_by_name = {}
    model_idx = {}
    inst_out = []
    skipped = 0
    for name in sorted(by_model.keys()):
        if name + '.dff' not in idx:
            skipped += 1
            continue
        data = fimg.read(0)  # noop
        fimg.seek(idx[name + '.dff'][0])
        data = fimg.read(idx[name + '.dff'][1])
        try:
            mesh = model_mesh(data)
        except Exception:
            skipped += 1
            continue
        if not mesh:
            skipped += 1
            continue
        model_idx[name] = len(models)
        models.append(name)
        mesh_by_name[name] = mesh
        inst_out.append((name, by_model[name]))
    fimg.close()
    print('моделей в карте:', len(models), 'пропущено:', skipped)

    # --- запись ---
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work', 'grove.gsmap')
    buf = bytearray()
    buf += b'GSMAP'
    buf += struct.pack('<IfffIII', 2, SEC, origin_x, origin_z, nx, nz, len(models))

    for name in models:
        verts, tris, colors = mesh_by_name[name]
        buf += struct.pack('<III', len(verts), len(tris), len(colors))
        for v in verts:
            buf += struct.pack('<8f', *v)
        for t in tris:
            buf += struct.pack('<III', *t)
        for col in colors:
            buf += struct.pack('<I', col)

    sector_insts = defaultdict(list)
    for name, insts in inst_out:
        mi = model_idx[name]
        for inst in insts:
            sx = int((inst['x'] - origin_x) / SEC)
            sz = int((inst['y'] - origin_z) / SEC)
            if 0 <= sx < nx and 0 <= sz < nz:
                sector_insts[(sx, sz)].append((mi, inst))
    for sz in range(nz):
        for sx in range(nx):
            lst = sector_insts.get((sx, sz), [])
            buf += struct.pack('<I', len(lst))
            for mi, inst in lst:
                buf += struct.pack('<H', mi)
                buf += struct.pack('<3f', inst['x'], inst['y'], inst['z'])
                buf += struct.pack('<4f', inst['qx'], inst['qy'], inst['qz'], inst['qw'])

    open(out_path, 'wb').write(bytes(buf))
    print('WROTE', out_path, len(buf), 'bytes')

if __name__ == '__main__':
    main()