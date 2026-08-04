// Mirror header: self-contained stand-in reproducing the API surface of
// <pcl/point_types.h> for the point types wrapped so far.
//
// Why a mirror and not the real header?  pxd generation must run on machines
// without PCL/Eigen installed (CI, sdist builds), and the generated pxd only
// needs *names and types* — the real memory layout always comes from the
// actual PCL headers at C++ compile time, because the generated pxd says
// `cdef extern from "pcl/point_types.h"`.
//
// Keep this file in sync with the PCL API you wrap.  When a field or type
// is missing here, add it and re-run:  python pxdgen/generate.py
#pragma once
// (committed gating fixture: mirror of the python-pcl_skbuild header)

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

struct PointXYZRGBA {
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

struct PointNormal {
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
