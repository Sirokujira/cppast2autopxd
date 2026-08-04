# Common rules (always loaded)

## Ground truth is the cython compiler

- A pxd change is DONE only when the real `cython` compiler accepts the
  output. Text that "looks like Cython" is not evidence.
- Python side: `pytest tests/test_cython_compile.py` is the gate.
- C++ side: `bash run_tests.sh` inside `cpp/` — every fixture must show
  `[cython OK]`.

## Never silent

- Unsupported constructs are skipped WITH a recorded warning (Python) or a
  `# skipped:` comment (C++). Silently dropping or silently emitting broken
  text are both bugs.

## Generated files

- Never hand-edit generated `.pxd` output to make a test pass; fix the
  generator (parser/typemap/emitter or the C++ post-process pass) instead.

## Paths

- Configuration, docs, and tests use RELATIVE paths only. Machine-specific
  locations (LLVM, PCL installs) are discovered at runtime or passed via
  environment variables (`CPPAST2AUTOPXD_RESOURCE_DIR`,
  `CPPAST2AUTOPXD_LIBCLANG`, `LLVM_PREFIX`, `PCL_ROOT`, `SDKROOT`) — never hard-coded.

## Workflow

Research → Plan → Execute → Review → Ship: read the relevant rule file and
existing tests before editing; keep changes small; run the matching verify
command; state exactly what passed.
