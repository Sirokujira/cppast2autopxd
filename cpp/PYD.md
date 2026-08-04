# `.pyd` support — what it means and how this repo handles it

## TL;DR

A `.pyd` is **not something generated from C/C++ source** — it is the *compiled*
Python extension module on **Windows** (a specially-named DLL). It is the exact
counterpart of a `.so` on macOS/Linux. So "pyd support" is not a generator
feature; it is a property of the **build step** that turns the generated `.pxd`
+ a `.pyx` wrapper into a binary module.

The pipeline is:

```
C/C++ header ──cppast_autopxd──▶ .pxd ──cimport──▶ .pyx ──Cython+compiler──▶  .so   (macOS/Linux)
                                                                              .pyd  (Windows)
```

The same `setup.py` / `pyproject.toml` used in [examples/](examples/) produces a
`.so` on macOS/Linux and a `.pyd` on Windows — Cython + setuptools pick the
platform-correct extension automatically. There is nothing extra to "generate".

## What we did for it

- The example and scaffolded `setup.py` files use a **portable C++ standard
  flag** (`/std:c++14` on MSVC/Windows, `-std=c++14` elsewhere), so the build
  works under the MSVC toolchain that produces `.pyd` — not just clang/gcc.
- `language="c++"` + `cythonize(...)` are already cross-platform.

## Building a `.pyd` on Windows

With Python + a C++ compiler (MSVC Build Tools, or MinGW) and `cython` installed:

```bat
cd examples\mathpkg
python -m pip install .
:: or, in-place:
python setup.py build_ext --inplace
:: -> mathlib_py.cp3XX-win_amd64.pyd  (importable: `import mathlib_py`)
```

The resulting `.pyd` imports and runs identically to the `.so` shown in the
macOS/Linux demos (same `add` / `hypot2` / `Accumulator`).

## Why we don't "generate" `.pyd` files directly

A `.pyd` is machine code for a specific Python ABI + CPU + OS. Producing one
requires compiling on (or cross-compiling for) Windows; it is the output of the
toolchain, never a text artifact emitted by a source-to-source generator like
`cppast_autopxd`. Generating it from the parser would mean *being* a C++
compiler, which is out of scope (and unnecessary — Cython + the platform
compiler already do it).

See [FEASIBILITY.md](FEASIBILITY.md) and [examples/README.md](examples/README.md)
for the end-to-end `.pxd → module` demos.
