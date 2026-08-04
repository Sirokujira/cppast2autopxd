// mathlib.cpp - implementation of mathlib.h (compiled into the extension).
#include "mathlib.h"

#include <cmath>

namespace mathlib {

int add(int a, int b) { return a + b; }

double hypot2(double x, double y) { return std::sqrt(x * x + y * y); }

Accumulator::Accumulator() : total_(0.0), count_(0) {}

Accumulator::Accumulator(double initial) : total_(initial), count_(1) {}

void Accumulator::add(double v) {
  total_ += v;
  ++count_;
}

double Accumulator::total() const { return total_; }

int64_t Accumulator::count() const { return count_; }

}  // namespace mathlib
