#pragma once
// Загрузка карты .gsmap (собственный формат gtasandstone) + стриминг по секторам.
//
// Формат v2:
//   'GSMAP' u32 ver(=2)
//   f32 secSize, f32 originX, f32 originZ
//   u32 numSectorsX, u32 numSectorsZ, u32 numModels
//   models[..]: u32 numVerts, u32 numTris, u32 numMats,
//     verts (pos 3f + norm 3f + uv 2f), tris (3x u32), mats (color u32 x N)
//   sectors: u32 count, (modelIdx u16, pos 3f, quat xyzw 4f) x count

#include "engine.hpp"
#include <cstdint>

namespace stone {

struct GsMapVertex {
    float px, py, pz;
    float nx, ny, nz;
    float u, v;
};

struct GsMapModel {
    uint32_t numVerts, numTris, numMats;
    GsMapVertex* verts;
    uint32_t* tris;
    uint32_t* matColors;
};

#pragma pack(push, 1)
struct GsMapInstance {
    uint16_t model;
    Vec3 pos;
    float qx, qy, qz, qw;
};
#pragma pack(pop)

struct GsMapSector {
    uint32_t count;
    GsMapInstance* insts;
};

struct GsMap {
    float secSize;
    float originX, originZ;
    uint32_t numSectorsX, numSectorsZ;
    uint32_t numModels;
    GsMapModel* models;
    GsMapSector* sectors;  // [numSectorsZ * numSectorsX]
};

// Загружает карту из памяти (данные копируются).
bool gsmapLoad(GsMap& m, const void* data, uint32_t size);
void gsmapFree(GsMap& m);

// Индексы секторов, пересекающихся квадратом вокруг точки (world coords).
// Возвращает до maxOut индексов (z*numSectorsX + x).
int gsmapSectorsAround(const GsMap& m, float x, float z, float radius,
                       int* out, int maxOut);

} // namespace stone