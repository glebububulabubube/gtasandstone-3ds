#include "menu.hpp"
#include "render.hpp"
#include <citro3d.h>
#include <string.h>
#include <stdio.h>
#include "vshader_ui_shbin.h"

// Вшитые бинарники ассетов (bin2o): имя_без_точек + _bin / _bin_size
extern const u8 intro_bin[];
extern const u32 intro_bin_size;
extern const u8 title_bin[];
extern const u32 title_bin_size;
extern const u8 skip_bin[];
extern const u32 skip_bin_size;
extern const u8 play_bin[];
extern const u32 play_bin_size;

namespace stone {

// --- размеры ассетов (файлы: u16 w, u16 h, затем данные уже в целевом виде) ---
static const int VIDEO_W = 256, VIDEO_H = 144;
static const int VIDEO_TEX_H = 256;      // power-of-two текстура для кадра
static const int TITLE_TEX_W = 512, TITLE_TEX_H = 256;   // title.bin уже 512x256 swizzled
static const int BTN_TEX_W = 256, BTN_H = 64;            // skip/play.bin уже 256x64 swizzled

static C3D_Tex g_texVideo;   // ETC1 256x256 (нижние 112 строк пустые), данные линейные
static C3D_Tex g_texTitle;   // RGBA8 512x256 (уже свозиллинговые, из конвертера)
static C3D_Tex g_texSkip;    // RGBA8 256x64
static C3D_Tex g_texPlay;    // RGBA8 256x64

static DVLB_s* g_dvlb = nullptr;
static shaderProgram_s g_program;
static int g_uProj = -1;
static int g_introFrames = 0;

static C3D_RenderTarget* g_topUI = nullptr;
// Нижний экран: рисуем прямо во фреймбуфер (там консоль printf) — кнопки поверх консоли.
// Указатель фреймбуфера берём заново каждый кадр (gfx меняет буферы после swap).

// ETC1-данные одного кадра: (256/4)*(144/4)*8
static const size_t VIDEO_ETC1_FRAME_SZ = (256/4)*(144/4)*8;

static void bindTex(C3D_Tex* tex) {
    C3D_TexBind(0, tex);
    C3D_TexSetFilter(tex, GPU_LINEAR, GPU_LINEAR);
    C3D_TexSetWrap(tex, GPU_CLAMP_TO_EDGE, GPU_CLAMP_TO_EDGE);
}

// Квад в экранных координатах (x,y в пикселях от левого-верхнего), uv от 0..1
// y увеличивается вниз; V переворачиваем: текстуры у PICA200 верх-низ от низа.
static void uiQuad(float x0, float y0, float x1, float y1,
                   float u0, float v0, float u1, float v1,
                   float r, float g, float b, float a) {
    C3D_ImmDrawBegin(GPU_TRIANGLES);
    C3D_ImmSendAttrib(x0, y0, 0, 1);  C3D_ImmSendAttrib(r,g,b,a); C3D_ImmSendAttrib(u0,1.0f-v0,0,1);
    C3D_ImmSendAttrib(x1, y0, 0, 1);  C3D_ImmSendAttrib(r,g,b,a); C3D_ImmSendAttrib(u1,1.0f-v0,0,1);
    C3D_ImmSendAttrib(x1, y1, 0, 1);  C3D_ImmSendAttrib(r,g,b,a); C3D_ImmSendAttrib(u1,1.0f-v1,0,1);
    C3D_ImmSendAttrib(x0, y0, 0, 1);  C3D_ImmSendAttrib(r,g,b,a); C3D_ImmSendAttrib(u0,1.0f-v0,0,1);
    C3D_ImmSendAttrib(x1, y1, 0, 1);  C3D_ImmSendAttrib(r,g,b,a); C3D_ImmSendAttrib(u1,1.0f-v1,0,1);
    C3D_ImmSendAttrib(x0, y1, 0, 1);  C3D_ImmSendAttrib(r,g,b,a); C3D_ImmSendAttrib(u0,1.0f-v1,0,1);
    C3D_ImmDrawEnd();
}

static void pushProjOrtho(float w, float h) {
    C3D_Mtx ortho;
    Mtx_OrthoTilt(&ortho, 0.0f, w, h, 0.0f, -1.0f, 1.0f, false);
    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER, g_uProj, &ortho);
}

void MenuInit() {
    // Таргеты рендера для меню (без depth — чистый 2D)
    g_topUI = C3D_RenderTargetCreate(240, 400, GPU_RB_RGBA8, 0);
    C3D_RenderTargetSetOutput(g_topUI, GFX_TOP, GFX_LEFT, GX_TRANSFER_FLIP_VERT(0) | GX_TRANSFER_OUT_TILED(0) | GX_TRANSFER_RAW_COPY(0) |
                                                            GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8) | GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB8) |
                                                            GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO));

    // Нижний экран: фреймбуфер берём каждый кадр в drawButton (gfx меняет буферы после swap)

    // UI-шейдер (второй DVLB — не трогаем основной)
    g_dvlb = DVLB_ParseFile((u32*)vshader_ui_shbin, vshader_ui_shbin_size);
    if (g_dvlb) {
        shaderProgramInit(&g_program);
        shaderProgramSetVsh(&g_program, &g_dvlb->DVLE[0]);
        g_uProj = shaderInstanceGetUniformLocation(g_program.vertexShader, "u_proj");
    }

    C3D_AttrInfo* attrInfo = C3D_GetAttrInfo();
    AttrInfo_Init(attrInfo);
    AttrInfo_AddLoader(attrInfo, 0, GPU_FLOAT, 2);
    AttrInfo_AddLoader(attrInfo, 1, GPU_FLOAT, 4);
    AttrInfo_AddLoader(attrInfo, 2, GPU_FLOAT, 2);

    // --- video: 256x144 ETC1 -> текстура 256x256 (линейные блоки сверху) ---
    g_introFrames = 0;
    if (intro_bin_size >= 6) {
        memcpy(&g_introFrames, intro_bin + 4, 2);
        if (C3D_TexInit(&g_texVideo, VIDEO_W, VIDEO_TEX_H, GPU_ETC1)) {
            memset(g_texVideo.data, 0, g_texVideo.size);  // нижние 112 строк — пусто
            C3D_TexFlush(&g_texVideo);
        }
        // первые кадр загрузим при первом отображении (MenuFrame)
    }

    // --- title: уже 512x256 swizzled RGBA8 из конвертера ---
    if (title_bin_size >= TITLE_TEX_W*TITLE_TEX_H*4 + 4) {
        C3D_TexInit(&g_texTitle, TITLE_TEX_W, TITLE_TEX_H, GPU_RGBA8);
        C3D_TexUpload(&g_texTitle, title_bin + 4);
        C3D_TexFlush(&g_texTitle);
        bindTex(&g_texTitle);
    }

    // --- buttons: уже 256x64 swizzled RGBA8 ---
    if (skip_bin_size >= BTN_TEX_W*BTN_H*4 + 4) {
        C3D_TexInit(&g_texSkip, BTN_TEX_W, BTN_H, GPU_RGBA8);
        C3D_TexUpload(&g_texSkip, skip_bin + 4);
        C3D_TexFlush(&g_texSkip);
        bindTex(&g_texSkip);
    }
    if (play_bin_size >= BTN_TEX_W*BTN_H*4 + 4) {
        C3D_TexInit(&g_texPlay, BTN_TEX_W, BTN_H, GPU_RGBA8);
        C3D_TexUpload(&g_texPlay, play_bin + 4);
        C3D_TexFlush(&g_texPlay);
        bindTex(&g_texPlay);
    }
}

void MenuShutdown() {
    C3D_TexDelete(&g_texVideo);
    C3D_TexDelete(&g_texTitle);
    C3D_TexDelete(&g_texSkip);
    C3D_TexDelete(&g_texPlay);
    // возвращаем верхний экран игровому таргету (он был отцеплён в MenuInit)
    RenderRestoreTarget();
    C3D_RenderTargetDelete(g_topUI);
    if (g_dvlb) {
        shaderProgramFree(&g_program);
        DVLB_Free(g_dvlb);
        g_dvlb = nullptr;
    }
}

int MenuIntroFrames() { return g_introFrames; }

static bool inRect(int x, int y, int x0, int y0, int x1, int y1) {
    return x >= x0 && x <= x1 && y >= y0 && y <= y1;
}

static void drawButton(C3D_Tex* tex, float w, float h,
                       int bx0, int by0, int bx1, int by1, bool pressed) {
    C3D_FrameBuf fb;
    C3D_FrameBufAttrib(&fb, 320, 240, false);
    C3D_FrameBufColor(&fb, gfxGetFramebuffer(GFX_BOTTOM, GFX_LEFT, NULL, NULL), GPU_RB_RGBA8);
    C3D_FrameBufDepth(&fb, NULL, GPU_RB_DEPTH24);
    C3D_SetFrameBuf(&fb);
    C3D_SetViewport(0, 0, 320, 240);
    bindTex(tex);
    pushProjOrtho(w, h);
    uiQuad((float)bx0, (float)by0, (float)bx1, (float)by1,
           0.0f, 0.0f, 200.0f/256.0f, 1.0f, 1,1,1, pressed?0.85f:0.6f);
}

int MenuFrame(MenuMode mode, int frame, int touchX, int touchY, bool touchDown) {
    if (!g_dvlb) return 0;

    int btnX0 = (320-200)/2, btnY0 = 240-64-40;
    int btnX1 = btnX0+200,   btnY1 = btnY0+64;
    bool pressed = touchDown && inRect(touchX, touchY, btnX0, btnY0, btnX1, btnY1);

    C3D_BindProgram(&g_program);
    C3D_TexEnv* env = C3D_GetTexEnv(0);
    C3D_TexEnvInit(env);
    C3D_TexEnvSrc(env, C3D_Both, GPU_TEXTURE0, GPU_PRIMARY_COLOR, GPU_PRIMARY_COLOR);
    C3D_TexEnvFunc(env, C3D_Both, GPU_MODULATE);

    C3D_DepthTest(false, GPU_ALWAYS, GPU_WRITE_ALL);
    C3D_AlphaTest(true, GPU_GREATER, 0);
    C3D_AlphaBlend(GPU_BLEND_ADD, GPU_BLEND_ADD, GPU_SRC_ALPHA, GPU_ONE_MINUS_SRC_ALPHA,
                   GPU_ONE, GPU_ONE_MINUS_SRC_ALPHA);
    C3D_CullFace(GPU_CULL_NONE);

    C3D_FrameBegin(C3D_FRAME_SYNCDRAW);

    if (mode == MenuMode::MENU_INTRO) {
        // обновляем ETC1-кадр: копируем ровно 256x144 данных (не полный tex->size,
        // чтобы не выйти за конец intro.bin), затем сброс кэша
        if (frame >= 0 && frame < g_introFrames && intro_bin_size >= 6) {
            const uint8_t* src = intro_bin + 6 + (size_t)frame * VIDEO_ETC1_FRAME_SZ;
            memcpy(g_texVideo.data, src, VIDEO_ETC1_FRAME_SZ);
            C3D_TexFlush(&g_texVideo);
        }
        C3D_RenderTargetClear(g_topUI, C3D_CLEAR_COLOR, 0xFF000000, 0);
        C3D_FrameDrawOn(g_topUI);
        bindTex(&g_texVideo);
        pushProjOrtho(400.0f, 240.0f);
        // 16:9 в 5:3 — letterbox по бокам (чёрные поля)
        float aspectVideo = 256.0f/144.0f;
        float vh = 400.0f / aspectVideo;
        float vy0 = (240.0f - vh)*0.5f;
        uiQuad(0.0f, vy0, 400.0f, vy0+vh, 0.0f, 0.0f, 1.0f, 144.0f/256.0f, 1,1,1,1);

        drawButton(&g_texSkip, 320.0f, 240.0f, btnX0, btnY0, btnX1, btnY1, pressed);
    } else {
        C3D_RenderTargetClear(g_topUI, C3D_CLEAR_COLOR, 0xFF000000, 0);
        C3D_FrameDrawOn(g_topUI);
        bindTex(&g_texTitle);
        pushProjOrtho(400.0f, 240.0f);
        uiQuad(0, 0, 400, 240, 0.0f, 0.0f, 400.0f/512.0f, 240.0f/256.0f, 1,1,1,1);

        drawButton(&g_texPlay, 320.0f, 240.0f, btnX0, btnY0, btnX1, btnY1, pressed);
    }

    C3D_FrameEnd(0);

    return pressed ? 1 : 0;
}

} // namespace stone