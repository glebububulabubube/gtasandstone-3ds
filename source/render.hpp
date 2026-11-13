#pragma once
// Рендер тестовой карты и персонажа через citro3d (PICA200) на Old 3DS.

#include "engine.hpp"
#include "world.hpp"

namespace stone {

void RenderInit();
void RenderShutdown();
void SetPlayerPos(const Vec3& p);

// Отрисовка кадра: камера + персонаж + карта
void RenderFrame(const Camera& cam);
void RenderSetWorld(World* w);

} // namespace stone