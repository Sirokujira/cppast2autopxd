// vectord.h - self-contained header modeled on draco's core/vector_d.h, to
// validate template emission against real-world patterns (class-keyword
// template params, typedefs, operators, methods returning the template type).
#pragma once

#include <stdint.h>

namespace draco {

template <class ScalarT, int dimension_t>
class VectorD {
 public:
  typedef ScalarT Scalar;
  typedef VectorD<ScalarT, dimension_t> Self;

  VectorD();
  VectorD(const Scalar& c0, const Scalar& c1);

  Scalar& operator[](int i);
  const Scalar& operator[](int i) const;

  Self operator-() const;
  Self operator+(const Self& o) const;

  Scalar Dot(const Self& o) const;
  Scalar SquaredNorm() const;
  int dimension() const;

 private:
  Scalar v_[dimension_t];
};

}  // namespace draco
