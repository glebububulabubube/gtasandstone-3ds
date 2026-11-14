#pragma once
// Скелетная математика и процедурные анимации для модели CJ (.gsmod).
// Матрицы 3x4 хранятся строками: r0, r1, r2 — поворот 3x3, t = m[9..11].
// Соглашение: world[i] = world[parent] * local[i]; точка p' = M * p.

#include "gsmod.hpp"

namespace stone {

struct Mat34 {
    float m[12];
};

void mat34Identity(Mat34& out);
void mat34Mul(Mat34& out, const Mat34& a, const Mat34& b);
// out = R(angle,axis) * in (поворот в локальной системе: вокруг origin матрицы)
void mat34RotX(Mat34& out, const Mat34& in, float deg);
void mat34RotY(Mat34& out, const Mat34& in, float deg);
void mat34RotZ(Mat34& out, const Mat34& in, float deg);
// сместиться на position (перевести мировую матрицу в точку p)
void mat34Translate(Mat34& out, const Mat34& in, float x, float y, float z);

enum AnimType {
    ANIM_IDLE = 0,
    ANIM_WALK,
    ANIM_RUN,
    ANIM_JUMP,
};

// Заполняет мировые матрицы костей процедурной анимацией.
// time — секунды (для циклов), phase — 0..1 (фаза, можно из скорости).
void animateSkeleton(GsModel& m, AnimType anim, float time, float phase, Mat34* world);

// Скиннинг вершины: на входе базовые позиция/норма(бина), на выходе pos/norm в мировых координатах.
// uses model->bones invmat.
void skinVertex(GsModel& m, const Mat34* world, int boneA, float wA, int boneB, float wB,
                const float* inPos, float* outPos);

// индекс кости по имени (-1 если нет)
int boneIndex(const GsModel& m, const char* name);

} // namespace stone