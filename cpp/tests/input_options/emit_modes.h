// Fixture for --extern_from / --except_plus / --no_nogil (the emitter-mode
// flags that let the C++ tool stand in for the Python implementation in
// python-pcl_skbuild's pxdgen pipeline).
//
// Self-contained on purpose: it covers every shape the `except +` placement
// rules have to distinguish.
//   * const methods       -> `except + nogil const` (the ONLY order cython
//                            accepts; with --no_nogil the const is dropped
//                            because nothing can separate the two)
//   * `T&` returns        -> exempt (except + would return a reference to a
//                            by-value temporary)
//   * `const T&` returns  -> NOT exempt
//   * constructors        -> take it
//   * operators, member function templates, operator() -> parsed correctly
#pragma once

#include <cstddef>

namespace demo {

struct Value
{
    int v;
};

class Store
{
public:
    Store();
    Store(std::size_t n);

    // plain, mutating
    void clear();
    void reserve(std::size_t n);

    // const observers
    std::size_t size() const;
    bool empty() const;

    // mutable reference returns: must NOT gain `except +`
    Value& at(std::size_t i);
    Value& front();
    Value& operator[](std::size_t i);

    // a const reference return is by-value-safe, so it DOES gain `except +`
    const Value& peek() const;

    // value-returning operator
    Store operator+(const Store& rhs) const;

    // callable object: `operator()` must not be mistaken for the parameter list
    int operator()(int a);

    // member function template
    template <typename T>
    T& get(std::size_t i);

private:
    std::size_t count_;
};

// free function
std::size_t total(const Store& s);

}  // namespace demo
