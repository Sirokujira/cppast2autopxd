// Simplified stand-in mirroring the API surface of pcl/point_types.h.
// Exercises the anonymous union/struct flattening that real PCL point
// types rely on (SSE-padded unions).
#pragma once

#include <cstdint>

namespace pcl {

struct PointXYZ {
    union {
        struct {
            float x;
            float y;
            float z;
        };
        float data[4];
    };
};

struct PointXYZI {
    union {
        struct {
            float x;
            float y;
            float z;
        };
        float data[4];
    };
    union {
        struct {
            float intensity;
        };
        float data_c[4];
    };
};

struct PointXYZRGB {
    union {
        struct {
            float x;
            float y;
            float z;
        };
        float data[4];
    };
    union {
        union {
            struct {
                std::uint8_t b;
                std::uint8_t g;
                std::uint8_t r;
                std::uint8_t a;
            };
            float rgb;
        };
        std::uint32_t rgba;
    };
};

struct Normal {
    union {
        struct {
            float normal_x;
            float normal_y;
            float normal_z;
        };
        float data_n[4];
    };
    union {
        struct {
            float curvature;
        };
        float data_c[4];
    };
};

}  // namespace pcl
