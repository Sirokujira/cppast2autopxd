#!/usr/bin/env bash
# gen.sh - (re)generate miniz.pxd from the vendored real miniz header.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TOOL="$REPO/cppast_autopxd"
[[ -x "$TOOL" ]] || { echo "build the tool first: (cd $REPO && ./bootstrap.sh)" >&2; exit 1; }
"$TOOL" --output_dir "$HERE" --xml_dir "" --std c++14 "$HERE/src/miniz.h"
echo "generated: $HERE/miniz.pxd"
