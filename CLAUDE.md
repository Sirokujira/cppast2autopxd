# cppast2autopxd — Claude Code guide

Generates Cython `.pxd` declaration files from C/C++ headers. TWO
implementations live here, validated against shared expectations:

- `src/cppast2autopxd/` — **Python implementation** (libclang bindings;
  zero native build steps; drives python-pcl_skbuild's pxdgen pipeline)
- `cpp/` — **C++ implementation** `cppast_autopxd` (built on the real
  [cppast](https://github.com/foonathan/cppast) library; status ledger in
  `cpp/FEASIBILITY.md`)

Downstream consumer: `python-pcl_skbuild` (PCL wrapper pxd files).

## Commands

```sh
# Python implementation
pip install -e .[test]              # needs a system clang (builtin headers)
pytest                              # 67-test suite
pytest tests/test_cython_compile.py -v   # ground truth: cython accepts output
cppast2autopxd tests/headers/rectangle.hpp --namespace shapes  # smoke

# C++ implementation
cd cpp && ./bootstrap.sh            # clone cppast + build + run fixtures
cd cpp && bash run_tests.sh         # all fixtures must be [cython OK]
```

Slash commands: `/verify` (Python gate), `/verify-cpp` (C++ gate),
`/add-construct <construct>` (parity workflow for new C++ constructs).
Sub-agent: `pxd-reviewer` (evidence-based review of generator changes).

## Rules (auto-loaded from .claude/rules/)

- `common.md` — cython-compiler-is-ground-truth, never-silent skips, no
  hand-editing generated output, relative paths only
- `python-implementation.md` — layer architecture, proven Cython grammar
  facts (const/except+, `=*`, `T&` returns...), name-resolution discipline
- `cpp-implementation.md` — post-process pass pipeline, FEASIBILITY ledger,
  fixture policy, LLVM discovery

Read the matching rule file before editing; the grammar facts there were
established by running the real cython compiler — do not re-litigate them
from memory.

## Test layout

- `tests/headers/` — sample C++ headers; `mini_pcl/` mirrors PCL's API,
  `parity/` carries the C++ reference implementation's fixtures
- `tests/test_real_pcl.py` — runs only where a system PCL install exists
  (auto-skips elsewhere); when PCL is present it must stay green
- `cpp/tests/input/*.h` — committed gating fixtures for the C++ tool
  (subdirectories are fetched real-world samples, informational)
