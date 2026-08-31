// Fixture for the name/spelling rules that decide whether generated pxd is
// usable at all (#56). Self-contained: `other` stands in for a sibling
// header whose names arrive via --extra_cimport, exactly as PCL's compat
// shims name pcl:: types from inside namespace pclcompat.
#pragma once

#include <cstddef>

#include "name_resolution_other.h"

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

// C++ default arguments cannot be spelled in a pxd (`=*` is rejected inside
// `cdef extern`), so they expand into one declaration per callable arity.
int saveWidget(const other::Widget& w, bool binary = false,
               std::size_t precision = 8);

}  // namespace shim
