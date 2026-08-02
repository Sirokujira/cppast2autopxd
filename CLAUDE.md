# cppast2autopxd — Claude Code guide

Python tool that generates Cython `.pxd` declaration files from C++ headers
using libclang. Downstream consumer: `python-pcl_skbuild` (generates PCL
wrapper pxd files with this tool).

## Layout

- `src/cppast2autopxd/parser.py` — libclang AST → IR (skips what pxd can't
  express, records warnings)
- `src/cppast2autopxd/ir.py` — backend-agnostic IR dataclasses
- `src/cppast2autopxd/typemap.py` — C++ type spelling → Cython type +
  required cimports (textual, recursive)
- `src/cppast2autopxd/emitter.py` — IR → `cdef extern from` pxd text
- `src/cppast2autopxd/config.py` — TOML batch config (`[[headers]]` jobs)
- `src/cppast2autopxd/cli.py` — `cppast2autopxd` CLI (single header or
  `--config`)
- `tests/headers/` — sample C++ headers incl. `mini_pcl/` (stand-ins
  mirroring PCL's API surface)

## Commands

```sh
pip install -e .[test]        # needs system clang for builtin headers
pytest                        # full suite
pytest tests/test_cython_compile.py -v   # E2E: cython must accept output
cppast2autopxd tests/headers/rectangle.hpp --namespace shapes  # smoke test
```

## Hard-won rules (do not regress)

1. Cython grammar rejects `const` together with `except +` on a method —
   `except +` wins, `const` is dropped (see `emitter._one_signature`).
2. `=*` defaults are ONLY for template parameters; C++ default arguments
   must be expanded into overloads (see `emitter._signatures`).
3. The pip `libclang` wheel has no builtin headers; `parser.
   _builtin_include_args()` discovers a resource dir via
   `clang -print-resource-dir` (override: `CPPAST2AUTOPXD_RESOURCE_DIR`).
4. Anonymous unions/structs are flattened into the parent class — required
   for PCL point types.
5. `std::vector`'s allocator argument (and other default template args) must
   be dropped to match Cython's `libcpp` declarations.
6. Methods returning a NON-CONST reference (`T&`) never get `except +`:
   the try/catch wrapper stores the result in a by-value temporary, so
   `&cloud[i]` would point at a copy and writes would be silently lost
   (proven against real PCL; see `emitter._returns_mutable_reference`).

## Editing rules

- Any emitter/parser change MUST keep `tests/test_cython_compile.py` green —
  it runs the real cython compiler over generated output; that test is the
  ground truth for "valid pxd".
- New C++ constructs: parser lowers to IR, emitter renders, and both a
  text-level test (test_generate.py) and the E2E pyx (test_cython_compile.py)
  get extended.
- Unsupported constructs are skipped with a warning, never silently.
