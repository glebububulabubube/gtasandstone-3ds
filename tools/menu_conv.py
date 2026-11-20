#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конвертер меню gtasandstone:
  1) video -> ETC1-кадры (intro.bin), прореживание до ~15 fps
  2) картинка-титул -> RGBA 400x240 (title.bin)
  3) кнопки SKIP / PLAY -> RGBA-спрайты (skip.bin / play.bin)

Формат ETC1: блоки 4x4 линейно, little-endian, (w/4)*(h/4) по 8 байт.
intro.bin: u16 w, u16 h, u16 frames, затем N кадров ETC1 (w*u16? нет — w/4*h/4*8).
title.bin / skip.bin / play.bin: u16 w, u16 h, затем RGBA w*h*4 (GPU_RGBA8).
"""
import struct, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

MODIFIER = [
    (-8,  -2,  2,  8),
    (-17, -5,  5, 17),
    (-29, -9,  9, 29),
    (-42, -13, 13, 42),
    (-60, -18, 18, 60),
    (-80, -24, 24, 80),
    (-106, -33, 33, 106),
    (-183, -47, 47, 183),
]

def clamp255(v):
    return 0 if v < 0 else (255 if v > 255 else v)

def extend4(v): return v << 4 | v
def extend5(v): return v << 3 | v >> 2

def encode_etc1_rgb(img_rgb):
    """img_rgb: HxWx3 uint8, H,W кратны 4. Возвращает байты ETC1. Векторизовано по блокам."""
    h, w = img_rgb.shape[:2]
    bh, bw = h // 4, w // 4
    N = bh * bw
    blocks = img_rgb[:bh*4, :bw*4].reshape(bh, 4, bw, 4, 3)
    blocks = blocks.transpose(0, 2, 1, 3, 4).reshape(N, 4, 4, 3)

    subs = np.empty((4, N, 8, 3), dtype=np.float64)
    subs[0] = blocks[:, :, 0:2, :].reshape(N, 8, 3)
    subs[1] = blocks[:, :, 2:4, :].reshape(N, 8, 3)
    subs[2] = blocks[:, 0:2, :, :].reshape(N, 8, 3)
    subs[3] = blocks[:, 2:4, :, :].reshape(N, 8, 3)

    MOD = np.array(MODIFIER, dtype=np.int16)

    cws = np.empty((4, N, 3), dtype=np.int16)
    best_t = np.empty((4, N), dtype=np.int16)
    best_i = np.empty((4, N), dtype=np.int16)
    best_e = np.empty((4, N), dtype=np.float64)
    for s in range(4):
        sb = subs[s]
        mean = sb.mean(axis=1)
        cw = np.clip(np.round(mean * 15.0 / 255.0), 0, 15).astype(np.int16)
        base = ((cw << 4) | cw)
        colors = np.clip(base[:, None, None, :] + MOD[None, :, :, None], 0, 255)
        diff = colors[:, None, :, :, :] - sb[:, :, None, None, :]
        err = (diff.astype(np.float64) ** 2).sum(axis=(1, 4))
        bidx = err.reshape(N, 32).argmin(axis=1)
        best_t[s] = bidx // 4
        best_i[s] = bidx % 4
        best_e[s] = err.reshape(N, 32)[np.arange(N), bidx]
        cws[s] = cw

    err_f0 = best_e[0] + best_e[1]
    err_f1 = best_e[2] + best_e[3]
    use_f1 = err_f1 < err_f0

    cw0 = np.where(use_f1[:, None], cws[2], cws[0])
    cw1 = np.where(use_f1[:, None], cws[3], cws[1])
    t0 = np.where(use_f1, best_t[2], best_t[0])
    t1 = np.where(use_f1, best_t[3], best_t[1])
    i0 = np.where(use_f1, best_i[2], best_i[0])
    i1 = np.where(use_f1, best_i[3], best_i[1])

    yy, xx = np.mgrid[0:4, 0:4]
    sb_mask_f0 = xx < 2
    sb_mask_f1 = yy < 2
    sb_mask = np.where(use_f1[:, None, None], sb_mask_f1[None], sb_mask_f0[None])
    msb0 = (i0 >> 1) & 1; lsb0 = i0 & 1
    msb1 = (i1 >> 1) & 1; lsb1 = i1 & 1
    msb_pix = np.where(sb_mask, msb0[:, None, None], msb1[:, None, None])
    lsb_pix = np.where(sb_mask, lsb0[:, None, None], lsb1[:, None, None])

    r1, g1, b1 = cw0[:, 0], cw0[:, 1], cw0[:, 2]
    r2, g2, b2 = cw1[:, 0], cw1[:, 1], cw1[:, 2]
    word = (r1.astype(np.uint64) << 60) | (r2.astype(np.uint64) << 56) | \
           (g1.astype(np.uint64) << 52) | (g2.astype(np.uint64) << 48) | \
           (b1.astype(np.uint64) << 44) | (b2.astype(np.uint64) << 40) | \
           (t0.astype(np.uint64) << 37) | (t1.astype(np.uint64) << 34)
    word |= use_f1.astype(np.uint64) << 32
    pos = 31 - (yy * 4 + xx)
    msb_shift = pos[None, :, :].astype(np.uint64)
    lsb_shift = (pos - 16)[None, :, :].astype(np.uint64)
    word |= (msb_pix.astype(np.uint64) << msb_shift).sum(axis=(1, 2))
    word |= (lsb_pix.astype(np.uint64) << lsb_shift).sum(axis=(1, 2))
    return np.ascontiguousarray(word.astype('<u8')).tobytes()

def decode_etc1_block(data, off):
    q = struct.unpack_from('<Q', data, off)[0]
    flip = (q >> 32) & 1
    diff = (q >> 33) & 1
    t0 = (q >> 37) & 7
    t1 = (q >> 34) & 7
    if not diff:
        r1 = (q >> 60) & 0xF; r2 = (q >> 56) & 0xF
        g1 = (q >> 52) & 0xF; g2 = (q >> 48) & 0xF
        b1 = (q >> 44) & 0xF; b2 = (q >> 40) & 0xF
        c0 = np.array([extend4(r1), extend4(g1), extend4(b1)], dtype=float)
        c1 = np.array([extend4(r2), extend4(g2), extend4(b2)], dtype=float)
    else:
        r1 = (q >> 60) & 0x1F; dr2 = (q >> 56) & 7
        g1 = (q >> 52) & 0x1F; dg2 = (q >> 48) & 7
        b1 = (q >> 44) & 0x1F; db2 = (q >> 40) & 7
        def s3(v): return v - 8 if v & 4 else v
        r2 = clamp255(r1 + s3(dr2)); g2 = clamp255(g1 + s3(dg2)); b2 = clamp255(b1 + s3(db2))
        c0 = np.array([extend5(r1), extend5(g1), extend5(b1)], dtype=float)
        c1 = np.array([extend5(r2), extend5(g2), extend5(b2)], dtype=float)
    tab0 = MODIFIER[t0]; tab1 = MODIFIER[t1]
    pix = np.zeros((4, 4, 3), dtype=np.uint8)
    for yy in range(4):
        for xx in range(4):
            msb = (q >> (31 - (yy*4+xx))) & 1
            lsb = (q >> (15 - (yy*4+xx))) & 1
            idx = (msb << 1) | lsb
            sb = (0 if xx < 2 else 1) if flip == 0 else (0 if yy < 2 else 1)
            c = c0 if sb == 0 else c1
            mod = tab0[idx] if sb == 0 else tab1[idx]
            pix[yy, xx] = np.clip(c + mod, 0, 255).astype(np.uint8)
    return pix

def decode_etc1_rgb(data, w, h):
    out = np.zeros((h, w, 3), dtype=np.uint8)
    off = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            block = decode_etc1_block(data, off); off += 8
            out[by:by+4, bx:bx+4] = block[:min(4, h-by), :min(4, w-bx)]
    return out

def write_rgba_bin(path, arr):
    """arr: HxWx3 или HxWx4 uint8 -> файл с заголовком u16 w, u16 h."""
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        rgb = np.dstack([arr, np.full((h, w), 255, np.uint8)])
    else:
        rgb = arr
    with open(path, 'wb') as f:
        f.write(struct.pack('<HH', w, h))
        f.write(rgb.tobytes())
    print(f'  {os.path.basename(path)}: {w}x{h}, {os.path.getsize(path)} bytes')

def swizzle_rgba8(img, pw, ph):
    """img: HxWx3 или HxWx4 uint8 -> PICA200-swizzled RGBA8 в текстуру pw x ph (кратны 8).
    Блоки 8x8: tile = (y//8)*(pw//8) + (x//8), внутри tile: (y%8)*8 + (x%8)."""
    h, w = img.shape[:2]
    tex = np.zeros((ph, pw, 4), dtype=np.uint8)
    if img.shape[2] == 3:
        tex[:h, :w] = np.dstack([img, np.full((h, w), 255, np.uint8)])
    else:
        tex[:h, :w] = img
    out = bytearray(pw * ph * 4)
    for y in range(ph):
        for x in range(pw):
            tile = (y // 8) * (pw // 8) + (x // 8)
            pos = tile * 64 + (y % 8) * 8 + (x % 8)
            out[pos*4:pos*4+4] = tex[y, x].tobytes()
    return bytes(out)

def write_swizzled_rgba(path, img, pw, ph):
    """Пишет файл с заголовком u16 w, u16 h (реальные текстурные размеры) + swizzled RGBA8."""
    data = swizzle_rgba8(img, pw, ph)
    with open(path, 'wb') as f:
        f.write(struct.pack('<HH', pw, ph))
        f.write(data)
    print(f'  {os.path.basename(path)}: {pw}x{ph} swizzled RGBA8, {os.path.getsize(path)} bytes')

def gen_assets_header(outdir, names):
    """Генерит menu_assets.h с static const массивами для малых ассетов (title/skip/play).
    intro.bin слишком большой (24МБ) — он вшивается через bin2s (как cj.bin/grove.bin)."""
    lines = ['#pragma once', '// Авто-генерированный заголовок ассетов меню (menu_conv.py).', '// static const — не требует bin2s/bin2o.', '#include <cstdint>', '']
    for name in names:
        p = os.path.join(outdir, name + '.bin')
        data = open(p, 'rb').read()
        if len(data) > 4*1024*1024:
            print(f'  skip {name}.bin in header ({len(data)} bytes — слишком большой, через bin2s)')
            continue
        var = name.replace('.', '_')
        lines.append(f'static const unsigned char {var}_data[] = {{')
        n = 0
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            lines.append('    ' + ','.join(str(b) for b in chunk) + ',')
            n += 1
        lines.append('};')
        lines.append(f'static const unsigned int {var}_size = {len(data)};')
        lines.append('')
        print(f'  header: {name} -> {len(data)} bytes ({n} lines)')
    hpath = os.path.join(outdir, '..', '..', '..', 'include', 'menu_assets.h')
    with open(hpath, 'w') as f:
        f.write('\n'.join(lines))
    print(f'menu_assets.h written: {os.path.getsize(hpath)} bytes')

def button_sprite(text, w=200, h=64):
    """Полупрозрачная плашка с текстом -> RGBA HxWx4."""
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w-1, h-1], radius=14, fill=(0, 0, 0, 170), outline=(255, 255, 255, 220), width=2)
    font = None
    for fname in ('arialbd.ttf', 'arial.ttf', 'segoeuib.ttf', 'DejaVuSans-Bold.ttf'):
        for base in (r'C:\Windows\Fonts', '/usr/share/fonts/truetype/dejavu'):
            p = os.path.join(base, fname)
            if os.path.exists(p):
                try:
                    font = ImageFont.truetype(p, 34)
                except Exception:
                    font = None
                if font: break
        if font: break
    if font is None:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    d.text(((w-tw)//2 - bbox[0], (h-th)//2 - bbox[1]), text, font=font, fill=(255, 255, 255, 255))
    return np.array(img)

def cover_crop(img, W, H):
    """Масштаб с покрытием и центр-кроп до WxH."""
    tw, th = img.size
    scale = max(W / tw, H / th)
    nw, nh = int(round(tw*scale)), int(round(th*scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - W)//2, (nh - H)//2
    return img.crop((x0, y0, x0+W, y0+H))

def main():
    import imageio.v2 as iio
    video = r"C:\Users\Пользователь\Desktop\GTA San Andreas - Intro_144p.mp4"
    title_jpg = r"C:\Users\Пользователь\Desktop\b6ca4b3f4bf01a80e2158547a1e0088b28a1e5266cb0bc597f3c671db2c4fa77.jpg"
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work', 'menu')
    os.makedirs(outdir, exist_ok=True)

    W, H = 256, 144
    STEP = 2  # 30 fps -> ~15 fps (89 c -> 89 c, кадров вдвое меньше)

    reader = iio.get_reader(video)
    meta = reader.get_meta_data()
    fps = meta.get('fps', 30) or 30
    print(f'video: {W}x{H} fps={fps:.2f}, sample step={STEP}')

    frame_sz = (W//4)*(H//4)*8
    frames = 0
    intro_path = os.path.join(outdir, 'intro.bin')
    with open(intro_path, 'wb') as f:
        f.write(struct.pack('<HHH', W, H, 0))  # счётчик перепишем в конце
        first_check = None
        fi = 0
        for frame in reader:
            if fi % STEP != 0:
                fi += 1
                continue
            if frame.shape[0] != H or frame.shape[1] != W:
                frame = np.asarray(Image.fromarray(frame).resize((W, H), Image.LANCZOS))
            rgb = frame[..., :3].astype(np.uint8) if frame.ndim == 3 else np.stack([frame]*3, -1)
            etc = encode_etc1_rgb(rgb)
            f.write(etc)
            if first_check is None:
                first_check = (rgb, etc)
            frames += 1
            fi += 1
            if frames % 200 == 0: print(f'  frame {frames}')
        f.seek(4); f.write(struct.pack('<H', frames))   # frames пишется ПОСЛЕ w и h
        f.flush(); os.fsync(f.fileno())
    reader.close()
    print(f'intro.bin: {os.path.getsize(intro_path)} bytes, frames={frames} ({frames/(2670/30):.1f} fps actual)')

    # контроль энкодера: декод первого кадра и сравнение с оригиналом
    if first_check:
        rgb0, etc0 = first_check
        dec = decode_etc1_rgb(etc0, W, H)
        mae = float(np.abs(dec.astype(int) - rgb0.astype(int)).mean())
        print(f'  ETC1 sanity: first frame MAE={mae:.2f} (0..255, чем меньше тем лучше)')

    # титул 400x240 -> текстура 512x256 (swizzled RGBA8 для PICA200)
    pil = Image.open(title_jpg)
    if pil.mode != 'RGB':
        pil = pil.convert('RGB')
    title = cover_crop(pil, 400, 240)
    write_swizzled_rgba(os.path.join(outdir, 'title.bin'), np.array(title), 512, 256)

    # кнопки 200x64 -> текстуры 256x64 (swizzled RGBA8)
    write_swizzled_rgba(os.path.join(outdir, 'skip.bin'), button_sprite('SKIP'), 256, 64)
    write_swizzled_rgba(os.path.join(outdir, 'play.bin'), button_sprite('PLAY'), 256, 64)

    # заголовок с данными малых ассетов (title/skip/play); intro.bin (24МБ) — через bin2s как cj/grove
    gen_assets_header(outdir, ['title', 'skip', 'play'])

if __name__ == '__main__':
    main()