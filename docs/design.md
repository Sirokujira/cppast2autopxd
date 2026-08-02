# Design

## Goal

Automate writing Cython `.pxd` declarations for large C++ APIs (primarily
PCL, for python-pcl_skbuild). Hand-written pxd files drift out of sync with
headers and are the single largest maintenance cost of a Cython wrapper.

## Pipeline

```
                +------------------+     +---------+     +------------+
 C++ header --> | parser backend   | --> |   IR    | --> |  emitter   | --> .pxd
                | (libclang today) |     | (ir.py) |     |(emitter.py)|
                +------------------+     +---------+     +------------+
                        |
                  typemap.py  (C++ type spelling -> Cython type + cimports)
```

- **parser.py** — walks the clang AST, keeps only declarations from the
  parsed file, applies namespace/name filters, lowers to IR. Everything that
  cannot be represented in a pxd (move ctors, rvalue refs, function pointers,
  alias templates, unsupported operators, private members) is skipped with a
  recorded warning so a generation run is auditable.
- **ir.py** — small dataclass tree: `Module -> NamespaceBlock -> Class/Enum/
  Typedef/Function/Variable`. Backend-agnostic on purpose.
- **typemap.py** — purely textual, recursive translation of C++ type
  spellings (`std::vector<pcl::PointXYZ> &` → `vector[PointXYZ]&`). Collects
  required cimport lines as a side effect. Textual operation means a future
  non-libclang backend can reuse it unchanged.
- **emitter.py** — renders IR into `cdef extern from` blocks.

## Notable emission rules

| C++ construct | pxd output |
| --- | --- |
| plain data `struct` | `cdef struct` (usable with value semantics) |
| class / struct with members | `cdef cppclass` |
| class template `<typename T>` | `cdef cppclass Name[T]` |
| anonymous union/struct fields | flattened into the parent class |
| default arguments | overload expansion (`f()`, `f(int)`) — `=*` is only valid for template parameter defaults |
| `const` method + `except +` | `except +` wins; Cython's grammar rejects the combination |
| method returning `T&` (non-const) | no `except +` — Cython's try/catch wrapping stores the result in a by-value temp, so writes through `&obj[i]` would be silently lost (matches libcpp's `T& operator[](size_type)`) |
| `std::vector<T, Alloc>` | `vector[T]` (allocator dropped, matches libcpp) |
| `boost::shared_ptr` / `pcl::shared_ptr` | `shared_ptr` from `libcpp.memory` |
| scoped enum | `cdef enum class` |

## Why libclang and not cppast?

[cppast](https://github.com/sirokujira/cppast) is a C++ library over libclang
with a cleaner AST; building it requires a C++ toolchain, its submodules and
LLVM dev packages. The Python `libclang` wheel gives us the same parse
fidelity with zero native build steps, which matters because this tool runs
inside pip builds and CI. The IR boundary is designed so a
`cppast`-dump-based backend (parsing the output of the cppast tool binary)
can be added later without touching typemap/emitter — that is the "cppast2"
in the name.

## Known limitations

- Non-type template parameters → class skipped (Cython cannot declare them)
- Alias templates (`template<class T> using X = ...`) → skipped
- Function templates → skipped
- Conversion operators (except none) → skipped
- Qualified names from unwrapped namespaces (e.g. `Eigen::Vector4f`) require
  an explicit `[typemap.substitutions]` entry; the failure is loud, not
  silent
- Explicit enum item values are not reproduced (extern enums do not need
  them)
