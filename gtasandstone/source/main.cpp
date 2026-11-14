#include <3ds.h>
#include <citro3d.h>
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

static void handleInput(u32 held, u32 down) {
    player.accel = (held & KEY_R) ? 2.5f : 1.0f; // R - бег
    if (down & KEY_B) player.jump();
    if (down & KEY_START) running = false;
}

static float yawFromForward(const stone::Vec3& f) {
    // forward (x,z) -> yaw вокруг Y. У нас камера: z вперёд мир, but forward.z=-1 по умолчанию
    float yaw = atan2f(f.x, -f.z);
    return yaw;
}

int main() {
    gfxInitDefault();
    C3D_Init(C3D_DEFAULT_CMDBUF_SIZE);
    stone::RenderInit();

    // загружаем модель CJ (вшита в бинарник через bin2o: cj.bin -> cj_bin / cj_bin_size)
    stone::GsModel model;
    if (stone::gsmodLoad(model, cj_bin, cj_bin_size)) {
        stone::GsmSetModel(model);
        printf("CJ model loaded: %u bones, %u parts\n", model.numBones, model.numParts);
    } else {
        printf("CJ model FAILED to load!\n");
    }

    // карта (grove.bin -> grove_bin / grove_bin_size)
    stone::GsMap map;
    if (stone::gsmapLoad(map, grove_bin, grove_bin_size)) {
        stone::GsmSetMap(map);
        printf("Map loaded: %ux%u sectors, %u models\n", map.numSectorsX, map.numSectorsZ, map.numModels);
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