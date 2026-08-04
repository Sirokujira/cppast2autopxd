#!/usr/bin/env bash
# build_and_test.sh - regenerate the .pxd from the REAL miniz header, build the
# extension, import it, and verify real compression behavior end to end:
#   miniz.h -> cppast_autopxd (.pxd) -> Cython (.pyx) -> .so -> import -> run
# Set PY=/path/to/python (needs cython + setuptools).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-python3}"
[[ "$(uname)" == "Darwin" ]] && export SDKROOT="${SDKROOT:-$(xcrun --show-sdk-path)}"
cd "$HERE"

echo "== (re)generate miniz.pxd from real header =="
bash gen.sh

echo "== build extension =="
rm -f miniz_py*.so miniz_py.cpp; rm -rf build
"$PY" setup.py build_ext --inplace >/dev/null

echo "== import and verify (round-trip real data) =="
"$PY" - <<'PYEOF'
import zlib, os
import miniz_py as mz

print("miniz version:", mz.version())

payload = (b"The quick brown fox jumps over the lazy dog. " * 50)

# 1) miniz CRC-32 must match Python's zlib.crc32 (proves we call the real lib)
assert mz.crc32(payload) == zlib.crc32(payload), "crc32 mismatch"

# 2) compress with miniz, decompress with miniz: round-trip
comp = mz.compress(payload, 9)
assert len(comp) < len(payload), "no compression happened"
back = mz.uncompress(comp, len(payload))
assert back == payload, "round-trip mismatch"

# 3) cross-check: miniz output is zlib-compatible -> Python's zlib can inflate it
assert zlib.decompress(comp) == payload, "miniz output not zlib-compatible"

print("crc32      :", hex(mz.crc32(payload)))
print("orig/comp  : %d -> %d bytes" % (len(payload), len(comp)))
print("PASS: real miniz C lib -> pxd -> Cython -> Python; compress/crc verified")
PYEOF
