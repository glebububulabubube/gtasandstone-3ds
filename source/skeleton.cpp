#include "skeleton.hpp"
#include <math.h>
#include <string.h>

namespace stone {

static const float PI = 3.14159265f;
static inline float rad(float d) { return d * PI / 180.0f; }

void mat34Identity(Mat34& out) {
    float m[12] = {1,0,0, 0,1,0, 0,0,1, 0,0,0};
    memcpy(out.m, m, sizeof(m));
}

void mat34Mul(Mat34& out, const Mat34& a, const Mat34& b) {
    // out = a * b (строки: поворот a[3x3], t=a.t; b работает в системе a)
    float r[9], t[3];
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            r[i*3+j] = a.m[i*3+0]*b.m[0*3+j] + a.m[i*3+1]*b.m[1*3+j] + a.m[i*3+2]*b.m[2*3+j];
        }
        t[i] = a.m[9+i] + a.m[i*3+0]*b.m[9+0] + a.m[i*3+1]*b.m[9+1] + a.m[i*3+2]*b.m[9+2];
    }
    memcpy(out.m, r, 36);
    out.m[9] = t[0]; out.m[10] = t[1]; out.m[11] = t[2];
}

static void rotateAxis(Mat34& out, const Mat34& in, float rad, int ax) {
    float c = cosf(rad), s = sinf(rad);
    Mat34 R; mat34Identity(R);
    if (ax == 0) {
        R.m[4] = c; R.m[5] = s; R.m[7] = -s; R.m[8] = c;
    } else if (ax == 1) {
        R.m[0] = c; R.m[2] = -s; R.m[6] = s; R.m[8] = c;
    } else {
        R.m[0] = c; R.m[1] = s; R.m[3] = -s; R.m[4] = c;
    }
    mat34Mul(out, in, R); // вращение в локальных координатах (после in)
}

void mat34RotX(Mat34& out, const Mat34& in, float deg) { rotateAxis(out, in, rad(deg), 0); }
void mat34RotY(Mat34& out, const Mat34& in, float deg) { rotateAxis(out, in, rad(deg), 1); }
void mat34RotZ(Mat34& out, const Mat34& in, float deg) { rotateAxis(out, in, rad(deg), 2); }

void mat34Translate(Mat34& out, const Mat34& in, float x, float y, float z) {
    Mat34 T; mat34Identity(T);
    T.m[9] = x; T.m[10] = y; T.m[11] = z;
    mat34Mul(out, in, T);
}

int boneIndex(const GsModel& m, const char* name) {
    for (uint32_t i = 0; i < m.numBones; ++i) {
        char b[33];
        memcpy(b, m.bones[i].name, 32); b[32] = 0;
        // обрежем ведущие/хвостовые пробелы
        char* s = b;
        while (*s == ' ') s++;
        char* e = b + strlen(b);
        while (e > s && (e[-1] == ' ')) *--e = 0;
        if (strncmp(s, name, 32) == 0) return (int)i;
    }
    return -1;
}

static void evalPose(GsModel& m, AnimType anim, float time, float phase, Mat34* local) {
    // базовая поза = локальные матрицы из файла
    for (uint32_t i = 0; i < m.numBones; ++i) {
        Mat34& l = local[i];
        memcpy(l.m, m.bones[i].local, 48);
    }

    // индексы костей по именам
    int pelvis = boneIndex(m, "Pelvis");
    int spine1 = boneIndex(m, "Spine 1");
    int spine2 = boneIndex(m, "Spine 2");
    int neck   = boneIndex(m, "Neck");
    int head   = boneIndex(m, "Head");
    int lThigh = boneIndex(m, "L Thigh");
    int rThigh = boneIndex(m, "R Thigh");
    int lCalf  = boneIndex(m, "L Calf");
    int rCalf  = boneIndex(m, "R Calf");
    int lFoot  = boneIndex(m, "L Foot");
    int rFoot  = boneIndex(m, "R Foot");
    int lToe   = boneIndex(m, "L Toe0");
    int rToe   = boneIndex(m, "R Toe0");
    int lUpArm = boneIndex(m, "L UpperArm");
    int rUpArm = boneIndex(m, "R UpperArm");
    int lFrm   = boneIndex(m, "L ForeArm");
    int rFrm   = boneIndex(m, "R ForeArm");
    int lHand  = boneIndex(m, "L Hand");
    int rHand  = boneIndex(m, "R Hand");

    float t = time;
    bool ground = (anim != ANIM_JUMP);

    if (anim == ANIM_WALK || anim == ANIM_RUN) {
        float spd = (anim == ANIM_RUN) ? 2.0f : 1.0f;
        float cyc = t * 3.0f * spd;
        float swing = sinf(cyc);
        float swingP = sinf(cyc + PI);
        float bend  = (anim == ANIM_RUN) ? 1.1f  : 0.7f;

        // ноги: махи вперёд/назад (ось Z в системе бедра)
        if (lThigh >= 0) mat34RotZ(local[lThigh], local[lThigh], swing * 40.0f * bend);
        if (rThigh >= 0) mat34RotZ(local[rThigh], local[rThigh], swingP * 40.0f * bend);
        // сгиб колена
        if (lCalf >= 0)  mat34RotZ(local[lCalf],  local[lCalf],  fmaxf(0, -swing) * 55.0f * bend);
        if (rCalf >= 0)  mat34RotZ(local[rCalf],  local[rCalf],  fmaxf(0, -swingP) * 55.0f * bend);
        // стопы
        if (lFoot >= 0)  mat34RotX(local[lFoot],  local[lFoot],  -fmaxf(0, swing) * 12.0f);
        if (rFoot >= 0)  mat34RotX(local[rFoot],  local[rFoot],  -fmaxf(0, swingP) * 12.0f);

        // руки: встречные махи
        if (lUpArm >= 0) mat34RotZ(local[lUpArm], local[lUpArm], -swingP * 25.0f * bend);
        if (rUpArm >= 0) mat34RotZ(local[rUpArm], local[rUpArm], -swing * 25.0f * bend);
        if (lFrm >= 0)   mat34RotZ(local[lFrm],   local[lFrm],   swingP * 20.0f);
        if (rFrm >= 0)   mat34RotZ(local[rFrm],   local[rFrm],   swing * 20.0f);

        // лёгкое покачивание корпуса (для бега — сильнее)
        float sway = (anim == ANIM_RUN) ? 6.0f : 3.0f;
        if (spine1 >= 0) mat34RotY(local[spine1], local[spine1], sinf(cyc) * sway);

    } else if (anim == ANIM_JUMP) {
        // прыжок: ноги поджаты, руки вверх-назад
        if (lThigh >= 0) mat34RotZ(local[lThigh], local[lThigh], 35.0f);
        if (rThigh >= 0) mat34RotZ(local[rThigh], local[rThigh], 35.0f);
        if (lCalf >= 0)  mat34RotZ(local[lCalf],  local[lCalf],  65.0f);
        if (rCalf >= 0)  mat34RotZ(local[rCalf],  local[rCalf],  65.0f);
        if (lUpArm >= 0) mat34RotZ(local[lUpArm], local[lUpArm], -120.0f);
        if (rUpArm >= 0) mat34RotZ(local[rUpArm], local[rUpArm], -120.0f);
        if (lFrm >= 0)   mat34RotZ(local[lFrm],   local[lFrm],  30.0f);
        if (rFrm >= 0)   mat34RotZ(local[rFrm],   local[rFrm],  30.0f);
    } else {
        // idle: почти неподвижен, лёгкое дыхание
        if (spine1 >= 0) mat34RotX(local[spine1], local[spine1], sinf(t * 1.8f) * 1.2f);
        if (head   >= 0) mat34RotY(local[head],   local[head],   sinf(t * 0.7f) * 4.0f);
    }
    (void)ground; (void)pelvis; (void)spine2; (void)neck; (void)lToe; (void)rToe;
    (void)lHand; (void)rHand;
}

void animateSkeleton(GsModel& m, AnimType anim, float time, float phase, Mat34* world) {
    (void)phase;  // зарезервировано
    Mat34 local[64];
    if (m.numBones > 64) return;
    evalPose(m, anim, time, phase, local);

    // world[i] = world[parent] * local[i]; корень — чисто identity (позиция задаётся локально при рендере)
    for (uint32_t i = 0; i < m.numBones; ++i) {
        int p = m.bones[i].parent;
        if (p < 0) {
            mat34Identity(world[i]);
            mat34Mul(world[i], world[i], local[i]);
        } else {
            mat34Mul(world[i], world[p], local[i]);
        }
    }
}

void skinVertex(GsModel& m, const Mat34* world, int boneA, float wA, int boneB, float wB,
                const float* inPos, float* outPos) {
    // позиция = sum over bones (world[b] * invmat[b] * p)
    // см. стандарт: p' = sum w_b * (World_b * InvModel_b) * p
    float x = inPos[0], y = inPos[1], z = inPos[2];
    outPos[0] = outPos[1] = outPos[2] = 0.0f;
    int bones[2] = { boneA, boneB };
    float ws[2] = { wA, wB };
    if (wA + wB <= 0.0f) { bones[0] = 0; ws[0] = 1.0f; bones[1] = -1; ws[1] = 0.0f; }
    for (int k = 0; k < 2; ++k) {
        if (bones[k] < 0 || bones[k] >= (int)m.numBones || ws[k] <= 0.0f) continue;
        const GsBone& b = m.bones[bones[k]];
        // invmat * p
        float inv[3] = {
            b.invmat[0]*x + b.invmat[1]*y + b.invmat[2]*z + b.invmat[9],
            b.invmat[3]*x + b.invmat[4]*y + b.invmat[5]*z + b.invmat[10],
            b.invmat[6]*x + b.invmat[7]*y + b.invmat[8]*z + b.invmat[11],
        };
        const Mat34& W = world[bones[k]];
        outPos[0] += ws[k] * (W.m[0]*inv[0] + W.m[1]*inv[1] + W.m[2]*inv[2] + W.m[9]);
        outPos[1] += ws[k] * (W.m[3]*inv[0] + W.m[4]*inv[1] + W.m[5]*inv[2] + W.m[10]);
        outPos[2] += ws[k] * (W.m[6]*inv[0] + W.m[7]*inv[1] + W.m[8]*inv[2] + W.m[11]);
    }
}

} // namespace stone
