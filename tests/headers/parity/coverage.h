// coverage.h - exercises a broad range of declaration kinds to drive the pxd
// generator toward full Cython-rule coverage. Self-contained (only <stdint.h>).
#pragma once

#include <stdint.h>

// --- global variables (extern) ---
extern int g_counter;
extern const double g_pi;

// --- C-style function pointer typedef ---
typedef int (*binary_op)(int, int);

// --- plain enum + scoped enum ---
enum Color { RED, GREEN = 5, BLUE };
enum class Mode : unsigned int { Fast, Slow = 10 };

// --- anonymous typedef enum (common C idiom) ---
typedef enum { LOW = -1, MID = 0, HIGH = 1 } Level;

namespace cov {

// --- POD struct with various member types ---
struct Vec2 {
  float x;
  float y;
};

// --- struct with a bitfield ---
struct Flags {
  unsigned int a : 1;
  unsigned int b : 3;
  unsigned int rest : 28;
};

// --- typedef struct {...} Name (anonymous) ---
typedef struct { double re; double im; } Complex;

// --- free functions ---
int add(int a, int b);
const char* name_of(int kind);
void apply(binary_op op, int a, int b);

// --- a class with ctor/dtor/methods/static ---
class Widget {
 public:
  Widget();
  explicit Widget(int id);
  ~Widget();

  int id() const;
  void set_id(int v);
  static Widget make(int id);

 private:
  int id_;
};

// --- inheritance ---
class Button : public Widget {
 public:
  Button();
  void click();
};

// --- function template ---
template <typename T>
T max_of(T a, T b);

// --- class template ---
template <typename T, int N>
class Array {
 public:
  T& at(int i);
  int size() const;
};

}  // namespace cov
