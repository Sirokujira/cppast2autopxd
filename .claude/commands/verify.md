---
description: Full verification loop for cppast2autopxd (install, tests, E2E cython check)
---

Run the full verification loop for this repository:

1. `pip install -e .[test]` (skip if already installed in this session)
2. `pytest -q` — all tests must pass.
3. If anything in `src/cppast2autopxd/emitter.py`, `parser.py`, or
   `typemap.py` changed, pay special attention to
   `tests/test_cython_compile.py`: it runs the real cython compiler over
   generated pxd output and is the ground truth for validity.
4. Report failures with the exact cython error output; when the failure is a
   grammar issue (const/except+/default args), consult the "Hard-won rules"
   section of CLAUDE.md before changing the emitter.
