---
description: Add support for a new C/C++ construct to the pxd generators (both implementations)
---

Add generator support for the construct given in $ARGUMENTS, keeping the
two implementations in parity:

1. **Probe first**: write a minimal `.pxd` by hand expressing the intended
   output and run `python -m cython --cplus -3` over a pyx that cimports
   it. If Cython rejects every phrasing, the construct is skip-with-warning
   territory — do not force it.
2. **Python implementation**: lower it in `src/cppast2autopxd/parser.py`
   (to `ir.py` nodes), render in `emitter.py`, map types in `typemap.py`.
   Extend `tests/test_generate.py` (text level) and
   `tests/test_cython_compile.py` (E2E usage in the shared pyx).
3. **C++ implementation**: extend the visitor/post-process pipeline in
   `cpp/autopxd.hpp` (new behaviors are text passes, in the established
   style), add a self-contained gating fixture under `cpp/tests/input/`,
   and append a numbered `cpp/FEASIBILITY.md` entry.
4. **Gates**: `python -m pytest tests/ -q` all green AND
   `cd cpp && bash run_tests.sh` all `[cython OK]`.
5. If the construct appears in PCL's API surface, also extend the parity
   or mini-PCL fixtures so the coverage is locked for the downstream
   python-pcl_skbuild pipeline.
