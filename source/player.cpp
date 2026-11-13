#include "player.hpp"
#include <3ds.h>

namespace stone {

static const float GRAVITY = -22.0f;
static const float JUMP_VEL = 8.5f;
static const float MOVE_SPEED = 5.0f;   // базовая скорость ходьбы
static const float RUN_SPEED = 10.5f;   // скорость бега (R зажат)

void Player::reset(const Vec3& p) {
    position = p;
    velocity = Vec3(0, 0, 0);
    onGround = false;
    forward = Vec3(0, 0, 1);
}

void Player::jump() {
    if (onGround) {
        velocity.y = JUMP_VEL;
        onGround = false;
    }
}

void Player::update(u32 held, const World& world) {
    // Направление движения по стику / крестовине
    float dx = 0, dz = 0;
    circlePosition cpos;
    hidCircleRead(&cpos);
    float stickX = cpos.dx / 156.0f;
    float stickY = cpos.dy / 156.0f;
    if (stickX != 0 || stickY != 0) {
        dx = stickX;
        dz = -stickY; // вперёд = минус по z
    } else {
        if (held & KEY_UP)    dz -= 1;
        if (held & KEY_DOWN)  dz += 1;
        if (held & KEY_LEFT)  dx -= 1;
        if (held & KEY_RIGHT) dx += 1;
    }

    // Нормализуем горизонтальное направление
    float len = dx*dx + dz*dz;
    if (len > 1.0f) {
        float inv = 1.0f / __builtin_sqrtf(len);
        dx *= inv; dz *= inv;
    }

    // Бег
    float speed = accel > 1.5f ? RUN_SPEED : MOVE_SPEED;
    velocity.x = dx * speed;
    velocity.z = dz * speed;

    // Гравитация
    velocity.y += GRAVITY * 0.016f;

    // Интеграция
    position = position + velocity * 0.016f;

    // Запоминаем направление взгляда для отрисовки
    if (dx != 0 || dz != 0) {
        forward = Vec3(dx, 0, dz);
    }

    // Коллизии с миром (земля + стены)
    collide(world);
}

void Player::collide(const World& world) {
    // Пол персонажа = bottom
    float feet = position.y - halfW;
    // Стены: ограничиваем по XZ чтобы персонаж не провалился в бокс
    // (простая версия: держим центр в области мира)

    float groundY = world.groundAt(position);
    if (feet < groundY) {
        position.y = groundY + halfW;
        if (velocity.y < 0) velocity.y = 0;
        onGround = true;
    } else {
        onGround = false;
    }

    // Простая граница карты: радиус мира
    float r = world.radius;
    Vec3 rel = position - world.center;
    rel.y = 0;
    float dist = __builtin_sqrtf(rel.x*rel.x + rel.z*rel.z);
    if (dist > r) {
        rel.x *= r / dist;
        rel.z *= r / dist;
        position.x = world.center.x + rel.x;
        position.z = world.center.z + rel.z;
    }
}

} // namespace stone