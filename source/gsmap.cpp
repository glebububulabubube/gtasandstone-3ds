#include "gsmap.hpp"
#include <stdlib.h>
#include <string.h>
#include <math.h>

namespace stone {

bool gsmapLoad(GsMap& m, const void* data, uint32_t size) {
    const uint8_t* d = (const uint8_t*)data;
    if (size < 33) return false;
    if (memcmp(d, "GSMAP", 5) != 0) return false;

    uint32_t ver;
    memcpy(&ver, d + 5, 4);
    memcpy(&m.secSize, d + 9, 4);
    memcpy(&m.originX, d + 13, 4);
    memcpy(&m.originZ, d + 17, 4);
    memcpy(&m.numSectorsX, d + 21, 4);
    memcpy(&m.numSectorsZ, d + 25, 4);
    memcpy(&m.numModels, d + 29, 4);
    if (ver < 2) return false;
    if (m.secSize <= 0.0f) return false;

    uint32_t o = 33;
    m.models = (GsMapModel*)malloc(m.numModels * sizeof(GsMapModel));
    if (!m.models) return false;

    for (uint32_t i = 0; i < m.numModels; ++i) {
        GsMapModel& mod = m.models[i];
        if (o + 12 > size) { gsmapFree(m); return false; }
        memcpy(&mod.numVerts, d + o, 4); o += 4;
        memcpy(&mod.numTris, d + o, 4); o += 4;
        memcpy(&mod.numMats, d + o, 4); o += 4;

        mod.verts = (GsMapVertex*)malloc(mod.numVerts * sizeof(GsMapVertex));
        mod.tris = (uint32_t*)malloc((size_t)mod.numTris * 3 * 4);
        mod.matColors = (uint32_t*)malloc(mod.numMats * 4);
        if (!mod.verts || (mod.numTris && !mod.tris) || (mod.numMats && !mod.matColors)) {
            gsmapFree(m); return false;
        }
        if (o + (size_t)mod.numVerts * 32 > size) { gsmapFree(m); return false; }
        memcpy(mod.verts, d + o, (size_t)mod.numVerts * 32); o += (size_t)mod.numVerts * 32;
        memcpy(mod.tris, d + o, (size_t)mod.numTris * 12);   o += (size_t)mod.numTris * 12;
        memcpy(mod.matColors, d + o, (size_t)mod.numMats * 4); o += (size_t)mod.numMats * 4;
    }

    m.sectors = (GsMapSector*)malloc((size_t)m.numSectorsZ * m.numSectorsX * sizeof(GsMapSector));
    if (!m.sectors) { gsmapFree(m); return false; }
    for (uint32_t s = 0; s < m.numSectorsZ * m.numSectorsX; ++s) {
        GsMapSector& sec = m.sectors[s];
        if (o + 4 > size) { gsmapFree(m); return false; }
        memcpy(&sec.count, d + o, 4); o += 4;
        sec.insts = (GsMapInstance*)malloc(sec.count * sizeof(GsMapInstance));
        if (sec.count && !sec.insts) { gsmapFree(m); return false; }
        if (o + (size_t)sec.count * 30 > size) { gsmapFree(m); return false; }
        memcpy(sec.insts, d + o, (size_t)sec.count * 30); o += (size_t)sec.count * 30;
    }
    return true;
}

void gsmapFree(GsMap& m) {
    if (m.models) {
        for (uint32_t i = 0; i < m.numModels; ++i) {
            free(m.models[i].verts);
            free(m.models[i].tris);
            free(m.models[i].matColors);
        }
        free(m.models); m.models = 0;
    }
    if (m.sectors) {
        for (uint32_t s = 0; s < m.numSectorsZ * m.numSectorsX; ++s)
            free(m.sectors[s].insts);
        free(m.sectors); m.sectors = 0;
    }
    m.numModels = m.numSectorsX = m.numSectorsZ = 0;
}

int gsmapSectorsAround(const GsMap& m, float x, float z, float radius,
                       int* out, int maxOut) {
    if (!m.sectors || maxOut <= 0) return 0;
    int x0 = (int)floorf((x - radius - m.originX) / m.secSize);
    int x1 = (int)floorf((x + radius - m.originX) / m.secSize);
    int z0 = (int)floorf((z - radius - m.originZ) / m.secSize);
    int z1 = (int)floorf((z + radius - m.originZ) / m.secSize);
    if (x0 < 0) x0 = 0; if (z0 < 0) z0 = 0;
    if (x1 >= (int)m.numSectorsX) x1 = (int)m.numSectorsX - 1;
    if (z1 >= (int)m.numSectorsZ) z1 = (int)m.numSectorsZ - 1;

    int n = 0;
    for (int sz = z0; sz <= z1 && n < maxOut; ++sz)
        for (int sx = x0; sx <= x1 && n < maxOut; ++sx)
            out[n++] = sz * (int)m.numSectorsX + sx;
    return n;
}

} // namespace stone