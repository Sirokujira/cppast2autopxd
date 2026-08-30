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

# --- options block (gating): --extra_cimport / --typemap composition -------
# cross_base.h generates plainly; cross_ref.h needs Vec3 cimported from that
# pxd and the sibling-header alias myindex_t substituted away — the same
# shape as PCL's message headers (PCLHeader/uindex_t). The pair must
# compile together under cython.
OPT_IN="$ROOT/tests/input_options"
if [[ -d "$OPT_IN" ]]; then
  name="options"
  if "$TOOL" --output_dir "$OUT" --xml_dir "" --std "$STD" "$OPT_IN/cross_base.h" >"$OUT/cross_base.log" 2>&1 \
     && "$TOOL" --output_dir "$OUT" --xml_dir "" --std "$STD" \
          --extra_cimport "from cross_base cimport Vec3, Vec3Alias" \
          --config "$ROOT/tests/configs/cross_ref.conf" \
          "$OPT_IN/cross_ref.h" >"$OUT/cross_ref.log" 2>&1; then
    # A MULTI-SYMBOL cimport must survive as ONE line. cxxopts splits a
    # vector option's value on commas by default, which turned this into two
    # entries and wrote the second to the pxd as a stray indented line --
    # invalid Cython with exit 0. It is the form python-pcl_skbuild's config
    # uses, so keep a fixture on it.
    if ! grep -q '^from cross_base cimport Vec3, Vec3Alias$' "$OUT/cross_ref.pxd"; then
      printf 'NG    %-24s multi-symbol --extra_cimport was split\n' "$name"
      status=1
    fi
    if [[ -n "$CYTHON" && "$CYTHON" != "skip" && -x "$CYTHON" ]]; then
      # same availability guard as cython_check: without a cython binary the
      # generation-only gate must stay green, not fail on this block.
      tmp="$(mktemp -d)"
      cp "$OUT/cross_base.pxd" "$OUT/cross_ref.pxd" "$tmp/"
      printf 'cimport cross_ref\n' > "$tmp/use_cross.pyx"
      if ( cd "$tmp" && "$CYTHON" --cplus use_cross.pyx ) >"$tmp/err" 2>&1; then
        printf 'OK    %-24s cross-cimport pair  [cython OK]\n' "$name"
      else
        cp "$tmp/err" "$OUT/$name.cython.log"
        printf 'NG    %-24s [cython FAIL -> %s]\n' "$name" "$OUT/$name.cython.log"
        status=1
      fi
      rm -rf "$tmp"
    else
      printf 'OK    %-24s cross-cimport pair  [cython skipped]\n' "$name"
    fi
  else
    printf 'NG    %-24s generation failed\n' "$name"
    status=1
  fi
fi

# --- emitter-mode block (gating): --extern_from / --except_plus / --no_nogil
# The flags that let this tool stand in for the Python implementation in
# python-pcl_skbuild's pxdgen pipeline. Generated twice from one fixture
# (with and without nogil) because the `except +` placement rules differ:
# `except + nogil const` is the only spelling cython accepts for a const
# method, and with --no_nogil there is no separator so the const is dropped.
# Checked by content, not just by exit code — an `except +` silently not
# emitted would still cython-compile.
if [[ -f "$ROOT/tests/input_options/emit_modes.h" ]]; then
  name="emit_modes"
  MODE_A="$OUT/emit_modes_nogil"; MODE_B="$OUT/emit_modes_no_nogil"
  mkdir -p "$MODE_A" "$MODE_B"
  # MODE_A takes extern_from from a CONFIG FILE and MODE_B from the flag, so
  # both routes to the same setting are covered.
  if "$TOOL" --output_dir "$MODE_A" --xml_dir "" --std "$STD" \
        --config "$ROOT/tests/configs/emit_modes.conf" --except_plus \
        "$ROOT/tests/input_options/emit_modes.h" >"$MODE_A/gen.log" 2>&1 \
     && "$TOOL" --output_dir "$MODE_B" --xml_dir "" --std "$STD" \
        --extern_from "demo/store.hpp" --except_plus --no_nogil \
        "$ROOT/tests/input_options/emit_modes.h" >"$MODE_B/gen.log" 2>&1; then
    a="$MODE_A/emit_modes.pxd"; b="$MODE_B/emit_modes.pxd"
    bad=""
    # --extern_from replaces the parsed file's name in both modes
    grep -q 'cdef extern from "demo/store.hpp"' "$a" || bad="$bad extern_from(nogil)"
    grep -q 'cdef extern from "demo/store.hpp"' "$b" || bad="$bad extern_from(no_nogil)"
    # const method: the one accepted order, and const dropped without nogil
    grep -q 'size_t size() except + nogil const$' "$a" || bad="$bad const-order"
    grep -q 'size_t size() except +$' "$b" || bad="$bad const-dropped"
    # mutable-reference returns stay exempt in both modes
    grep -q 'Value& at(size_t i) nogil$' "$a" || bad="$bad mutable-ref(nogil)"
    grep -q 'Value& at(size_t i)$' "$b" || bad="$bad mutable-ref(no_nogil)"
    grep -q 'Value& operator\[\](size_t i) nogil$' "$a" || bad="$bad mutable-ref-op"
    grep -q 'T& get\[T\](size_t i) nogil$' "$a" || bad="$bad mutable-ref-template"
    # a const-reference return is by-value safe, so it DOES take except +
    grep -q 'const Value& peek() except + nogil const$' "$a" || bad="$bad const-ref-return"
    # constructors, operator() and free functions take it too
    grep -q 'Store() except +$' "$a" || bad="$bad ctor"
    grep -q 'int operator()(int a) except + nogil$' "$a" || bad="$bad call-operator"
    grep -q 'size_t total(const Store& s) except + nogil$' "$a" || bad="$bad free-function"
    # `<` in an operator NAME is not an open angle bracket (every template
    # `<...>` is already `[...]` by this pass): operator< and operator<= must
    # not silently miss the `except +` their neighbours get.
    grep -q 'bool operator<(const Store& rhs) except + nogil const$' "$a" || bad="$bad operator-lt"
    grep -q 'bool operator<=(const Store& rhs) except + nogil const$' "$a" || bad="$bad operator-le"
    grep -q 'bool operator>=(const Store& rhs) except + nogil const$' "$a" || bad="$bad operator-ge"
    # `operator` must start a token: myoperator() is an ordinary function
    grep -q 'void myoperator(int a) except + nogil$' "$a" || bad="$bad name-ending-in-operator"
    # a function-pointer FIELD is not a callable declaration
    grep -q 'int(\* on_change)(int, int)$' "$a" || bad="$bad function-pointer-field"
    # --no_nogil really removes it (no bare `nogil` anywhere)
    grep -q ' nogil' "$b" && bad="$bad no_nogil-leak"
    if [[ -n "$bad" ]]; then
      printf 'NG    %-24s unexpected emission:%s\n' "$name" "$bad"
      status=1
    elif [[ -n "$CYTHON" && "$CYTHON" != "skip" && -x "$CYTHON" ]]; then
      # same availability guard as cython_check
      ok=1
      for d in "$MODE_A" "$MODE_B"; do
        ( cd "$d" && "$CYTHON" --cplus emit_modes.pxd ) >"$d/cython.log" 2>&1 || ok=0
      done
      if [[ $ok -eq 1 ]]; then
        printf 'OK    %-24s both emitter modes  [cython OK]\n' "$name"
      else
        printf 'NG    %-24s [cython FAIL -> %s]\n' "$name" "$MODE_A/cython.log"
        status=1
      fi
    else
      printf 'OK    %-24s both emitter modes  [cython skipped]\n' "$name"
    fi
  else
    printf 'NG    %-24s generation failed\n' "$name"
    status=1
  fi

  # extern_from is single-valued: a second one must be a LOCATED error, not
  # a silent last-one-wins. (The repeatable keys have no such rule.)
  dup="$OUT/emit_modes_dup.conf"
  printf 'extern_from = a/one.h\nextern_from = b/two.h\n' > "$dup"
  if "$TOOL" --output_dir "$MODE_A" --xml_dir "" --std "$STD" \
        --config "$dup" "$ROOT/tests/input_options/emit_modes.h" \
        >"$OUT/emit_modes_dup.log" 2>&1; then
    printf 'NG    %-24s duplicate extern_from accepted silently\n' "emit_modes"
    status=1
  elif ! grep -q 'more than once' "$OUT/emit_modes_dup.log"; then
    printf 'NG    %-24s duplicate extern_from failed without saying why\n' "emit_modes"
    status=1
  fi

  # Precedence: unlike the repeatable keys (which APPEND), a config
  # extern_from must LOSE to the flag — a command line silently overridden
  # by a file is the same class of bug as a silently ignored rule.
  prec="$OUT/emit_modes_prec.conf"
  printf 'extern_from = from/config.h\n' > "$prec"
  if "$TOOL" --output_dir "$MODE_A" --xml_dir "" --std "$STD" \
        --config "$prec" --extern_from "from/flag.h" \
        "$ROOT/tests/input_options/emit_modes.h" \
        >"$OUT/emit_modes_prec.log" 2>&1 \
     && grep -q 'cdef extern from "from/flag.h"' "$MODE_A/emit_modes.pxd"; then
    :
  else
    printf 'NG    %-24s --extern_from did not win over the config key\n' "emit_modes"
    status=1
  fi
else
  printf 'NG    %-24s tests/input_options/emit_modes.h missing\n' "emit_modes"
  status=1
fi

# --- real-PCL sweep (auto-skips without a PCL install; gates with one) -----
# -f, not -x: the script is invoked through `bash`, so a checkout that drops
# the exec bit (Windows, zip export, core.fileMode=false) must not silently
# remove the gate. Say so if it is missing at all.
if [[ -f "$ROOT/tests/sweep_real_pcl.sh" ]]; then
  if bash "$ROOT/tests/sweep_real_pcl.sh"; then :; else status=1; fi
else
  printf 'NG    %-24s tests/sweep_real_pcl.sh missing\n' "sweep"
  status=1
fi

exit $status
