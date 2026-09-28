// A sibling header, as PCL's real ones are: its types are declared HERE, so
// they never appear in the pxd generated for name_resolution.h and can only
// arrive through a cimport.
#pragma once
namespace other {
struct Widget { int id; };
struct Gadget { int id; };
}  // namespace other

