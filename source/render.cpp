#include "render.hpp"
#include <3ds.h>
#include <citro3d.h>
#include <string.h>
#include <math.h>
#include <stdio.h>          // <-- ДОБАВЛЕНО (для printf)
#include "gsmod.hpp"
#include "gsmap.hpp"
#include "vshader_shbin.h"

namespace stone {

static C3D_RenderTarget* g_target = nullptr;
static World* g_world = nullptr;
static Vec3 g_playerPos;
static AnimType g_anim = ANIM_IDLE;
static float g_facing = 0.0f;
static float g_animTime = 0.0f;
static GsModel g_model;
static bool g_modelLoaded = false;
static C3D_Tex g_tex[8];
static int g_texCount = 0;
static C3D_Tex g_whiteTex;

static GsMap g_map;
static bool g_mapLoaded = false;

static DVLB_s* g_dvlb = nullptr;
static shaderProgram_s g_program;
static int g_uLocProjection = -1;
static C3D_Mtx g_projection;

#define DISPLAY_TRANSFER_FLAGS \
	(GX_TRANSFER_FLIP_VERT(0) | GX_TRANSFER_OUT_TILED(0) | GX_TRANSFER_RAW_COPY(0) | \
	GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8) | GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB8) | \
	GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO))

static bool uploadTextures(const GsModel& m) {
    if (!m.numTextures) return false;
    g_texCount = (m.numTextures < 8) ? (int)m.numTextures : 8;
    bool ok = true;
    for (int i = 0; i < g_texCount; ++i) {
        const GsTexture& t = m.textures[i];
        if (t.w > 1024 || t.h > 1024) { ok = false; continue; }
        if (!C3D_TexInit(&g_tex[i], t.w, t.h, GPU_RGBA8)) { printf("tex init fail %d\n", i); ok = false; continue; }
        C3D_TexSetFilter(&g_tex[i], GPU_LINEAR, GPU_LINEAR);
        C3D_TexSetWrap(&g_tex[i], GPU_CLAMP_TO_EDGE, GPU_CLAMP_TO_EDGE);
        C3D_TexUpload(&g_tex[i], t.rgba);
        printf("tex %d: '%s' %ux%u\n", i, t.name, (unsigned)t.w, (unsigned)t.h);
    }
    return ok;
}

static void freeTextures() {
    for (int i = 0; i < g_texCount; ++i) {
        C3D_TexDelete(&g_tex[i]);
        memset(&g_tex[i], 0, sizeof(C3D_Tex));
    }
    g_texCount = 0;
}

void RenderInit() {
    g_target = C3D_RenderTargetCreate(240, 400, GPU_RB_RGBA8, GPU_RB_DEPTH24_STENCIL8);
    C3D_RenderTargetSetOutput(g_target, GFX_TOP, GFX_LEFT, DISPLAY_TRANSFER_FLAGS);

    g_dvlb = DVLB_ParseFile((u32*)vshader_shbin, vshader_shbin_size);
    shaderProgramInit(&g_program);
    shaderProgramSetVsh(&g_program, &g_dvlb->DVLE[0]);
    C3D_BindProgram(&g_program);

    g_uLocProjection = shaderInstanceGetUniformLocation(g_program.vertexShader, "projection");

    C3D_AttrInfo* attrInfo = C3D_GetAttrInfo();
    AttrInfo_Init(attrInfo);
    AttrInfo_AddLoader(attrInfo, 0, GPU_FLOAT, 3);
    AttrInfo_AddLoader(attrInfo, 1, GPU_FLOAT, 3);
    AttrInfo_AddLoader(attrInfo, 2, GPU_FLOAT, 2);

    C3D_TexEnv* env = C3D_GetTexEnv(0);
    C3D_TexEnvInit(env);
    C3D_TexEnvSrc(env, C3D_Both, GPU_TEXTURE0, GPU_PRIMARY_COLOR, GPU_PRIMARY_COLOR);
    C3D_TexEnvFunc(env, C3D_Both, GPU_MODULATE);

    Mtx_PerspTilt(&g_projection, C3D_AngleFromDegrees(60.0f), C3D_AspectRatioTop, 0.1f, 300.0f, false);

    uint8_t white[4] = {255, 255, 255, 255};
    C3D_TexInit(&g_whiteTex, 1, 1, GPU_RGBA8);
    C3D_TexSetFilter(&g_whiteTex, GPU_NEAREST, GPU_NEAREST);
    C3D_TexSetWrap(&g_whiteTex, GPU_CLAMP_TO_EDGE, GPU_CLAMP_TO_EDGE);
    C3D_TexUpload(&g_whiteTex, white);
}

void RenderShutdown() {
    freeTextures();
    C3D_TexDelete(&g_whiteTex);
    if (g_modelLoaded) gsmodFree(g_model);
    if (g_mapLoaded) gsmapFree(g_map);
    shaderProgramFree(&g_program);
    DVLB_Free(g_dvlb);
}

void RenderSetWorld(World* w) { g_world = w; }
void GsmSetMap(const GsMap& m) {
    if (g_mapLoaded) gsmapFree(g_map);
    g_map = m;
    g_mapLoaded = (m.models != 0 && m.sectors != 0);
}
void SetPlayerPos(const Vec3& p) { g_playerPos = p; }
void SetPlayerAnim(AnimType anim) { g_anim = anim; }
void SetPlayerFacing(float yawRad) { g_facing = yawRad; }
void SetAnimTime(float t) { g_animTime = t; }
void GsmSetModel(const GsModel& m) {
    if (g_modelLoaded) gsmodFree(g_model);
    g_model = m;
    g_modelLoaded = (m.bones != 0);
    freeTextures();
    uploadTextures(g_model);
}

static inline void vert(float x, float y, float z, float r, float g, float b, float u, float v) {
    C3D_ImmSendAttrib(x, y, z, 1.0f);
    C3D_ImmSendAttrib(r, g, b, 1.0f);
    C3D_ImmSendAttrib(u, v, 0.0f, 1.0f);
}

static void drawQuad(const Vec3* v, float cr, float cg, float cb) {
    C3D_ImmDrawBegin(GPU_TRIANGLES);
    vert(v[0].x, v[0].y, v[0].z, cr, cg, cb, 0, 0);
    vert(v[1].x, v[1].y, v[1].z, cr, cg, cb, 1, 0);
    vert(v[3].x, v[3].y, v[3].z, cr, cg, cb, 0, 1);
    vert(v[1].x, v[1].y, v[1].z, cr, cg, cb, 1, 0);
    vert(v[2].x, v[2].y, v[2].z, cr, cg, cb, 1, 1);
    vert(v[3].x, v[3].y, v[3].z, cr, cg, cb, 0, 1);
    C3D_ImmDrawEnd();
}

static void drawBox(const Vec3& centre, const Vec3& half, u32 rgb) {
    float x0 = centre.x-half.x, x1 = centre.x+half.x;
    float y0 = centre.y-half.y, y1 = centre.y+half.y;
    float z0 = centre.z-half.z, z1 = centre.z+half.z;

    Vec3 p[8] = {
        Vec3(x0,y0,z0), Vec3(x1,y0,z0), Vec3(x1,y1,z0), Vec3(x0,y1,z0),
        Vec3(x0,y0,z1), Vec3(x1,y0,z1), Vec3(x1,y1,z1), Vec3(x0,y1,z1)
    };

    float r = ((rgb>>16)&0xFF)/255.0f, g = ((rgb>>8)&0xFF)/255.0f, b = (rgb&0xFF)/255.0f;

    Vec3 quad[4];
    quad[0]=p[3]; quad[1]=p[2]; quad[2]=p[6]; quad[3]=p[7];
    drawQuad(quad, r, g, b);
    quad[0]=p[0]; quad[1]=p[4]; quad[2]=p[5]; quad[3]=p[1];
    drawQuad(quad, r*0.5f, g*0.5f, b*0.5f);
    quad[0]=p[1]; quad[1]=p[5]; quad[2]=p[6]; quad[3]=p[2];
    drawQuad(quad, r*0.8f, g*0.8f, b*0.8f);
    quad[0]=p[0]; quad[1]=p[3]; quad[2]=p[7]; quad[3]=p[4];
    drawQuad(quad, r*0.7f, g*0.7f, b*0.7f);
    quad[0]=p[4]; quad[1]=p[7]; quad[2]=p[6]; quad[3]=p[5];
    drawQuad(quad, r*0.9f, g*0.9f, b*0.9f);
    quad[0]=p[0]; quad[1]=p[1]; quad[2]=p[2]; quad[3]=p[3];
    drawQuad(quad, r*0.6f, g*0.6f, b*0.6f);
}

// --- CJ ---
static void drawCJ(const Vec3& feetPos, float yaw, AnimType anim, float time) {
    if (!g_modelLoaded) return;

    static const float FEET_OFFSET = 1.05f;

    Mat34 world[64];
    animateSkeleton(g_model, anim, time, 0.0f, world);

    float cy = cosf(yaw), sy = sinf(yaw);

    uint32_t curTex = 0xFFFFFFFF;
    for (uint32_t pi = 0; pi < g_model.numParts; ++pi) {
        const GsPart& p = g_model.parts[pi];
        if (!p.numVerts || !p.numTris) continue;

        uint16_t tid = p.matTex ? p.matTex[0] : 0xFFFF;
        if (tid >= g_texCount) {
            if (curTex != 0xFFFFFFFF) { C3D_TexBind(0, &g_whiteTex); curTex = 0xFFFFFFFF; }
        } else if (tid != curTex) {
            C3D_TexBind(0, &g_tex[tid]);
            curTex = tid;
        }

        C3D_ImmDrawBegin(GPU_TRIANGLES);
        for (uint32_t t = 0; t < p.numTris; ++t) {
            for (int k = 0; k < 3; ++k) {
                uint32_t idx = p.tris[t*3 + k];
                if (idx >= p.numVerts) continue;
                const GsVertex& v = p.verts[idx];
                float out[3];
                skinVertex(g_model, world, v.b0, v.w0, v.b1, v.w1, &v.px, out);
                float mx = out[0], my = out[2], mz = -out[1];
                float wx = mx*cy + mz*sy + feetPos.x;
                float wy = my + FEET_OFFSET + feetPos.y;
                float wz = -mx*sy + mz*cy + feetPos.z;

                uint32_t col = 0xFFFFFF;
                if (p.matColors && p.numMats) col = p.matColors[0];
                float cr = ((col>>16)&0xFF)/255.0f, cg = ((col>>8)&0xFF)/255.0f, cb = (col&0xFF)/255.0f;
                float nl = 0.6f + 0.4f*fmaxf(0.0f, v.nz);
                C3D_ImmSendAttrib(wx, wy, wz, 1.0f);
                C3D_ImmSendAttrib(cr*nl, cg*nl, cb*nl, 1.0f);
                C3D_ImmSendAttrib(v.u, v.v, 0.0f, 1.0f);
            }
        }
        C3D_ImmDrawEnd();
    }
}

// --- Проверочный текстурированный квад с лицом (для диагностики текстур) ---
static void drawTestQuad() {
    if (g_texCount < 1) return;
    C3D_TexBind(0, &g_tex[0]);
    C3D_ImmDrawBegin(GPU_TRIANGLES);
    float s = 1.2f;
    float x0 = g_playerPos.x - s, x1 = g_playerPos.x + s;
    float y0 = 0.1f, y1 = y0 + 2.0f;
    float z = g_playerPos.z - 3.0f;
    vert(x0, y0, z, 1,1,1, 0, 0);
    vert(x1, y0, z, 1,1,1, 1, 0);
    vert(x1, y1, z, 1,1,1, 1, 1);
    vert(x0, y0, z, 1,1,1, 0, 0);
    vert(x1, y1, z, 1,1,1, 1, 1);
    vert(x0, y1, z, 1,1,1, 0, 1);
    C3D_ImmDrawEnd();
}

void RenderFrame(const Camera& cam) {
    if (!g_target || !g_world) return;

    C3D_Mtx view;
    Mtx_LookAt(&view,
               FVec3_New(cam.pos.x,  cam.pos.y,  cam.pos.z),
               FVec3_New(cam.look.x, cam.look.y, cam.look.z),
               FVec3_New(0.0f, 1.0f, 0.0f), false);

    C3D_Mtx projView;
    Mtx_Multiply(&projView, &g_projection, &view);

    C3D_FrameBegin(C3D_FRAME_SYNCDRAW);
    C3D_RenderTargetClear(g_target, C3D_CLEAR_ALL, 0x68B0D8FF, 0);
    C3D_FrameDrawOn(g_target);

    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER, g_uLocProjection, &projView);
    C3D_DepthTest(true, GPU_GEQUAL, GPU_WRITE_ALL);

    // --- Карта: стриминг секторов вокруг игрока ---
    C3D_TexBind(0, &g_whiteTex);
    for (int i = 0; i < g_world->count; ++i) {
        const Box& b = g_world->boxes[i];
        Vec3 c = (b.min + b.max) * 0.5f;
        Vec3 h = (b.max - b.min) * 0.5f;
        u32 col = (i == 0) ? 0x3CB371 : 0x8B7355;
        drawBox(c, h, col);
    }

    if (g_mapLoaded) {
        int sectors[16];
        int ns = gsmapSectorsAround(g_map, g_playerPos.x, g_playerPos.z, 250.0f, sectors, 12);
        C3D_TexBind(0, &g_whiteTex);
        uint32_t drawnVerts = 0;
        uint32_t drawnModels = 0;
        for (int si = 0; si < ns; ++si) {
            const GsMapSector& sec = g_map.sectors[sectors[si]];
            for (uint32_t ii = 0; ii < sec.count; ++ii) {
                if (drawnModels >= 500) break;
                const GsMapInstance& inst = sec.insts[ii];
                if (inst.model >= g_map.numModels) continue;
                const GsMapModel& mod = g_map.models[inst.model];
                if (!mod.numVerts || !mod.numTris) continue;
                drawnVerts += mod.numVerts;
                if (drawnVerts > 60000) { drawnVerts -= mod.numVerts; continue; }
                drawnModels++;

                uint32_t col = 0xCCCCCC;
                if (mod.matColors && mod.numMats) col = mod.matColors[0];

                float x=inst.qx, y=inst.qy, z=inst.qz, w=inst.qw;
                float r[9] = {
                    1-2*(y*y+z*z), 2*(x*y-w*z),   2*(x*z+w*y),
                    2*(x*y+w*z),   1-2*(x*x+z*z), 2*(y*z-w*x),
                    2*(x*z-w*y),   2*(y*z+w*x),   1-2*(x*x+y*y),
                };

                C3D_ImmDrawBegin(GPU_TRIANGLES);
                for (uint32_t t = 0; t < mod.numTris; ++t) {
                    for (int k = 0; k < 3; ++k) {
                        uint32_t idx = mod.tris[t*3 + k];
                        if (idx >= mod.numVerts) continue;
                        const GsMapVertex& v = mod.verts[idx];
                        float lx = r[0]*v.px + r[1]*v.py + r[2]*v.pz + inst.pos.x;
                        float ly = r[3]*v.px + r[4]*v.py + r[5]*v.pz + inst.pos.y;
                        float lz = r[6]*v.px + r[7]*v.py + r[8]*v.pz + inst.pos.z;
                        float wx = lx;
                        float wy = lz;
                        float wz = -ly;
                        float l = 0.6f + 0.4f*fmaxf(0.0f, v.nz);
                        float cr = ((col>>16)&0xFF)/255.0f*l;
                        float cg = ((col>>8)&0xFF)/255.0f*l;
                        float cb = (col&0xFF)/255.0f*l;
                        C3D_ImmSendAttrib(wx, wy, wz, 1.0f);
                        C3D_ImmSendAttrib(cr, cg, cb, 1.0f);
                        C3D_ImmSendAttrib(v.u, v.v, 0.0f, 1.0f);
                    }
                }
                C3D_ImmDrawEnd();
            }
        }
    }

    // --- Персонаж + проверочный квад с текстурой ---
    drawCJ(g_playerPos, g_facing, g_anim, g_animTime);
    drawTestQuad();

    C3D_FrameEnd(0);
}

} // namespace stone
