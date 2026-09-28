// Fixture for nested types inside a class (#62). Every block header below
// the extern-block level drops `cdef`; a struct holding a nested type
// promotes to cppclass (a `cdef struct` body admits fields only); a scoped
// enum keeps its `class`; and a nested type must leave the ENCLOSING
// class's access tracking alone -- K's private members leaked after
// `struct In` when kind and access were single flags.
#pragma once

#include <vector>

namespace demo {
enum class Top { P, Q };

class K {
public:
    struct In { int q; double w; };
    int after_struct() const;
private:
    int hidden();          // after a nested struct: used to leak
    int hidden_field;
public:
    enum Mode { A, B };
    enum class Kind { X, Y };
    class Inner {
        int secret();
    public:
        Inner();
        int shown() const;
    };
    int after_inner();     // Inner ended in `public:`; K is still public
    K();
    In get() const;
    void set(const In& in_);
    Mode mode() const;
    Kind kind() const;
    std::vector<In> all() const;
private:
    int hidden2();
};

struct S {
    struct Nested { int n; };
    Nested nested;
    int count;
};

template <typename T>
class Box {
public:
    struct Item { T value; };
    Item first() const;
};
}  // namespace demo
