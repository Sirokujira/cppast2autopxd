---
paths: "cpp/**"
---
# C++ implementation rules (cpp/ — cppast_autopxd)

## Architecture

- `main.cpp` — CLI (cxxopts) + cppast `libclang_compile_config`.
- `autopxd.hpp` — visitor over the cppast AST plus a PIPELINE OF TEXT
  POST-PROCESS PASSES over the emitted lines (import hoisting, anonymous
  flattening, angle->square brackets, skip-comments, `pass` insertion...).
  New emission rules are added as passes in that chain, in the established
  style; order matters (flatten before `pass` insertion, etc.).
- `generator/` — token generator architecture consumed by `code_gen.hpp`.
- `nodes.h` — PxdNode tree the visitor builds.

## The ledger

- `FEASIBILITY.md` numbers every emission fix (#1..#55 so far). When you
  fix or add a behavior, append a numbered entry with the before/after.

## Build & test

```sh
cd cpp && ./bootstrap.sh      # clones cppast into .deps/, builds, tests
bash run_tests.sh             # committed fixtures are gating; all must be
                              # [cython OK]
pip install ./cpp             # scikit-build + CMake packaging: builds the
                              # binary (FetchContent clones cppast when
                              # .deps/ is absent), ships it in the
                              # cppast_autopxd_native package with the
                              # `cppast-autopxd` console script
```

- LLVM discovery: Homebrew keg on macOS, `llvm-config`/`llvm-config-N` on
  Linux; override with `LLVM_PREFIX`. Never hard-code an LLVM path.
- Fixture policy: committed `tests/input/*.h` are gating; subdirectories
  (`tests/input/draco/` etc.) are fetched real-world samples and
  informational. New behaviors get a committed, self-contained fixture.

## Emitter modes

- `--extern_from` / `--except_plus` / `--no_nogil` are the counterparts of
  the Python emitter's `extern_from` / `except_plus` / `nogil`, and are
  what lets this tool serve python-pcl_skbuild's pipeline through the
  delegation backend. `extern_from` is also a config key, single-valued:
  a duplicate is a located error and the command-line flag wins.
- `except +` placement is compiler-proven, not guessed (#54):
  `except + nogil const` is the ONLY accepted spelling of a const method
  (`const except +`, `except + const` and `const nogil` are syntax
  errors), so under `--no_nogil` the const is dropped. A non-const `T&`
  return never takes `except +` — cython's try/catch stores a by-value
  temporary, so the caller would get a reference to a copy.
- Two traps the pass shape invites (#55): by this point templates are
  already `[...]`, so a `<` in a declaration is an OPERATOR NAME, never a
  bracket; and a `(` immediately followed by `*` is a function-pointer
  DECLARATOR, not a parameter list.
- Option values are taken verbatim: `CXXOPTS_VECTOR_DELIMITER` is disabled
  in `main.cpp` because cxxopts otherwise splits a repeatable option's
  value on commas, which silently broke `cimport A, B`.

## Skip discipline

- A declaration Cython cannot express becomes a `# skipped: <decl> (<why>)`
  comment — the rest of the file must stay `[cython OK]`.
