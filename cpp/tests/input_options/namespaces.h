// Fixture for --namespace (#58): the exact-match filter that lets a config
// entry say which namespace a pxd is FOR, the way python-pcl_skbuild's
// `namespaces = ["pcl::io"]` does. Same semantics as the Python filter:
//   * "a"     keeps `namespace "a"` blocks ONLY -- not the nested `a::b`
//   * "a::b"  keeps the nested block
//   * ""      keeps the file-level (global) block
//   * no flag keeps everything, as before
#pragma once

#include <vector>

// file-level declaration: kept only when "" is among the namespaces
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
