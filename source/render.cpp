#include "render.hpp"
#include <3ds.h>
#include <citro3d.h>
#include <string.h>
#include "vshader_shbin.h"

namespace stone {

static C3D_RenderTarget* g_target = nullptr;
static World* g_world = nullptr;
static Vec3 g_playerPos;

// Шейдер
static DVLB_s* g_dvlb = nullptr;
static shaderProgram_s g_program;
static int g_uLocProjection = -1;
static C3D_Mtx g_projection;

#define DISPLAY_TRANSFER_FLAGS \
	(GX_TRANSFER_FLIP_VERT(0) | GX_TRANSFER_OUT_TILED(0) | GX_TRANSFER_RAW_COPY(0) | \
	GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8) | GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB8) | \
	GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO))

void RenderInit() {
    g_target = C3D_RenderTargetCreate(240, 400, GPU_RB_RGBA8, GPU_RB_DEPTH24_STENCIL8);
    C3D_RenderTargetSetOutput(g_target, GFX_TOP, GFX_LEFT, DISPLAY_TRANSFER_FLAGS);

    g_dvlb = DVLB_ParseFile((u32*)vshader_shbin, vshader_shbin_size);
    shaderProgramInit(&g_program);
    shaderProgramSetVsh(&g_program, &g_dvlb->DVLE[0]);
    C3D_BindProgram(&g_program);

    g_uLocProjection = shaderInstanceGetUniformLocation(g_program.vertexShader, "projection");

    // В immediate-режиме формат и число компонент игнорируются, но загрузчики нужны.
    C3D_AttrInfo* attrInfo = C3D_GetAttrInfo();
    AttrInfo_Init(attrInfo);
    AttrInfo_AddLoader(attrInfo, 0, GPU_FLOAT, 3); // v0 = позиция
    AttrInfo_AddLoader(attrInfo, 1, GPU_FLOAT, 3); // v1 = цвет

    // Фрагментный TEV-блок: просто отдаём цвет вершины.
    // В C++ нельзя передавать 0 вместо enum-значения (старый пример из C),
    // поэтому все три источника указываем явно.
    C3D_TexEnv* env = C3D_GetTexEnv(0);
    C3D_TexEnvInit(env);
    C3D_TexEnvSrc(env, C3D_Both, GPU_PRIMARY_COLOR, GPU_PRIMARY_COLOR, GPU_PRIMARY_COLOR);
    C3D_TexEnvFunc(env, C3D_Both, GPU_REPLACE);

    // Mtx_PerspTilt обязателен: экран 3DS повёрнут, обычный Mtx_Persp даёт картинку "набок".
    Mtx_PerspTilt(&g_projection, C3D_AngleFromDegrees(60.0f), C3D_AspectRatioTop, 0.1f, 300.0f, false);
}

void RenderShutdown() {
    shaderProgramFree(&g_program);
    DVLB_Free(g_dvlb);
}

void RenderSetWorld(World* w) { g_world = w; }
void SetPlayerPos(const Vec3& p) { g_playerPos = p; }

// одна вершина: позиция + цвет
static inline void vert(float x, float y, float z, float r, float g, float b) {
    C3D_ImmSendAttrib(x, y, z, 1.0f);   // v0
    C3D_ImmSendAttrib(r, g, b, 1.0f);   // v1
}

// квад из 4 вершин (2 треугольника)
static void drawQuad(const Vec3* v, float cr, float cg, float cb) {
    C3D_ImmDrawBegin(GPU_TRIANGLES);
    vert(v[0].x, v[0].y, v[0].z, cr, cg, cb);
    vert(v[1].x, v[1].y, v[1].z, cr, cg, cb);
    vert(v[3].x, v[3].y, v[3].z, cr, cg, cb);
    vert(v[1].x, v[1].y, v[1].z, cr, cg, cb);
    vert(v[2].x, v[2].y, v[2].z, cr, cg, cb);
    vert(v[3].x, v[3].y, v[3].z, cr, cg, cb);
    C3D_ImmDrawEnd();
}

// куб: центр + половина размеров + цвет 0xRRGGBB
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

    // верх (+y)
    quad[0]=p[3]; quad[1]=p[2]; quad[2]=p[6]; quad[3]=p[7];
    drawQuad(quad, r, g, b);
    // низ (-y)
    quad[0]=p[0]; quad[1]=p[4]; quad[2]=p[5]; quad[3]=p[1];
    drawQuad(quad, r*0.5f, g*0.5f, b*0.5f);
    // +x
    quad[0]=p[1]; quad[1]=p[5]; quad[2]=p[6]; quad[3]=p[2];
    drawQuad(quad, r*0.8f, g*0.8f, b*0.8f);
    // -x
    quad[0]=p[0]; quad[1]=p[3]; quad[2]=p[7]; quad[3]=p[4];
    drawQuad(quad, r*0.7f, g*0.7f, b*0.7f);
    // +z
    quad[0]=p[4]; quad[1]=p[7]; quad[2]=p[6]; quad[3]=p[5];
    drawQuad(quad, r*0.9f, g*0.9f, b*0.9f);
    // -z
    quad[0]=p[0]; quad[1]=p[1]; quad[2]=p[2]; quad[3]=p[3];
    drawQuad(quad, r*0.6f, g*0.6f, b*0.6f);
}

void RenderFrame(const Camera& cam) {
    if (!g_target || !g_world) return;

    // Вид: из камеры на точку взгляда
    C3D_Mtx view;
    Mtx_LookAt(&view,
               FVec3_New(cam.pos.x,  cam.pos.y,  cam.pos.z),
               FVec3_New(cam.look.x, cam.look.y, cam.look.z),
               FVec3_New(0.0f, 1.0f, 0.0f), false);

    // Шейдер знает только одну матрицу — сразу projection * view
    C3D_Mtx projView;
    Mtx_Multiply(&projView, &g_projection, &view);

    C3D_FrameBegin(C3D_FRAME_SYNCDRAW);
    C3D_RenderTargetClear(g_target, C3D_CLEAR_ALL, 0x68B0D8FF, 0);
    C3D_FrameDrawOn(g_target);

    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER, g_uLocProjection, &projView);
    C3D_DepthTest(true, GPU_GEQUAL, GPU_WRITE_ALL);

    // --- Карта ---
    for (int i = 0; i < g_world->count; ++i) {
        const Box& b = g_world->boxes[i];
        Vec3 c = (b.min + b.max) * 0.5f;
        Vec3 h = (b.max - b.min) * 0.5f;
        u32 col = (i == 0) ? 0x3CB371 : 0x8B7355;
        drawBox(c, h, col);
    }

    // --- Персонаж (position = ноги) ---
    {
        const Vec3& at = g_playerPos;
        drawBox(at + Vec3(0.0f, 0.43f, 0.0f), Vec3(0.28f, 0.43f, 0.28f), 0x2B3A5B); // штаны
        drawBox(at + Vec3(0.0f, 1.17f, 0.0f), Vec3(0.34f, 0.31f, 0.22f), 0xEDEDED); // торс
        drawBox(at + Vec3(0.0f, 1.61f, 0.0f), Vec3(0.15f, 0.14f, 0.15f), 0xA9764F); // голова
        drawBox(at + Vec3(0.0f, 1.77f, 0.0f), Vec3(0.17f, 0.04f, 0.17f), 0x1A1A1A); // кепка
    }

    C3D_FrameEnd(0);
}

} // namespace stone
