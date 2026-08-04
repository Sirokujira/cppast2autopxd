# Examples: C/C++ → `.pxd` → Cython → importable Python package

These examples prove the full pipeline end to end — not just that a valid `.pxd`
is generated, but that the generated declarations drive a **real, importable
Python extension module**.

```
C++ header ──cppast_autopxd──▶ .pxd ──cimport──▶ .pyx ──Cython+clang──▶ .so ──import──▶ Python
```

## `minizpkg/` — REAL third-party library (miniz)

The headline example: a real, unmodified production C library —
[**miniz** 3.0.2](https://github.com/richgel999/miniz) (a zlib-compatible
compression library) — vendored as `src/miniz.{h,c}` and exposed as `miniz_py`.

- `miniz.pxd` — **generated** by `cppast_autopxd` from the real 71 KB header
  (117-function public API). The *entire* generated `.pxd` compiles with Cython.
- `miniz_py.pyx` — hand-written wrapper for the compression API.
- `build_and_test.sh` verifies real behavior:
  - `mz_crc32` matches Python's `zlib.crc32` (so we really call miniz),
  - `mz_compress2` + `mz_uncompress` round-trip,
  - miniz output is zlib-compatible (`zlib.decompress` reads it).

```sh
cd examples/minizpkg
PY=/path/to/python-with-cython ./build_and_test.sh
#  -> PASS: real miniz C lib -> pxd -> Cython -> Python; compress/crc verified
```

Getting the full real header to compile drove eight generator fixes (bogus libc
imports, opaque-struct `pass`, struct-member const, pointer typedefs, value-param
const, typedef dedup, anonymous `typedef enum {} Name`, curated `time_t`/`FILE`
imports) — see the repo `FEASIBILITY.md`.

## `mathpkg/` — minimal worked example

A small C++ library (`src/mathlib.h` + `src/mathlib.cpp`) with free functions
and a class, wrapped into the `mathlib_py` module.

- `mathlib.pxd` — **generated** by `cppast_autopxd` (regenerate: `./gen.sh`).
- `mathlib_py.pyx` — hand-written Cython wrapper that `cimport`s the `.pxd`.
- `pyproject.toml` + `setup.py` — PEP 517 build (`pip install .` works in an
  isolated build env).
- `build_and_test.sh` — regenerates the `.pxd`, builds in place, imports, and
  asserts behavior.

Run it (needs `cython` + `setuptools`; on macOS clang is used):

```sh
# from the repo root, build the tool once:
./bootstrap.sh
# then:
cd examples/mathpkg
PY=/path/to/python-with-cython ./build_and_test.sh
#  -> PASS: C++ -> pxd -> Cython -> Python import works end to end
```

Or as an installable package:

```sh
cd examples/mathpkg && pip install .
python -c "import mathlib_py as m; print(m.add(2,3), m.hypot2(3,4))"   # 5 5.0
```

## Scaffolding a new package — `../scaffold_pkg.sh`

The dependency-free, non-interactive alternative to a cookiecutter template:
give it a header (and optional `.cpp`) and it emits a complete buildable package
skeleton (generated `.pxd`, starter `.pyx`, `pyproject.toml`, `setup.py`,
`build_and_test.sh`, `README.md`).

```sh
./scaffold_pkg.sh --name mypkg --header path/to/foo.h --source path/to/foo.cpp
cd generated/mypkg
# edit mypkg.pyx to expose the API you want, then:
./build_and_test.sh
```

> Note: when the C++ sources live under `src/`, setuptools may place the built
> `.so` next to them in `src/`; import from there, or use `pip install .` for a
> proper install. `mathpkg` keeps the wrapper stem (`mathlib_py`) distinct from
> the header stem (`mathlib`) to avoid any module/dir confusion.
