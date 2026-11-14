#include <3ds.h>
#include <citro3d.h>
#include <citro2d.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "player.hpp"
#include "world.hpp"
#include "render.hpp"
#include "gsmod.hpp"
#include "gsmap.hpp"
#include "cj_bin.h"
#include "grove_bin.h"

static stone::Player player;
static bool running = true;
static stone::GsMap map;   // для FPS-экрана

static void handleInput(u32 held, u32 down) {
    player.accel = (held & KEY_R) ? 2.5f : 1.0f; // R - бег
    if (down & KEY_B) player.jump();
    if (down & KEY_START) running = false;
}

static float yawFromForward(const stone::Vec3& f) {
    float yaw = atan2f(f.x, -f.z);
    return yaw;
}

int main() {
    gfxInitDefault();
    // Нижний экран — диагностическая консоль
    consoleInit(GFX_BOTTOM, NULL);
    // Увеличенный command buffer: много вершин карты через C3D_ImmSendAttrib.
    C3D_Init(0xC0000);
    stone::RenderInit();

    // загружаем модель CJ (вшита в бинарник через bin2o: cj.bin -> cj_bin / cj_bin_size)
    stone::GsModel model;
    if (stone::gsmodLoad(model, cj_bin, cj_bin_size)) {
        stone::GsmSetModel(model);
        printf("CJ model loaded: %u bones, %u parts\n", (unsigned)model.numBones, (unsigned)model.numParts);
    } else {
        printf("CJ model FAILED to load!\n");
    }

    // карта (grove.bin -> grove_bin / grove_bin_size)
    stone::GsMap map2;
    if (stone::gsmapLoad(map2, grove_bin, grove_bin_size)) {
        map = map2;
        stone::GsmSetMap(map2);
        printf("Map loaded: %ux%u sectors, %u models\n", (unsigned)map2.numSectorsX, (unsigned)map2.numSectorsZ, (unsigned)map2.numModels);
    } else {
        printf("Map FAILED to load!\n");
    }

    stone::World world;
    world.init();
    player.reset(world.spawn());

    stone::RenderSetWorld(&world);
    stone::SetPlayerPos(player.position);

    while (aptMainLoop()) {
        hidScanInput();
        u32 held = hidKeysHeld();
        u32 down = hidKeysDown();
        handleInput(held, down);

        // FPS-счётчик (нижний экран)
        static int frames = 0;
        static double last = 0.0;
        double now = svcGetSystemTick() / 268123480.0;
        frames++;
        if (now - last >= 1.0) {
            consoleClear();
            printf("GTA Sandstone\n");
            printf("pos: %.1f %.1f %.1f\n", player.position.x, player.position.y, player.position.z);
            printf("fps: %d\n", frames);
            printf("sec: %d/%d\n", map.numSectorsX * map.numSectorsZ, map.numSectorsX * map.numSectorsZ);
            frames = 0;
            last = now;
        }

        player.update(held, world);

        // Камера: позади игрока, смотрим на него
        stone::Camera cam;
        cam.pos = player.position + stone::Vec3(-3.5f, 3.2f, 2.5f);
        cam.look = player.position + stone::Vec3(0, 1.4f, 0);

        stone::SetPlayerPos(player.position);
        stone::SetPlayerAnim((stone::AnimType)player.animState());
        stone::SetPlayerFacing(yawFromForward(player.forward));
        stone::SetAnimTime(player.animTime());
        stone::RenderFrame(cam);

        if (!running) break;
    }

    stone::RenderShutdown();
    C3D_Fini();
    gfxExit();
    return 0;
}
