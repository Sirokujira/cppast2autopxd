// Fixture for the name/spelling rules that decide whether generated pxd is
// usable at all (#56). Self-contained: `other` stands in for a sibling
// header whose names arrive via --extra_cimport, exactly as PCL's compat
// shims name pcl:: types from inside namespace pclcompat.
#pragma once

#include <cstddef>
#include <limits>
#include <memory>
#include <vector>

#include "name_resolution_other.h"

// Declared HERE, so they appear in the generated pxd and must count as KNOWN
// names even though they are not classes: a ctypedef / using / union binds a
// usable name just as a struct does.
namespace local {
typedef int Index;
using Scalar = float;
union Cell { int i; float f; };
}  // namespace local

namespace shim {

// A name that merely CONTAINS "const" must survive intact. Splitting on the
// substring turned `reconstruct` into `re ruct`, `constant_value` into
// `ant_value` and `const_pointer` into `const _pointer`.
struct Mesh
{
    void reconstruct(int* out);
    int constant_value() const;
    const int* const_pointer() const;
};

// Qualified names from ANOTHER namespace: resolvable when the tail is
// cimported (Widget), reported as a skip when it is not (Gadget).
void useWidget(const other::Widget& w);
void useGadget(const other::Gadget& g);

// `in` is a legal C++ parameter name and a Python keyword.
void copyInto(const other::Widget& in, other::Widget& out);

// Locally declared non-class names, referenced qualified.
void useIndex(local::Index i);
void useScalar(local::Scalar s);
void useCell(const local::Cell& c);

// C++ default arguments cannot be spelled in a pxd (`=*` is rejected inside
// `cdef extern`), so they expand into one declaration per callable arity.
int saveWidget(const other::Widget& w, bool binary = false,
               std::size_t precision = 8);

// A default value can be the ONLY place a `::` appears. Every parameter type
// here is expressible, so all three arities must be emitted — the default
// text is deleted before anything judges the line.
void setLimits(other::Widget& w, float lo = -std::numeric_limits<float>::max(),
               float hi = std::numeric_limits<float>::max());

// A function-pointer typedef must keep its parameter TYPES intact. Dropping
// the template brackets glued the argument onto the name
// (`shared_ptrother::Widget`), which the qualified-name pass then "resolved"
// to a silently WRONG type.
typedef void (*WidgetCb)(std::shared_ptr<other::Widget> w, void* user_data);

// A dependent name: no qualifier NAME precedes the `::` once `<...>` has
// become `[...]`, so resolving would glue `iterator` onto `vector[int]`.
// It must skip with a reason instead.
std::vector<int>::iterator firstOf(std::vector<int>& v);

// A data member named with a Python keyword is an "Empty declarator" to
// cython, exactly like a parameter.
struct Packet
{
    int in;
    float lambda;
    int ok;
};

}  // namespace shim
