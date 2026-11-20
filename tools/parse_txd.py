#!/usr/bin/env python3
"""Парсер .txd GTA San Andreas: извлечение текстур в RGBA8 (PPM для проверки).

Пример:
    py -3 tools/parse_txd.py tools/extracted/head.txd tools/out_txd
"""
import os
import struct
import sys

# --- RenderWare чанки ---
CHUNK_TEXDICTIONARY = 0x16
CHUNK_TEXTURENATIVE = 0x15
CHUNK_RASTER = 0x19
CHUNK_STRUCT = 0x01
CHUNK_STRING = 0x02
CHUNK_EXTENSION = 0x03

# Форматы растра (PC-версия SA)
RASTER_8888 = 0x20
RASTER_888 = 0x21
RASTER_565 = 0x22
RASTER_4444 = 0x23
RASTER_5551 = 0x24
RASTER_1555 = 0x25
RASTER_8880 = 0x26
RASTER_PAL4 = 0x28
RASTER_PAL8 = 0x29
RASTER_DXT1 = 0x2A
RASTER_DXT3 = 0x2B
RASTER_DXT5 = 0x2C


def cstr(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("latin1", "replace")


def parse_txd(path: str):
    with open(path, "rb") as f:
        raw = f.read()

    if len(raw) < 12:
        raise SystemExit("файл слишком мал")

    typ, size, ver = struct.unpack_from("<III", raw, 0)
    if typ != CHUNK_TEXDICTIONARY:
        raise SystemExit(f"не TXD: тип 0x{typ:X}")

    # Тело TXD: version + count + deviceId
    tv = struct.unpack_from("<I", raw, 12)[0]
    count = struct.unpack_from("<H", raw, 16)[0]
    print(f"TXD dict v=0x{tv:X} count={count}")

    off = 20
    textures = []
    for i in range(count):
        if off + 12 > len(raw):
            raise SystemExit(f"директория оборвана на {i}")
        ctype, csize, cver = struct.unpack_from("<III", raw, off)
        if ctype != CHUNK_TEXTURENATIVE:
            print(f"  [warn] не TextureNative (0x{ctype:X}) на {i}, стоп")
            break
        body = off + 12
        if body + 80 > len(raw):
            raise SystemExit("body текстуры обрезан")

        # Format: u32? в SA скажем так — проверим эмпирически
        # Head 8bit: 0x09 — палитровый. Здесь раскладка:
        #   u32 rasterVersion; u16 format?? -> проверим по имени.
        # Известная раскладка из rwtools:
        #   0x00 rasterVersion u32
        #   0x04 format u16
        #   0x06 rasterFlags u16
        #   0x08 width u16
        #   0x0A height u16
        #   0x0C depth u8
        #   0x0D numLevels u8
        #   0x0E rasterType u8
        #   0x0F compression u8
        #   0x10 hasAlpha u8
        #   0x11 numPaletteEntries u8
        #   0x12 paletteDataSize u32
        #   0x16 name[32]
        #   0x36 mask[32]
        rver = struct.unpack_from("<I", raw, body + 0)[0]
        fmt = struct.unpack_from("<H", raw, body + 4)[0]
        flags = struct.unpack_from("<H", raw, body + 6)[0]
        w = struct.unpack_from("<H", raw, body + 8)[0]
        h = struct.unpack_from("<H", raw, body + 10)[0]
        depth = raw[body + 12]
        levels = raw[body + 13]
        rtype = raw[body + 14]
        comp = raw[body + 15]
        alpha = raw[body + 16]
        pal_n = raw[body + 17]
        pal_size = struct.unpack_from("<I", raw, body + 18)[0]
        name = cstr(raw[body + 22 : body + 54])
        mask = cstr(raw[body + 54 : body + 86])
        print(
            f"  tex[{i}] off=0x{off:X} rver=0x{rver:X} fmt=0x{fmt:02X} "
            f"flags=0x{flags:04X} {w}x{h} depth={depth} levels={levels} "
            f"rtype={rtype} comp={comp} alpha={alpha} palN={pal_n} palSize={pal_size} "
            f"name={name!r} mask={mask!r}"
        )
        textures.append((name, mask, fmt, w, h, depth, rtype, alpha, body))
        off = body + csize

    return textures


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    parse_txd(sys.argv[1])