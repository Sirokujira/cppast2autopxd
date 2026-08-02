// Regression header for review-confirmed edge cases:
// extern "C" blocks, named unions (top-level, nested, and as the type of a
// named field), anonymous enums, nested enum + typedef ordering, array
// parameters that must not fabricate overloads, genuine defaults that must.
#pragma once

#include <cstddef>

extern "C" {
    struct CPoint {
        double cx;
        double cy;
    };

    int c_distance(const CPoint* a, const CPoint* b);
}

namespace edge {

union Blob {
    float f;
    int i;
    unsigned char bytes[4];
};

enum {
    ANON_FIRST,
    ANON_SECOND
};

struct Holder {
    Blob blob;          // field of a named union type
    union {             // truly anonymous union: members flatten
        float fast;
        double precise;
    };
    union {             // unnamed union typing a NAMED field: must NOT flatten
        float u;
        float v;
    } tex;
};

class Machine {
public:
    enum Mode {
        IDLE,
        RUNNING
    };
    typedef Mode mode_t;    // typedef referencing the nested enum
    enum {
        LIMIT = 64
    };
    union Slot {
        int as_int;
        float as_float;
    };

    Machine();

    mode_t mode() const;
    void configure(const float matrix[16]);     // array param: ONE signature
    void tune(int level, double gain = 1.5);    // real default: TWO overloads

    Slot scratch;
    Mode current;
};

}  // namespace edge

namespace outer {
struct First {
    int a;
};
}  // namespace outer

namespace other {
struct Middle {
    int b;
};
}  // namespace other

namespace outer {
// Reopened namespace referencing a type from the interleaved one: blocks
// must stay in source order or this creates a forward reference.
struct Second {
    other::Middle payload;
};
}  // namespace outer
