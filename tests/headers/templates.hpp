// Template edge cases: defaulted template type parameters, explicit full
// specializations, partial specializations, static data members.
#pragma once

#include <cstddef>

namespace tpl {

template <typename T>
struct MyAlloc {
    T* allocate(std::size_t n);
};

template <typename T, typename Alloc = MyAlloc<T>>
class Box {
public:
    Box();
    void put(const T& value);
    T& get();
    static int instances;   // static data member: warn-skipped
};

// Explicit full specialization: must NOT emit a duplicate plain class.
template <>
class Box<int, MyAlloc<int>> {
public:
    Box();
    void put(const int& value);
    int& get();
};

// Partial specialization: must NOT emit a duplicate either.
template <typename T, typename Alloc>
class Box<T*, Alloc> {
public:
    Box();
    void put(T* value);
    T*& get();
};

}  // namespace tpl
