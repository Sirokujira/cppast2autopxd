#!/usr/bin/env bash
# bootstrap.sh - one-shot, idempotent setup:
#   1. clone cppast into .deps/cppast (if missing)
#   2. CMake-configure + build the cppast_autopxd tool (builds cppast as a
#      subproject; no separate cppast build/install step needed)
#   3. run the test fixtures
#
# Pin a known-good cppast with CPPAST_REF=<tag-or-sha>. Override the LLVM with
# LLVM_PREFIX=/path (defaults to Homebrew's keg-only llvm).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CPPAST="$ROOT/.deps/cppast"
BUILD="$ROOT/build"
# Default LLVM: Homebrew keg on macOS, distro llvm-config on Linux.
if [[ -z "${LLVM_PREFIX:-}" ]]; then
  if [[ -d /opt/homebrew/opt/llvm ]]; then
    LLVM_PREFIX=/opt/homebrew/opt/llvm
  elif command -v llvm-config >/dev/null 2>&1; then
    LLVM_PREFIX="$(llvm-config --prefix)"
  else
    for v in 20 19 18 17 16 15; do
      if command -v "llvm-config-$v" >/dev/null 2>&1; then
        LLVM_PREFIX="$(llvm-config-$v --prefix)"
        break
      fi
    done
  fi
fi
LLVM_PREFIX="${LLVM_PREFIX:-/opt/homebrew/opt/llvm}"
CPPAST_REF="${CPPAST_REF:-}"
log(){ echo "=== $* ==="; }

# 1) cppast source
if [[ ! -f "$CPPAST/CMakeLists.txt" ]]; then
  log "cloning cppast ${CPPAST_REF:+@$CPPAST_REF}"
  mkdir -p "$ROOT/.deps"
  if [[ -n "$CPPAST_REF" ]]; then
    git clone https://github.com/foonathan/cppast.git "$CPPAST" || { echo "clone FAILED"; exit 1; }
    git -C "$CPPAST" checkout "$CPPAST_REF" || { echo "checkout $CPPAST_REF FAILED"; exit 1; }
  else
    git clone --depth 1 https://github.com/foonathan/cppast.git "$CPPAST" || { echo "clone FAILED"; exit 1; }
  fi
fi

# 2) configure + build the tool (cppast is built transitively)
log "configuring (cmake)"
cmake -S "$ROOT" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_CONFIG_BINARY="$LLVM_PREFIX/bin/llvm-config" || { echo "configure FAILED"; exit 1; }

log "building cppast_autopxd (compiles cppast first; slow once)"
cmake --build "$BUILD" --target cppast_autopxd || { echo "build FAILED"; exit 1; }

[[ -x "$ROOT/cppast_autopxd" ]] || { echo "tool binary missing after build"; exit 1; }
log "built: $ROOT/cppast_autopxd"

# 3) run the tests
log "running tests"
bash "$ROOT/run_tests.sh" || true

log "bootstrap done"
