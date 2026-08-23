// Member function templates and method-bearing structs (FEASIBILITY #48,
// #49 — the former limitations 1c/1d): PCLPointCloud2 declares
// `template <typename T> T& at(...)`, which emitted a bare undefined `T`
// (free function templates and class templates already worked), and a
// struct whose only C++-ness is its METHODS stayed `cdef struct`, where
// Cython rejects a const-qualified method (`... nogil const`) — silently.
#pragma once

#include <cstddef>

namespace demo {

struct Blob {
    template <typename T> T& at(std::size_t i);
    template <typename T> const T& view(std::size_t i) const;
    int size() const;
};

struct Ops {
    int v;
    Ops operator+(const Ops& rhs) const;
};

struct Wrap {
    Wrap();
    template <typename U> Wrap(const U& other);
    int plain(int x);
};

}  // namespace demo
