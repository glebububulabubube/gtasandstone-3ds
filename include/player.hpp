#pragma once
// Персонаж CJ (бокс-человечек): ходьба, бег, прыжок, гравитация, коллизии.

#include "engine.hpp"
#include "world.hpp"

namespace stone {

class Player {
public:
    Vec3 position;
    Vec3 velocity;
    float accel;       // множитель бега (1.0 ходьба, 2.2 бег)
    bool onGround;
    float halfW = 0.35f; // половина ширины тела
    float height = 1.7f; // рост

    Vec3 forward; // для удобства отрисовки

    Player() : position(0, 0, 0), velocity(0, 0, 0), accel(1.0f), onGround(false) {}
    ~Player() {}

    void reset(const Vec3& p);
    void jump();
    void update(u32 held, const World& world);

    // коллизия: спроецировать позицию на землю мира
    void collide(const World& world);

    // AABB персонажа
    Vec3 center() const { return position + Vec3(0, height*0.5f, 0); }
};

} // namespace stone