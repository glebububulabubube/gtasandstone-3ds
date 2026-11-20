#pragma once
// Загрузка .gsmod (собственный формат gtasandstone): скелет, меши, текстуры.
// Заголовок: 'GSMOD' u32 версия(=4), u32 numBones, u32 numParts, u32 totalVerts
// Кость: name[32], parent i16, flags u32, local 3x4 (12f), invmat 3x4 (12f)
// Часть: numVerts u32, numTris u16, numMats u16,
//   verts: pos 3f, norm 3f, uv 2f, bone0 u16, w0 f32, bone1 u16, w1 f32
//   tris: 3x u32, mats: (color u32, texid u16) x numMats
// Таблица текстур: u32 count, (name[32], w u16, h u16, rgba w*h*4) x count

#include "engine.hpp"
#include <cstdint>

namespace stone {

struct GsBone {
    char name[32];
    int16_t parent;
    float local[12];   // 3x4: r0, r1, r2, t
    float invmat[12];  // 3x4: invmodel
};

struct GsVertex {
    float px, py, pz;
    float nx, ny, nz;
    float u, v;
    uint16_t b0, b1;
    float w0, w1;
};

struct GsPart {
    uint32_t numVerts;
    uint16_t numTris;
    uint16_t numMats;
    GsVertex* verts;
    uint32_t* tris;      // numTris*3 индексов
    uint32_t* matColors; // numMats цветов 0xRRGGBB
    uint16_t* matTex;    // numMats id текстур (0xFFFF = нет)
};

struct GsTexture {
    char name[32];
    uint16_t w, h;
    uint8_t* rgba;       // w*h*4
};

struct GsModel {
    uint32_t numBones;
    uint32_t numParts;
    uint32_t totalVerts;
    GsBone* bones;
    GsPart* parts;
    GsTexture* textures;
    uint32_t numTextures;
};

// Загружает .gsmod из памяти (данные копируются во внутренние буферы).
// Возвращает true при успехе.
bool gsmodLoad(GsModel& m, const void* data, uint32_t size);

// Освобождает память модели.
void gsmodFree(GsModel& m);

} // namespace stone