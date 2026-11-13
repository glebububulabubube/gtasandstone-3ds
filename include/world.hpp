#pragma once
// Простая тестовая карта: набор платформ-боксов.

#include "engine.hpp"

namespace stone {

struct World {
    enum { MAX_BOXES = 64 };
    Box boxes[MAX_BOXES];
    int count = 0;

    void init();
    void addBox(const Vec3& center, const Vec3& half);

    // высота земли под точкой (максимум по всем боксам, XZ — внутри)
    float groundAt(const Vec3& p) const;

    // точка спавна персонажа
    Vec3 spawn() const;

    // границы зоны для камеры
    Vec3 center;
    float radius;
};

} // namespace stone