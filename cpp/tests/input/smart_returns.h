// Smart pointers BY VALUE in signatures — the shapes the token-level
// template filter used to destroy (FEASIBILITY #39): a method or
// constructor naming a concrete template argument emitted empty brackets
// (`shared_ptr[] build()`). Free functions were never affected; PCL hits
// the method shape constantly (`makeShared()`, `getInputCloud()`).
#pragma once

#include <memory>
#include <vector>

namespace demo {

struct Res {
    int v;
};

class Factory {
 public:
    Factory();
    explicit Factory(std::shared_ptr<Res> seed);
    std::shared_ptr<Res> build() const;
    std::shared_ptr<const Res> view() const;
    std::vector<int> history() const;
    void absorb(std::shared_ptr<Res> extra);
    bool operator<(const Factory& other) const;
    bool operator<=(const Factory& other) const;
    bool operator>=(const Factory& other) const;
    bool operator==(const Factory& other) const;
    Factory& operator=(const Factory& other);
};

template <typename T>
class Pool {
 public:
    std::shared_ptr<T> acquire();
};

}  // namespace demo
