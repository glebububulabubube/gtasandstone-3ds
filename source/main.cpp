#include <3ds.h>
#include <citro3d.h>

#include "player.hpp"
#include "world.hpp"
#include "render.hpp"

static stone::Player player;
static bool running = true;

static void handleInput(u32 held, u32 down) {
    player.accel = (held & KEY_R) ? 2.5f : 1.0f; // R - бег
    if (down & KEY_B) player.jump();
    if (down & KEY_START) running = false;
}

int main() {
    gfxInitDefault();
    C3D_Init(C3D_DEFAULT_CMDBUF_SIZE);
    RenderInit();

    stone::World world;
    world.init();
    player.reset(world.spawn());

    RenderSetWorld(&world);
    SetPlayerPos(player.position);

    while (aptMainLoop()) {
        hidScanInput();
        u32 held = hidKeysHeld();
        u32 down = hidKeysDown();
        handleInput(held, down);

        player.update(held, world);

        // Камера: позади игрока, смотрим на него
        Camera cam;
        cam.pos = player.position + Vec3(-3.5f, 3.2f, 2.5f);
        cam.look = player.position + Vec3(0, 1.4f, 0);

        SetPlayerPos(player.position);
        RenderFrame(cam);

        if (!running) break;
    }

    RenderShutdown();
    C3D_Fini();
    gfxExit();
    return 0;
}