# C/C++ → `.pxd` auto-generation — feasibility & status

Goal: generate Cython `.pxd` declaration files from C/C++ headers, using
**cppast** (libclang) for parsing, validated against real libraries (PCL /
draco). This records what works today, the environment, and the gaps.

## TL;DR

- **Environment + build: working** on macOS arm64 via CMake (`./bootstrap.sh`).
  See [README_macos.md](README_macos.md).
- **Generation: working and Cython-validated** for plain C, C++, and **templated
  C++** headers — every committed fixture's `.pxd` is verified to compile with
  real Cython (`cython --cplus`), not just eyeballed.
- **Proven on a REAL library**: [miniz 3.0.2](https://github.com/richgel999/miniz)
  (unmodified, 117-function compression API) → generated `.pxd` (whole file
  Cython-valid) → `miniz_py` extension that imports and round-trips real data,
  with `mz_crc32` matching `zlib.crc32` and output readable by `zlib.decompress`.
  See [examples/minizpkg](examples/minizpkg) / [examples/README.md](examples/README.md).
- **Importable Python package: proven** — `build_ext` and `pip install .` (PEP
  517) both produce an importable module; see [examples/](examples/).
- **`.pyd`: out of scope** — a `.pyd` is a *compiled* Windows extension (DLL),
  the output of compiling Cython/C++, not something generated from C++ source.
- **Un-cimportable std constructs: handled** — declarations touching std
  iostreams (e.g. free `operator<<(std::ostream&, …)`) are now dropped as
  `# skipped:` comments so the rest of the file stays valid; the fetched
  draco `status.h` passes `[cython OK]`.
- **Linux: working** — builds against distro LLVM (verified Ubuntu 24.04 +
  LLVM 18, current upstream cppast); `bootstrap.sh` auto-detects
  `llvm-config`/`llvm-config-N` when Homebrew's keg is absent.
- **PCL point types: working** — anonymous unions/structs flatten into the
  enclosing record (committed gating fixtures `pcl_point_types.h` /
  `pcl_point_cloud.h`, both `[cython OK]`).

## Verified results (`./run_tests.sh`)

All nine committed fixtures generate AND pass Cython validation (a `cython`
binary on `PATH`, or `CYTHON=/path`, enables the `[cython OK]` check):

```
OK    c_api                          708 bytes  (21 AST visits)  [cython OK]
OK    coverage                      1242 bytes  (61 AST visits)  [cython OK]
OK    pcl_header                     469 bytes  (16 AST visits)  [cython OK]
OK    pcl_point_cloud                939 bytes  (32 AST visits)  [cython OK]
OK    pcl_point_types               1192 bytes  (115 AST visits)  [cython OK]
OK    simple                         824 bytes  (33 AST visits)  [cython OK]
OK    statuslike                     621 bytes  (25 AST visits)  [cython OK]
OK    templates                      667 bytes  (29 AST visits)  [cython OK]
OK    vectord                        821 bytes  (23 AST visits)  [cython OK]
```

(`tests/input/draco/status.h`, a fetched/gitignored real header, is generated
and checked too but is informational — see limitations below.)

### C++ — `tests/input/simple.h` → `tests/output/simple.pxd`

Actual output (abridged):

```cython
cdef extern from ".../simple.h" namespace "demo":
    cdef enum Color:
        RED = 0
        GREEN = 1
        BLUE = 2
    cdef enum Mode:
        Fast
        Slow
    cdef struct Point:
        float x
        float y
        int32_t id
    int add(int a, int b) nogil
    double distance(demo::Point const& a, demo::Point const& b) nogil
    cdef cppclass Shape:
        Shape()
        explicit Shape(double area)
        double area() const nogil
        void set_area(double a) nogil
        virtual int sides() const nogil
    ctypedef int(*compare_fn)(void const*, void const*)
```

The namespace block, enums, struct + fields, the class as `cdef cppclass` with
its public methods, and the function-pointer typedef are all emitted. Standard
headers are remapped to `from libc.stdint cimport ...`. Enum members carry their
`= value`, free functions and methods keep their return type, and `const` /
pointer / parameter spacing is normalized into valid Cython.

### C — `tests/input/c_api.h` → `tests/output/c_api.pxd`

`extern "C"` structs/enums + the three functions
(`vec3_add`, `vec3_dot`, `buffer_size`) are emitted, with
`ctypedef vec3 vec3` / `ctypedef status status` for the C typedef-struct idiom.

### Templated C++ — `tests/input/templates.h` & `vectord.h`

Template classes and free function templates emit as parametrized Cython
declarations. From `vectord.h` (modeled on draco's `core/vector_d.h`):

```cython
cdef extern from ".../vectord.h" namespace "draco":
    cdef cppclass VectorD[ScalarT, dimension_t]:
        ctypedef ScalarT Scalar
        ctypedef VectorD[ScalarT, dimension_t] Self
        VectorD()
        VectorD(Scalar const& c0, Scalar const& c1)
        Scalar& operator[](int i) nogil
        Self operator-() const nogil
        Scalar Dot(Self const& o) const nogil
        int dimension() const nogil
```

Single- and multi-parameter template classes (`Vector3[T]`, `Array[T, N]`),
methods returning the template type (`Self`), `const&` parameters, operators,
member typedefs with template arguments (`Foo<A, B>` → `Foo[A, B]`), and free
function templates (`T clamp(T v, T lo, T hi)`) are all handled. cppast emits a
`class_template_t` proxy wrapping the real `class_t`; the generator emits the
parametrized line once from the proxy and skips the duplicate inner class.

## Critical fix found during bring-up (macOS)

Homebrew's libclang has **no default macOS SDK sysroot**, so cppast's
preprocessing can't find `<stdint.h>`/`<string>` and the parsed AST comes back
**empty** (0-byte `.pxd`, no error). Fixed by exporting `SDKROOT` (via
`xcrun --show-sdk-path`) in `main.cpp` on `__APPLE__`. Reproduce the underlying
issue: `clang++ -E -std=c++14 tests/input/simple.h` fails with
"'stdint.h' file not found"; `-isysroot "$(xcrun --show-sdk-path)"` fixes it.

## Fixed emission bugs

All corrected and **verified by compiling the output with Cython**:

1. ~~enum values printed `RED 0`~~ → `RED = 0` (negatives kept: `= -1`).
2. ~~return types dropped (`cdef add(...)`)~~ → `int add(int a, int b)`, etc.
3. ~~`const`/pointer/param mangling (`voidconst*`, `area()const`, `a,int b`)~~ →
   `void const*`, `area() const`, `a, int b`.
4. ~~`from libc.stddef cimport stddef`~~ → actual symbols; `size_t` comes only
   from `libc.stddef` (it is *not* in `libc.stdint`); imports de-duplicated.
5. ~~templates not modeled~~ → template classes (`Vector3[T]`, `Array[T, N]`),
   free function templates (`T clamp[T](...)`), template-argument typedefs
   (`Foo<A, B>` → `Foo[A, B]`).
6. ~~namespace header missing for a namespace's only child~~ → emitted on both
   visitor paths.
7. ~~`demo::Point` qualified inside the namespace block~~ → unqualified `Point`;
   the enclosing `ClassName::` scope is also stripped (`Status::Code` → `Code`).
8. ~~`explicit` / `virtual` keywords~~ → stripped (invalid in `.pxd`).
9. ~~`= default` / `= delete`~~ → stripped; ~~`std::string`~~ → `string`.
10. ~~class-nested enum `ctypedef enum EnumTypeNameReplace ::C::E` / `EnumDef_X
    "::X`~~ → clean `enum Code:` (no `cdef` inside a cppclass) with plain members.
11. ~~`from libc.* cimport` interleaved with / inside `cdef extern from`~~ →
    hoisted to module top-level, de-duplicated by symbol, left-trimmed; empty
    `cdef extern from` blocks dropped; extern-from uses the header **basename**,
    not an absolute path.
12. ~~`#include <ostream>` → invalid `cimport <ostream>`~~ → non-mappable
    includes are skipped.
13. method modifier order `const nogil` → `nogil const` (Cython's order).
14. east-const → west-const (`T const&` → `const T&`), required by Cython.

### Found & fixed by running on the real miniz header

15. ~~bogus `from libc.<m> cimport <m>`~~ (e.g. `from libc.time cimport time`) →
    dropped, while valid C++ STL imports like `from libcpp.string cimport string`
    are kept.
16. ~~opaque/forward-declared struct (`struct X;`) → empty `cdef struct X:`~~ →
    a `pass` body is inserted.
17. ~~struct members not normalized~~ → members run through the same spacing
    pass (`unsigned char const* x` → `const unsigned char* x`).
18. ~~pointer typedef lost its `*` / kept pointer-const~~ → `typedef void* P`
    keeps `*`; `typedef void *const P` drops the meaningless const.
19. ~~duplicated typedef RHS (`unsigned long unsigned long mz_ulong`)~~ → fixed.
20. ~~top-level const on by-value params (`mz_uint32 const flags`)~~ → dropped.
21. ~~anonymous `typedef enum/struct { ... } Name;` left `Name` undefined~~ →
    the typedef name is attached to the otherwise-anonymous block.
22. curated symbol imports added for `time.h` (`time_t`) and `stdio.h` (`FILE`).

### Coverage pass (driven by `tests/input/coverage.h`)

23. ~~global/namespace variables emitted `extern int g;` (storage class + `;`)~~ →
    `int g` (storage keywords + trailing `;` dropped, run through normalization).
24. ~~static methods left a stray space, mis-aligning `@staticmethod`~~ → the
    space after `static` is dropped so the decorator and method align.
25. ~~redundant `ctypedef X X` self-typedefs leaked~~ → dropped in post-process.
26. ~~struct of only bit-fields collapsed to `pass`~~ → bit-fields emit as plain
    fields (`unsigned int a : 1` → `unsigned int a`; Cython has no width syntax).
27. `do_write_reference` wired to `ReferenceGenerator` (was a commented-out stub
    with the wrong signature) — completes the `generator/*` token architecture;
    `ReferenceGenerator` derives from `TokenGenerator` so existing matches hold.

### Robustness pass (Linux bring-up + PCL/draco real headers)

28. ~~anonymous nested `cdef union :` / `cdef struct :` (PCL point types)~~ →
    flattened into the enclosing record (header dropped, body dedented,
    applied repeatedly for nested unions-in-unions).
29. ~~free `operator<<(std::ostream&, …)` invalidated the whole file~~ → any
    declaration touching std iostream types is dropped as a `# skipped:`
    comment (curated deny-list; Cython ships no libcpp.ostream).
30. ~~move ctors / `T&&` emitted (Cython warns, un-callable)~~ → dropped as
    `# skipped:` comments.
31. ~~`bool` used without `from libcpp cimport bool` (silently resolved to
    Python bool; breaks the C++ compile of calling code)~~ → the import is
    added whenever a word-boundary `bool` appears in the body.
32. ~~`<cstdint>` (and transitive) stdint types missed the include-directive
    import mapping~~ → symbol-driven pass imports every stdint type actually
    used from `libc.stdint`.
33. ~~template angle brackets only converted at some sites
    (`ctypedef shared_ptr[PointCloud<PointT>]`, `vector<PointT> points`)~~ →
    a whole-file depth-counting pass converts every remaining template
    `<...>` to `[...]` (identifier-adjacent, `operator<`/`<<` untouched).

### Real-PCL pass (driven by `tests/input/pcl_header.h`, mirroring `pcl/PCLHeader.h`)

34. ~~member typedefs emitted inside `cdef struct` bodies (Cython rejects
    `ctypedef` there)~~ → a struct whose body contains member typedefs is
    promoted to `cdef cppclass` (the construct is C++-only, so promotion is
    safe; matches the Python implementation on `pcl/PCLHeader.h`).
35. ~~C++11 default member initializers leaked (`uint32_t seq=0`)~~ → field
    lines inside record bodies truncate at the first top-level `=`; enum
    members (`RED = 0`) and method declarations are untouched.
36. ~~libcpp.memory imports were include-driven: `<memory>` imported all of
    `unique_ptr`/`shared_ptr`/`weak_ptr` (unused noise), while `shared_ptr`
    arriving only transitively got no import at all~~ → symbol-driven pass
    (same shape as #32): scan the final body for word-boundary uses, add the
    missing, drop the unused.
37. ~~enclosing-class scope was deleted everywhere (`PCLHeader::Ptr` →
    bare `Ptr`), leaving namespace-scope aliases to a member typedef
    (`using HeaderPtr = PCLHeader::Ptr;`) undefined~~ → converted to
    Cython's dot spelling (`PCLHeader.Ptr`), verified valid both at
    namespace scope and inside the class's own body, so #7's inside-class
    case still compiles (`Status.Code get()`).

### Compilation-database mode (real PCL, verified on Linux)

`--database_dir <build> --database_file <a-TU-in-the-db>` feeds cppast the
exact flags of a CMake build (`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).
Verified against a real `find_package(PCL)` consumer: include dirs
(`-I/usr/include/pcl-1.14`, eigen) and the standard arrive from the
database and `pcl/PCLHeader.h` generates. Two caveats:

- **`--fast_preprocessing` is required for Boost-macro-heavy headers** —
  cppast's own preprocessing mangles `#include BOOST_PP_STRINGIZE(...)`
  (trailing `/**/` survives into the computed path) and errors out.
- ~~Known emission gaps on real-PCL constructs~~ — closed by #34-#37 below;
  the real `pcl/PCLHeader.h` (PCL 1.14, via `--fast_preprocessing`) now
  generates `[cython OK]`, matching the Python implementation's output.

## `.pyd` (Windows)

A `.pyd` is the *compiled* extension on Windows (the counterpart of the `.so`
shown in the demos), produced by the **same** Cython+setuptools build — not a
generator artifact. The example/scaffold `setup.py` now use a portable C++
standard flag (`/std:` on MSVC, `-std=` elsewhere) so the toolchain that emits
`.pyd` works. See [PYD.md](PYD.md).

## Known remaining limitations

1. **Free operators over un-cimportable std types** — e.g.
   `operator<<(std::ostream&, …)` in draco's raw `status.h`. Cython ships no
   `libcpp.ostream`, so such a declaration cannot be expressed; these need
   manual editing or a curated cimport map. (This is the only failure left in
   the fetched `status.h`; the committed `statuslike.h` covering the rest of
   that header passes.)
2. **Move semantics** (`T&&`) emit but Cython only warns ("Rvalue-reference as
   function argument not supported") — harmless but noise.
3. **Real PCL/draco headers** need their full include tree on `-I` to parse
   (they `#include` siblings); the committed `templates.h` / `vectord.h` /
   `statuslike.h` fixtures exercise the same constructs self-containedly.

## How to reproduce

```sh
brew install llvm cmake ninja
./bootstrap.sh                 # build + run tests
# real libraries:
tests/fetch_libs.sh draco
INCLUDES="-I.deps/draco/src" ./run_tests.sh
```

## Assessment

Auto-generating `.pxd` from C/C++ with cppast is **feasible and demonstrated**
for C and non-templated C++. To make the output drop-in valid Cython (and to
cover PCL/draco), the work is entirely in the `.pxd` *emission* layer — chiefly
the formatting bugs above and template class/function support.
