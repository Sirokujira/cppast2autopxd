// mathlib.h - small self-contained C++ library used to demonstrate the full
// pipeline: this header is parsed by cppast_autopxd to produce a .pxd, which a
// Cython .pyx then wraps into an importable Python extension module.
#pragma once

#include <stdint.h>

namespace mathlib {

// free functions
int add(int a, int b);
double hypot2(double x, double y);

// a small value type with methods
class Accumulator {
 public:
  Accumulator();
  explicit Accumulator(double initial);

  void add(double v);
  double total() const;
  int64_t count() const;

 private:
  double total_;
  int64_t count_;
};

}  // namespace mathlib
