#include "world.hpp"

namespace stone {

void World::init() {
    count = 0;

    // Земля: плита 40x40, верх на y = 0
    addBox(Vec3(0.0f, -0.5f, 0.0f), Vec3(20.0f, 0.5f, 20.0f));

    // Лестница из трёх ступеней (каждая следующая +0.9)
    addBox(Vec3(2.0f, 0.45f,  4.0f), Vec3(2.0f, 0.45f, 2.0f));  // верх 0.9
    addBox(Vec3(2.0f, 0.90f,  0.0f), Vec3(2.0f, 0.90f, 2.0f));  // верх 1.8
    addBox(Vec3(2.0f, 1.35f, -4.0f), Vec3(2.0f, 1.35f, 2.0f));  // верх 2.7

    // Башня: на неё только прыжком с последней ступени
    addBox(Vec3(2.0f, 2.30f, -8.0f), Vec3(2.0f, 2.30f, 2.0f));  // верх 4.6

    // Висящая платформа над башней
    addBox(Vec3(-2.0f, 6.20f, -8.0f), Vec3(2.0f, 0.20f, 2.0f)); // верх 6.4

    // Стена справа — чтобы было обо что упереться
    addBox(Vec3(9.0f, 1.20f, 0.0f), Vec3(0.5f, 1.20f, 4.0f));   // верх 2.4

    center = Vec3(0.0f, 1.0f, 0.0f);
    radius = 19.0f;
}

void World::addBox(const Vec3& centre, const Vec3& half) {
    if (count >= MAX_BOXES) return;
    boxes[count++] = Box(centre - half, centre + half);
}

float World::groundAt(const Vec3& p) const {
    float top = -1e9f;

    for (int i = 0; i < count; ++i) {
        const Box& b = boxes[i];
        if (!b.containsXZ(p))       continue;
        if (b.max.y > p.y + STEP_HEIGHT) continue; // слишком высоко — опорой не считается
        if (b.max.y > top) top = b.max.y;
    }

    if (top < -1e8f) top = -100.0f; // упал за край карты
    return top;
}

Vec3 World::spawn() const {
    return Vec3(2.0f, 1.0f, 12.0f);
}

} // namespace stone
