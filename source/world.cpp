#include "world.hpp"

namespace stone {

void World::init() {
    count = 0;
    // Газовая площадка: большая плита (земля)
    addBox(Vec3(0, -0.5f, 0), Vec3(20, 0.5f, 20));
    // Несколько платформ разной высоты для прыжков на них
    addBox(Vec3(3, 1.0f, -2), Vec3(2, 1.0f, 2));
    addBox(Vec3(-3, 2.0f, 3), Vec3(2, 2.0f, 2));
    addBox(Vec3(5, 1.5f, 4), Vec3(2, 1.5f, 2));
    addBox(Vec3(-6, 2.5f, -4), Vec3(2, 2.5f, 2));
    // Пару стен/препятствий
    addBox(Vec3(8, 1.0f, 0), Vec3(0.5f, 1.0f, 3));

    center = Vec3(0, 1.0f, 0);
    radius = 22.0f;
}

void World::addBox(const Vec3& center, const Vec3& half) {
    if (count >= MAX_BOXES) return;
    boxes[count++] = Box(center - half, center + half);
}

float World::groundAt(const Vec3& p) const {
    float top = -1e9f;
    for (int i = 0; i < count; ++i) {
        float t = boxes[i].topAt(p);
        if (t > top) top = t;
    }
    if (top == -1e9f) top = -100.0f; // упал за край карты
    return top;
}

Vec3 World::spawn() const {
    return Vec3(0, 2.5f, 0);
}

} // namespace stone