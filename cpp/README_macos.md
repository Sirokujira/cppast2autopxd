# Building `cppast_autopxd` on macOS

Generates Cython `.pxd` declaration files from C/C++ headers by parsing them
with [cppast](https://github.com/foonathan/cppast) (a libclang based C++ parser).

> **`.pyd`?** A `.pyd` is a *compiled* Windows Python extension (a DLL) — the
> output of compiling Cython/C++, not something generated from C++ source. This
> project targets `.pxd` only; `.pyd` is out of scope.

## Quick start

```sh
brew install llvm cmake ninja      # llvm provides libclang
./bootstrap.sh                     # clone cppast, build the tool, run tests
```

`bootstrap.sh` is idempotent/resumable. To pin a known-good cppast revision:
`CPPAST_REF=<tag-or-sha> ./bootstrap.sh`. Override the toolchain with
`LLVM_PREFIX=/path/to/llvm`.

## What bootstrap does

1. Clones cppast into `.deps/cppast` (gitignored) if missing.
2. CMake-configures and builds the `cppast_autopxd` target. cppast is built as
   a **subproject** (`add_subdirectory`) — no separate cppast install step.
   The binary is written to the repo root (`./cppast_autopxd`, gitignored).
3. Runs `run_tests.sh`, generating `tests/output/<name>.pxd` for every
   `tests/input/*.h`. If a `cython` binary is available (on `PATH` or via
   `CYTHON=/path/to/cython`), each generated `.pxd` is additionally **validated
   by compiling it with Cython** (`cython --cplus` on a `cimport` stub) and
   shown as `[cython OK]` / `[cython FAIL → …cython.log]`. Set `CYTHON=skip` to
   disable. To install Cython into a throwaway venv:
   `python3 -m venv /tmp/cyvenv && /tmp/cyvenv/bin/pip install cython`, then
   `CYTHON=/tmp/cyvenv/bin/cython ./run_tests.sh`.

Manual equivalent:

```sh
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_CONFIG_BINARY=/opt/homebrew/opt/llvm/bin/llvm-config
cmake --build build --target cppast_autopxd
```

> **Important:** pass `-DLLVM_CONFIG_BINARY=...`, **not**
> `-DLLVM_VERSION_EXPLICIT`. The latter makes cppast skip libclang header
> discovery and the build fails with `clang-c/Index.h not found`. Homebrew's
> llvm is keg-only, so its `llvm-config` is not on `PATH` — point at it
> explicitly (CMakeLists.txt already defaults to the Homebrew location).

## Run manually

```sh
./cppast_autopxd --output_dir tests/output --xml_dir "" --std c++14 tests/input/simple.h
# -> tests/output/simple.pxd
```

For real libraries pass their include roots so libclang resolves `#include`s:

```sh
tests/fetch_libs.sh draco
INCLUDES="-I.deps/draco/src" ./run_tests.sh
# or directly:
./cppast_autopxd --output_dir tests/output --xml_dir "" \
  -I .deps/draco/src tests/input/draco/status.h
```

## Options

- `USE_DOXYGEN` (CMake `-DUSE_DOXYGEN=ON`): enable Doxygen-XML doc-comment
  support. Heavy (Qt-based `doxy_parser`), off by default. The abstract
  interface header is always available; only the library + runtime calls are
  gated.

## Notes / gotchas (all handled in-repo)

- **Empty AST / 0-byte .pxd on macOS**: Homebrew libclang has no default SDK
  sysroot, so `<stdint.h>` etc. aren't found during preprocessing and the AST
  is empty. `main.cpp` exports `SDKROOT` (via `xcrun`) on `__APPLE__`.
- **cppast version drift**: current cppast dropped its generated
  `cppast_config.h` and only fetches cxxopts for its own tool — both are
  vendored under `compat/`.
- **`uint`**: `doxmlintf.h` uses the non-standard `uint`; `autopxd.hpp`
  includes `<sys/types.h>` first.

See [FEASIBILITY.md](FEASIBILITY.md) for what the generator produces today and
what still needs work.
