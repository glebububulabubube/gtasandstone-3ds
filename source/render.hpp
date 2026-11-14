#pragma once
// Рендер тестовой карты и персонажа CJ (модель .gsmod) через citro3d (PICA200) на Old 3DS.

#include "engine.hpp"
#include "world.hpp"
#include "skeleton.hpp"
#include "gsmod.hpp"
#include "gsmap.hpp"

namespace stone {

void RenderInit();
void RenderShutdown();
void SetPlayerPos(const Vec3& p);
void SetPlayerAnim(AnimType anim);
void SetPlayerFacing(float yawRad);
void SetAnimTime(float t);
// передаёт загруженную модель в рендер (владение остаётся у вызывающего)
void GsmSetModel(const GsModel& m);
// передаёт загруженную карту (.gsmap) в рендер (владение переходит к рендеру)
void GsmSetMap(const GsMap& m);

// Отрисовка кадра: камера + персонаж + карта
void RenderFrame(const Camera& cam);
void RenderSetWorld(World* w);

} // namespace stone