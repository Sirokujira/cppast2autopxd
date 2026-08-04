#!/usr/bin/env bash
# gen.sh - (re)generate mathlib.pxd from src/mathlib.h using cppast_autopxd.
# The .pxd is a build input committed alongside the hand-written wrapper; rerun
# this whenever the C++ header changes.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TOOL="$REPO/cppast_autopxd"

[[ -x "$TOOL" ]] || { echo "build the tool first: (cd $REPO && ./bootstrap.sh)" >&2; exit 1; }

"$TOOL" --output_dir "$HERE" --xml_dir "" --std c++14 "$HERE/src/mathlib.h"
echo "generated: $HERE/mathlib.pxd"
