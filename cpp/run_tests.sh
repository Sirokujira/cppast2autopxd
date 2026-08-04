#!/usr/bin/env bash
# run_tests.sh - generate .pxd for every header under tests/input and report.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$ROOT/cppast_autopxd"
[[ -x "$TOOL" ]] || TOOL="$ROOT/cppast_autopxd.exe"   # Windows build output
OUT="$ROOT/tests/output"
STD="${STD:-c++14}"

[[ -x "$TOOL" ]] || { echo "build the tool first: ./bootstrap.sh" >&2; exit 1; }
mkdir -p "$OUT"
# Optional extra include roots, e.g. INCLUDES="-I/path -I/path2" for draco/PCL.
# Build the array guardedly (macOS' bash 3.2 + `set -u` treats an empty
# "${arr[@]}" as an unbound variable).
EXTRA_INC=()
if [[ -n "${INCLUDES:-}" ]]; then
  read -r -a EXTRA_INC <<< "${INCLUDES}"
fi

# Optional: validate the generated .pxd actually parses as Cython. Enabled when
# a `cython` binary is found, or one is pointed to via CYTHON=/path/to/cython.
# (Set CYTHON=skip to disable.) Validation compiles a tiny `cimport <name>`.
CYTHON="${CYTHON:-$(command -v cython || true)}"
cython_check() {
  [[ -n "$CYTHON" && "$CYTHON" != "skip" && -x "$CYTHON" ]] || return 2  # 2 = unavailable
  local name="$1" pxd="$2" tmp
  tmp="$(mktemp -d)"
  cp "$pxd" "$tmp/$name.pxd"
  printf 'cimport %s\n' "$name" > "$tmp/use_$name.pyx"
  ( cd "$tmp" && "$CYTHON" --cplus "use_$name.pyx" ) >"$tmp/err" 2>&1
  local rc=$?
  [[ $rc -ne 0 ]] && cp "$tmp/err" "$OUT/$name.cython.log"
  rm -rf "$tmp"
  return $rc
}

shopt -s nullglob
status=0
for hdr in "$ROOT"/tests/input/*.h "$ROOT"/tests/input/**/*.h; do
  name="$(basename "$hdr" .h)"
  log="$OUT/$name.log"
  # Committed fixtures live directly in tests/input/*.h and are part of the
  # pass/fail contract. Headers in subdirectories (tests/input/draco/, pcl/)
  # are third-party, fetched, gitignored real-world samples: still generated and
  # cython-checked, but their failures are informational (don't fail the run).
  case "$hdr" in
    "$ROOT"/tests/input/*/*) gating=0 ;;
    *) gating=1 ;;
  esac
  if "$TOOL" --output_dir "$OUT" --xml_dir "" --std "$STD" ${EXTRA_INC[@]+"${EXTRA_INC[@]}"} "$hdr" >"$log" 2>&1; then
    pxd="$OUT/$name.pxd"
    bytes=$( [[ -f "$pxd" ]] && wc -c <"$pxd" | tr -d ' ' || echo 0 )
    cbs=$(grep -c is_new_entity "$log" 2>/dev/null || echo 0)
    if [[ "${bytes:-0}" -gt 0 ]]; then
      cython_check "$name" "$pxd"; cy=$?
      case $cy in
        0) cytag="  [cython OK]" ;;
        2) cytag="" ;;  # cython unavailable
        *) cytag="  [cython FAIL -> $OUT/$name.cython.log]"; [[ $gating -eq 1 ]] && status=1 ;;
      esac
      printf 'OK    %-28s %5s bytes  (%s AST visits)%s\n' "$name" "$bytes" "$cbs" "$cytag"
    else
      printf 'EMPTY %-28s  (no entities; see %s)\n' "$name" "$log"; [[ $gating -eq 1 ]] && status=1
    fi
  else
    printf 'FAIL  %-28s  (tool exit!=0; see %s)\n' "$name" "$log"; [[ $gating -eq 1 ]] && status=1
  fi
done
exit $status
