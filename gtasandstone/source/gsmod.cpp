#include "gsmod.hpp"
#include <3ds.h>
#include <stdlib.h>
#include <string.h>

namespace stone {

bool gsmodLoad(GsModel& m, const void* data, uint32_t size) {
    const uint8_t* d = (const uint8_t*)data;
    if (size < 21) return false;
    if (memcmp(d, "GSMOD", 5) != 0) return false;

    uint32_t ver = 0, nb = 0, np = 0, tv = 0;
    memcpy(&ver, d + 5, 4);
    memcpy(&nb, d + 9, 4);
    memcpy(&np, d + 13, 4);
    memcpy(&tv, d + 17, 4);
    if (ver < 4 || nb == 0) return false;

    uint32_t o = 21;
    m.numBones = nb;
    m.numParts = np;
    m.totalVerts = tv;
    m.bones = (GsBone*)malloc(nb * sizeof(GsBone));
    if (!m.bones) return false;

    for (uint32_t i = 0; i < nb; ++i) {
        GsBone& b = m.bones[i];
        if (o + 32 > size) { gsmodFree(m); return false; }
        memcpy(b.name, d + o, 32); o += 32;
        int16_t parent; uint32_t flags;
        memcpy(&parent, d + o, 2); o += 2;
        memcpy(&flags, d + o, 4); o += 4;
        b.parent = parent;
        memcpy(b.local, d + o, 48); o += 48;
        memcpy(b.invmat, d + o, 48); o += 48;
    }

    m.parts = (GsPart*)malloc(np * sizeof(GsPart));
    if (!m.parts) { gsmodFree(m); return false; }

    for (uint32_t i = 0; i < np; ++i) {
        GsPart& p = m.parts[i];
        if (o + 8 > size) { gsmodFree(m); return false; }
        uint32_t numV; uint16_t numT, numM;
        memcpy(&numV, d + o, 4); o += 4;
        memcpy(&numT, d + o, 2); o += 2;
        memcpy(&numM, d + o, 2); o += 2;
        p.numVerts = numV; p.numTris = numT; p.numMats = numM;

        p.verts = (GsVertex*)malloc(numV * sizeof(GsVertex));
        p.tris = (uint32_t*)malloc((size_t)numT * 3 * sizeof(uint32_t));
        p.matColors = (uint32_t*)malloc(numM * sizeof(uint32_t));
        p.matTex = (uint16_t*)malloc(numM * sizeof(uint16_t));
        if (!p.verts || (numT && !p.tris) || (numM && (!p.matColors || !p.matTex))) {
            gsmodFree(m); return false;
        }

        for (uint32_t v = 0; v < numV; ++v) {
            if (o + 44 > size) { gsmodFree(m); return false; }
            GsVertex& gv = p.verts[v];
            memcpy(&gv.px, d + o, 12); o += 12; // pos
            memcpy(&gv.nx, d + o, 12); o += 12; // norm
            memcpy(&gv.u,  d + o, 8);  o += 8;  // uv
            memcpy(&gv.b0, d + o, 2);  o += 2;
            memcpy(&gv.w0, d + o, 4);  o += 4;
            memcpy(&gv.b1, d + o, 2);  o += 2;
            memcpy(&gv.w1, d + o, 4);  o += 4;
        }
        memcpy(p.tris, d + o, (size_t)numT * 3 * 4); o += (size_t)numT * 12;
        for (uint32_t mm = 0; mm < numM; ++mm) {
            memcpy(&p.matColors[mm], d + o, 4); o += 4;
            memcpy(&p.matTex[mm], d + o, 2); o += 2;
        }
    }

    if (o + 4 > size) { gsmodFree(m); return false; }
    memcpy(&m.numTextures, d + o, 4); o += 4;
    m.textures = (m.numTextures ? (GsTexture*)malloc(m.numTextures * sizeof(GsTexture)) : 0);
    for (uint32_t i = 0; i < m.numTextures; ++i) {
        GsTexture& t = m.textures[i];
        memcpy(t.name, d + o, 32); o += 32;
        memcpy(&t.w, d + o, 2); o += 2;
        memcpy(&t.h, d + o, 2); o += 2;
        uint32_t sz = (uint32_t)t.w * t.h * 4;
        if (o + sz > size) { gsmodFree(m); return false; }
        t.rgba = (uint8_t*)malloc(sz);
        if (!t.rgba) { gsmodFree(m); return false; }
        memcpy(t.rgba, d + o, sz); o += sz;
    }
    return true;
}

void gsmodFree(GsModel& m) {
    if (m.bones) { free(m.bones); m.bones = 0; }
    if (m.parts) {
        for (uint32_t i = 0; i < m.numParts; ++i) {
            free(m.parts[i].verts);
            free(m.parts[i].tris);
            free(m.parts[i].matColors);
            free(m.parts[i].matTex);
        }
        free(m.parts); m.parts = 0;
    }
    if (m.textures) {
        for (uint32_t i = 0; i < m.numTextures; ++i)
            free(m.textures[i].rgba);
        free(m.textures); m.textures = 0;
    }
    m.numBones = m.numParts = m.totalVerts = m.numTextures = 0;
}

} // namespace stone