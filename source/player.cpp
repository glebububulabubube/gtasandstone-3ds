#include "player.hpp"
#include <3ds.h>
#include <math.h>

namespace stone {

static const float FRAME_DT   = 0.016f;
static const float GRAVITY    = -22.0f;
static const float JUMP_VEL   = 9.5f;
static const float MOVE_SPEED = 5.0f;
static const float RUN_SPEED  = 10.5f;

void Player::reset(const Vec3& p) {
    position = p;
    velocity = Vec3(0, 0, 0);
    onGround = false;
    forward = Vec3(0, 0, -1);
    moving = false;
    _animTime = 0.0f;
}

void Player::jump() {
    if (onGround) {
        velocity.y = JUMP_VEL;
        onGround = false;
        moving = false;
    }
}

void Player::update(u32 held, const World& world) {
    _animTime += FRAME_DT;
    float dx = 0.0f, dz = 0.0f;

    circlePosition cpos;
    hidCircleRead(&cpos);
    float stickX = cpos.dx / 156.0f;
    float stickY = cpos.dy / 156.0f;

    if (stickX > 0.15f || stickX < -0.15f || stickY > 0.15f || stickY < -0.15f) {
        dx = stickX;
        dz = -stickY; // вперёд = минус по z
    } else {
        if (held & KEY_UP)    dz -= 1.0f;
        if (held & KEY_DOWN)  dz += 1.0f;
        if (held & KEY_LEFT)  dx -= 1.0f;
        if (held & KEY_RIGHT) dx += 1.0f;
    }

    if (dx >  1.0f) dx =  1.0f;
    if (dx < -1.0f) dx = -1.0f;
    if (dz >  1.0f) dz =  1.0f;
    if (dz < -1.0f) dz = -1.0f;

    float len2 = dx*dx + dz*dz;
    if (len2 > 1.0f) {
        float inv = 1.0f / sqrtf(len2);
        dx *= inv;
        dz *= inv;
    }

    float speed = (accel > 1.5f) ? RUN_SPEED : MOVE_SPEED;
    velocity.x = dx * speed;
    velocity.z = dz * speed;

    moving = (dx != 0.0f || dz != 0.0f);

    velocity.y += GRAVITY * FRAME_DT;

    position.x += velocity.x * FRAME_DT;
    position.y += velocity.y * FRAME_DT;
    position.z += velocity.z * FRAME_DT;

    if (dx != 0.0f || dz != 0.0f) forward = Vec3(dx, 0.0f, dz);

    collide(world);
}

void Player::collide(const World& world) {
    // 1) Стены: выталкиваем по оси наименьшего проникновения.
    //    Боксы не выше STEP_HEIGHT над ногами считаем ступеньками.
    for (int i = 0; i < world.count; ++i) {
        const Box& b = world.boxes[i];

        if (b.max.y - position.y <= STEP_HEIGHT) continue; // ступенька, не стена
        if (position.y + height <= b.min.y)      continue; // бокс выше головы

        float pminx = position.x - halfW, pmaxx = position.x + halfW;
        float pminz = position.z - halfW, pmaxz = position.z + halfW;

        if (pmaxx <= b.min.x || pminx >= b.max.x) continue;
        if (pmaxz <= b.min.z || pminz >= b.max.z) continue;

        float pushNegX = pmaxx - b.min.x;
        float pushPosX = b.max.x - pminx;
        float pushNegZ = pmaxz - b.min.z;
        float pushPosZ = b.max.z - pminz;

        float best = pushNegX;
        int   axis = 0;
        float dir  = -1.0f;

        if (pushPosX < best) { best = pushPosX; dir =  1.0f; }
        if (pushNegZ < best) { best = pushNegZ; axis = 1; dir = -1.0f; }
        if (pushPosZ < best) { best = pushPosZ; axis = 1; dir =  1.0f; }

        if (axis == 0) position.x += dir * best;
        else           position.z += dir * best;
    }

    // 2) Земля
    float groundY = world.groundAt(position);
    if (position.y <= groundY) {
        position.y = groundY;
        if (velocity.y < 0.0f) velocity.y = 0.0f;
        onGround = true;
    } else {
        onGround = false;
    }

    // 3) Граница карты
    Vec3 rel = position - world.center;
    rel.y = 0.0f;
    float dist = sqrtf(rel.x*rel.x + rel.z*rel.z);
    if (dist > world.radius) {
        float k = world.radius / dist;
        position.x = world.center.x + rel.x * k;
        position.z = world.center.z + rel.z * k;
    }
}

} // namespace stone
