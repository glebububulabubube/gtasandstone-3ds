#pragma once
// Простая тестовая карта: набор платформ-боксов.

#include "engine.hpp"

namespace stone {

// Максимальная высота уступа, с которым взаимодействуем как со ступенькой,
// а не как со стеной. Всё, что выше, надо перепрыгивать.
static const float STEP_HEIGHT = 0.6f;

struct World {
    enum { MAX_BOXES = 64 };
    Box boxes[MAX_BOXES];
    int count;

    World() : count(0), center(0, 0, 0), radius(19.0f) {}

    void init();
    void addBox(const Vec3& center, const Vec3& half);

    // высота опоры под точкой p (p.y — уровень ног персонажа)
    float groundAt(const Vec3& p) const;

    // точка спавна персонажа
    Vec3 spawn() const;

    // границы зоны
    Vec3 center;
    float radius;
};

} // namespace stone
