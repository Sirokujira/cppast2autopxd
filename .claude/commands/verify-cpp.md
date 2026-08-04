---
description: Build and verify the C++ implementation (cpp/) — bootstrap, fixtures, cython gate
---

Verify the C++ implementation end to end:

1. `cd cpp && ./bootstrap.sh` on the first run (clones cppast into
   `cpp/.deps/`, builds with the auto-detected LLVM, runs tests). On
   later runs `cmake --build build --target cppast_autopxd` is enough.
2. `bash run_tests.sh` — every committed fixture must print `[cython OK]`.
   A `[cython FAIL -> ...]` on a committed fixture is a blocker: read the
   logged cython error, fix the responsible post-process pass in
   `autopxd.hpp` (see `.claude/rules/cpp-implementation.md`), rebuild,
   re-run.
3. If emission behavior changed, append a numbered entry to
   `cpp/FEASIBILITY.md` describing before/after.
4. Report the fixture table and what changed.
