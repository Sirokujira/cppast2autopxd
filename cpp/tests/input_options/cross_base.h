// Generated PLAINLY in the options block; cross_ref.h then cimports Vec3
// from the resulting pxd via --extra_cimport.
#pragma once
namespace xh {
struct Vec3 {
    float x;
    float y;
    float z;
};

// A second exported name, so the cimport cross_ref.h needs is the
// MULTI-SYMBOL form `cimport Vec3, Vec3Alias` -- the shape that a
// comma-splitting option parser silently breaks in two.
typedef Vec3 Vec3Alias;
}
