#pragma once
// Персонаж CJ (бокс-человечек): ходьба, бег, прыжок, гравитация, коллизии.

#include <3ds.h>
#include "engine.hpp"
#include "world.hpp"

namespace stone {

class Player {
public:
    Vec3 position;     // position.y = уровень ног
    Vec3 velocity;
    float accel;       // множитель скорости (1.0 ходьба, 2.5 бег)
    bool onGround;
    float halfW  = 0.35f; // половина ширины тела
    float height = 1.8f;  // рост

    Vec3 forward; // направление движения

    Player() : position(0, 0, 0), velocity(0, 0, 0), accel(1.0f), onGround(false),
               forward(0, 0, 1) {}

    void reset(const Vec3& p);
    void jump();
    void update(u32 held, const World& world);

    // стены + земля + границы карты
    void collide(const World& world);

    Vec3 center() const { return position + Vec3(0, height*0.5f, 0); }
};

} // namespace stone
