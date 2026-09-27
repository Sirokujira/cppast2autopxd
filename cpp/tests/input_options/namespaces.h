// Fixture for --namespace (#58): the exact-match filter that lets a config
// entry say which namespace a pxd is FOR, the way python-pcl_skbuild's
// `namespaces = ["pcl::io"]` does. Same semantics as the Python filter:
//   * "a"     keeps `namespace "a"` blocks ONLY -- not the nested `a::b`
//   * "a::b"  keeps the nested block
//   * ""      keeps the file-level (global) block
//   * no flag keeps everything, as before
#pragma once

#include <stdint.h>
#include <vector>

// file-level declarations: kept only when "" is among the namespaces. The
// typedef sits right after <stdint.h>, whose EIGHT-line cimport expansion is
// one entity with continuation lines at column 0 -- the shape that once
// re-enabled `keep` inside this dropped block and leaked the typedef,
// headerless, into an `a`-only pxd.
typedef uint32_t index_t;
int global_count();

namespace a {
struct Outer { int v; };
int outer_fn(const Outer& o);

namespace b {
struct Inner { int w; };
int inner_fn(const Inner& i);
}  // namespace b
}  // namespace a

namespace c {
struct Other { int x; };
int other_fn(const Other& o);
// A std type used ONLY here: the `vector` cimport the emitter interleaves
// with an earlier block must survive when that block is dropped and this
// one is kept -- an import line is never filtered out with a block.
std::vector<int> other_ids(const Other& o);
}  // namespace c
