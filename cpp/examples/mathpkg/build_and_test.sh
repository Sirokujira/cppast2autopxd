#!/usr/bin/env bash
# build_and_test.sh - regenerate the .pxd, build the extension in place, import
# it, and assert behavior. Proves the full pipeline:
#   C++ header -> cppast_autopxd (.pxd) -> Cython (.pyx) -> compiled .so -> import
#
# Set PY=/path/to/python to choose the interpreter (must have cython+setuptools).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-python3}"
[[ "$(uname)" == "Darwin" ]] && export SDKROOT="${SDKROOT:-$(xcrun --show-sdk-path)}"
cd "$HERE"

echo "== (re)generate .pxd =="
bash gen.sh

echo "== build extension in place =="
rm -f mathlib_py*.so mathlib_py.cpp; rm -rf build
"$PY" setup.py build_ext --inplace >/dev/null

echo "== import and verify =="
"$PY" - <<'PYEOF'
import mathlib_py as m
assert m.add(2, 3) == 5
assert abs(m.hypot2(3.0, 4.0) - 5.0) < 1e-9
a = m.Accumulator()
for v in (1.5, 2.5, 4.0): a.add(v)
assert a.total() == 8.0 and a.count() == 3
b = m.Accumulator(10.0); b.add(5.0)
assert b.total() == 15.0 and b.count() == 2
print("OK: add=%d hypot2=%.1f acc.total=%.1f acc.count=%d" %
      (m.add(2,3), m.hypot2(3.0,4.0), a.total(), a.count()))
print("PASS: C++ -> pxd -> Cython -> Python import works end to end")
PYEOF
