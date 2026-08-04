// simple.h - synthetic C/C++ header to validate pxd generation end-to-end.
#pragma once

#include <stdint.h>

namespace demo {

// plain C-like enum
enum Color {
  RED = 0,
  GREEN = 1,
  BLUE = 2,
};

// scoped enum
enum class Mode : int {
  Fast,
  Slow,
};

// POD struct
struct Point {
  float x;
  float y;
  int32_t id;
};

// free functions
int add(int a, int b);
double distance(const Point& a, const Point& b);

// a class with methods
class Shape {
 public:
  Shape();
  explicit Shape(double area);
  virtual ~Shape();

  double area() const;
  void set_area(double a);
  virtual int sides() const;

 private:
  double area_;
};

// function pointer typedef / callback
typedef int (*compare_fn)(const void* a, const void* b);

}  // namespace demo
