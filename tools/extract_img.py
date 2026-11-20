#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Извлекает файлы из GTA SA .img (формат v2, каталог в конце)."""
import struct, sys, os

def img_list(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'VER2':
        raise ValueError('не IMG v2 (нет VER2)')
    count = struct.unpack_from('<I', data, len(data) - 4)[0]
    dir_size = 4 + 72 * count
    dir_start = len(data) - dir_size
    entries = []
    for i in range(count):
        off_blk, size_blk = struct.unpack_from('<II', data, dir_start + 4 + 72 * i)
        name = data[dir_start + 4 + 72 * i + 8 : dir_start + 4 + 72 * i + 72].split(b'\0')[0].decode('ascii', 'replace')
        entries.append((name, off_blk * 2048, size_blk * 2048))
    return data, entries

def main():
    img = sys.argv[1]
    data, entries = img_list(img)
    print('entries:', len(entries))
    for name, off, size in entries:
        print(f'  {off:>10} {size:>10}  {name}')
    for name, off, size in entries:
        if name.lower() in ('player.dff', 'player.txd'):
            out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work', name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'wb') as f:
                f.write(data[off:off+size])
            print('extracted:', out, 'size', size)

if __name__ == '__main__':
    main()