// templates.h - exercise template class / function emission (PCL/draco-like).
#pragma once

#include <stdint.h>

namespace geo {

// single type parameter
template <typename T>
class Vector3 {
 public:
  Vector3();
  Vector3(T x, T y, T z);
  T dot(const Vector3<T>& other) const;
  T x() const;
  T y() const;
  T z() const;

 private:
  T data_[3];
};

// two type parameters
template <typename T, int N>
class Array {
 public:
  Array();
  T& at(int i);
  int size() const;
};

// free function template
template <typename T>
T clamp(T v, T lo, T hi);

}  // namespace geo
