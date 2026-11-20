#pragma once
// gtasandstone — базовые типы и математика движка (float, простая 3D-математика)

namespace stone {

struct Vec3 {
    float x, y, z;
    Vec3() : x(0), y(0), z(0) {}
    Vec3(float x, float y, float z) : x(x), y(y), z(z) {}
};

inline Vec3 operator+(const Vec3& a, const Vec3& b) { return Vec3(a.x+b.x, a.y+b.y, a.z+b.z); }
inline Vec3 operator-(const Vec3& a, const Vec3& b) { return Vec3(a.x-b.x, a.y-b.y, a.z-b.z); }
inline Vec3 operator*(const Vec3& a, float s)      { return Vec3(a.x*s, a.y*s, a.z*s); }
inline Vec3 operator*(float s, const Vec3& a)      { return Vec3(a.x*s, a.y*s, a.z*s); }

struct Box {
    Vec3 min;
    Vec3 max;
    Box() {}
    Box(const Vec3& mn, const Vec3& mx) : min(mn), max(mx) {}
    inline bool containsXZ(const Vec3& p) const {
        return p.x >= min.x && p.x <= max.x && p.z >= min.z && p.z <= max.z;
    }
    inline float topAt(const Vec3& p) const {
        if (!containsXZ(p)) return -1e9f;
        return max.y;
    }
};

struct Camera {
    Vec3 pos;   // позиция
    Vec3 look;  // точка, куда смотрим
    float yaw;
};

inline float clampf(float v, float lo, float hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

} // namespace stone