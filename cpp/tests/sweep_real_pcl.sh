#!/usr/bin/env bash
# sweep_real_pcl.sh - generate PCL's common message headers as a mutually
# cimporting set and verify every one compiles under cython.
#
# This is the C++ counterpart of the Python side's tests/test_real_pcl.py:
# it AUTO-SKIPS where no PCL install is found and GATES (exit 1) where one
# is, so the 8/9 result recorded in FEASIBILITY.md #51 cannot silently
# regress. types.h is excluded by design (template metaprogramming).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL="$ROOT/cppast_autopxd"
[[ -x "$TOOL" ]] || TOOL="$ROOT/cppast_autopxd.exe"
CONF="$ROOT/tests/configs/pcl_messages.conf"
STD="${STD:-c++14}"

# PCL discovery: PCL_ROOT wins, else the first pcl-*/pcl/PCLHeader.h under
# the usual include roots. Never hard-code a path.
find_pcl() {
  if [[ -n "${PCL_ROOT:-}" && -f "$PCL_ROOT/include/pcl/PCLHeader.h" ]]; then
    echo "$PCL_ROOT/include"; return 0
  fi
  if [[ -n "${PCL_ROOT:-}" && -f "$PCL_ROOT/PCLHeader.h" ]]; then
    echo "${PCL_ROOT%/pcl}"; return 0
  fi
  local d
  for d in /usr/include/pcl-* /usr/local/include/pcl-* /opt/homebrew/include/pcl-*; do
    [[ -f "$d/pcl/PCLHeader.h" ]] && { echo "$d"; return 0; }
  done
  return 1
}
find_eigen() {
  local d
  for d in "${EIGEN_ROOT:-}" /usr/include/eigen3 /usr/local/include/eigen3 /opt/homebrew/include/eigen3; do
    [[ -n "$d" && -d "$d/Eigen" ]] && { echo "$d"; return 0; }
  done
  return 1
}

PCL_INC="$(find_pcl)" || { echo "sweep: no PCL install found - skipped"; exit 0; }
[[ -x "$TOOL" ]] || { echo "sweep: build the tool first (./bootstrap.sh)" >&2; exit 1; }
EIGEN_INC="$(find_eigen || true)"
CYTHON="${CYTHON:-$(command -v cython || true)}"

OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
INC=(-I "$PCL_INC")
[[ -n "$EIGEN_INC" ]] && INC+=(-I "$EIGEN_INC")

# header:extra cimports it needs from its siblings (generated earlier in this
# same list, so each pxd resolves against the ones already written).
ENTRIES=(
  "PCLHeader:"
  "PCLPointField:"
  "PCLImage:PCLHeader"
  "ModelCoefficients:PCLHeader"
  "Vertices:"
  "PCLPointCloud2:PCLHeader,PCLPointField"
  "PolygonMesh:PCLHeader,PCLPointCloud2,Vertices"
  "point_types:"
)

status=0
for entry in "${ENTRIES[@]}"; do
  name="${entry%%:*}"
  deps="${entry#*:}"
  args=(--output_dir "$OUT" --xml_dir "" --std "$STD" --fast_preprocessing
        --config "$CONF" "${INC[@]}")
  if [[ "$name" == "Vertices" ]]; then
    # pcl/types.h also declares Indices; resolve it the same way, to a
    # spelling whose own import the generator derives.
    args+=(--typemap "Indices=vector[int32_t]"
           --extra_cimport "from libcpp.vector cimport vector")
  fi
  if [[ -n "$deps" ]]; then
    IFS=',' read -r -a dep_list <<< "$deps"
    for dep in "${dep_list[@]}"; do
      args+=(--extra_cimport "from $dep cimport $dep")
    done
  fi

  if ! "$TOOL" "${args[@]}" "$PCL_INC/pcl/$name.h" >"$OUT/$name.log" 2>&1; then
    printf 'NG    %-20s generation failed (see %s)\n' "$name" "$OUT/$name.log"
    status=1; continue
  fi
  if [[ -n "$CYTHON" && "$CYTHON" != "skip" && -x "$CYTHON" ]]; then
    printf 'cimport %s\n' "$name" > "$OUT/use_$name.pyx"
    if ( cd "$OUT" && "$CYTHON" --cplus -I "$OUT" "use_$name.pyx" ) >"$OUT/cy_$name.log" 2>&1; then
      printf 'OK    %-20s [cython OK]\n' "$name"
    else
      printf 'NG    %-20s [cython FAIL]\n' "$name"
      sed -n '1,12p' "$OUT/cy_$name.log" >&2
      status=1
    fi
  else
    printf 'OK    %-20s [generated; cython skipped]\n' "$name"
  fi
done

exit $status
