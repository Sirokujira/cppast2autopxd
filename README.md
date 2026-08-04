# cppast2autopxd

Generate Cython `.pxd` declaration files automatically from C++ headers.

`cppast2autopxd` parses C++ headers with **libclang** (the same compiler
infrastructure the [cppast](https://github.com/sirokujira/cppast) C++ library
builds on) and emits `cdef extern from` blocks ready to `cimport` from Cython
code. It exists to automate the most tedious part of wrapping C++ libraries
such as [PCL](https://pointclouds.org/) — see
[python-pcl_skbuild](https://github.com/sirokujira/python-pcl_skbuild), which
drives this tool from its build pipeline.

Existing `autopxd`/`autopxd2` tools cover C headers via pycparser; this tool
targets **C++**: namespaces, classes, class templates, overloads, operators,
smart pointers and STL containers.

## Features

- **C and C++** input (`--language c` for plain C headers: no `except +`,
  `_Bool` → `bint`, no C++ distutils line)
- `cdef extern from "header" namespace "ns" nogil:` blocks per namespace
- Classes / structs → `cdef cppclass` (plain data structs → `cdef struct`)
- Class templates → `cdef cppclass Name[T]` (non-type parameters declared by
  name: `VectorD[ScalarT, dimension_t]`), defaulted parameters as `Alloc=*`,
  member typedefs (`Ptr` aliases)
- Free function templates → `T clamp[T](T v, T lo, T hi)`
- Function pointers: typedefs (`ctypedef int (*cb)(int)`), struct fields,
  and inline parameters; C varargs (`printf(const char*, ...)`)
- Enums (plain, `enum class`, and anonymous) with `= value` members;
  `typedef struct {...} Name;` / `typedef enum {...} Name;` C idioms
- Simple integer `#define` constants exported as an anonymous enum
- Bit-fields emitted as plain fields (layout stays with the C compiler)
- typedefs, `using` aliases, free functions, named unions, `extern "C"`
  blocks, nested classes/enums/unions inside classes, `operator bool()`
- `std::` type mapping with automatic cimports (`vector`, `map`, `string`,
  `shared_ptr`, `pair`, `function`, `optional`, `atomic`, `complex`, stdint
  families, curated libc symbols like `time_t`/`FILE`, ...); default template
  arguments such as allocators are dropped to match Cython's `libcpp`
  declarations; `std::function<int(int)>` renders as `function[int(int)]`
- `boost::shared_ptr` / `pcl::shared_ptr` mapped to `shared_ptr`
- Anonymous union/struct flattening (PCL point types' SSE-padded unions)
- C++ default arguments expanded into Cython-visible overloads
- Private/protected members, move constructors, deleted members, rvalue
  references and other non-declarable constructs are skipped **with recorded
  warnings**, so runs are auditable
- `except +` appended everywhere by default so C++ exceptions become Python
  exceptions
- User type substitutions (e.g. map `Eigen::Vector4f` to your own pxd)
- Single-header CLI mode and TOML-config batch mode

## Install

```sh
pip install -e .
```

Requirements: Python >= 3.9, the `libclang` wheel (installed automatically),
and a clang installation for its builtin headers (`apt install clang` or
similar; auto-detected via `clang -print-resource-dir`, overridable with the
`CPPAST2AUTOPXD_RESOURCE_DIR` environment variable).

## Usage

Single header:

```sh
cppast2autopxd path/to/header.hpp -o out.pxd -I include/dir --namespace pcl
```

Batch mode from a TOML config:

```sh
cppast2autopxd --config pxdgen/pcl_headers.toml
```

### Driving everything from a CMake build (compile_commands.json)

Configure the C++ project (e.g. PCL, or a small consumer of it) with
`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, then point the generator at the
build directory — include paths, defines, the language standard, and
sysroot flags all come from the database, so nothing is hand-maintained:

```sh
cmake -S consumer -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cppast2autopxd /usr/include/pcl-1.14/pcl/PCLHeader.h \
    --compile-db build --namespace pcl -o pclheader.pxd
```

(or `compile_db = "build"` under `[generator]` in the TOML config).
Headers do not appear in compilation databases, so flags are taken from
the best path-matching source entry. The C++ implementation accepts a
database too: `cppast-autopxd <header> --database_dir build
--database_file <a-TU-in-the-db> --fast_preprocessing ...`.

### pyx scaffolds (starting-point wrappers)

The pxd is a mechanical projection and fully generated; a good `.pyx`
wrapper is a design artifact and is NOT fully automatable. The scaffolder
generates the mechanical part — one owned-pointer `cdef class` per
concrete C++ class, ctor/dtor plumbing, direct forwarding for
primitive/string-typed methods, `TODO` comments for the rest — and never
overwrites an existing file:

```sh
cppast2autopxd widget.hpp -o widget.pxd --pyx-scaffold widget_wrap.pyx
```

(or per-header `pyx_scaffold = "path.pyx"` in the TOML config.)

All relative paths in the config resolve against the **config file's own
directory** (here: `pxdgen/`):

```toml
[generator]
std = "c++14"
include_dirs = ["headers"]            # -> pxdgen/headers
nogil = true
except_plus = true

[typemap.substitutions."Eigen::Vector4f"]
cython = "Vector4f"
cimport = "from pcl.eigen cimport Vector4f"

[[headers]]
path = "headers/pcl/point_types.h"    # -> pxdgen/headers/pcl/point_types.h
extern_from = "pcl/point_types.h"     # path written into `cdef extern from`
output = "../src/pcl/pxd/point_types.pxd"   # -> src/pcl/pxd/ from repo root
namespaces = ["pcl"]
```

Python API:

```python
from cppast2autopxd import generate_pxd

result = generate_pxd("pcl/point_types.h", namespaces=["pcl"])
print(result.text)
for w in result.warnings:
    print("warning:", w)
```

## Example

Input header:

```cpp
namespace pcl {
struct PointXYZ {
    union {
        struct { float x; float y; float z; };
        float data[4];
    };
};
}
```

Output pxd:

```cython
cdef extern from "pcl/point_types.h" namespace "pcl" nogil:
    cdef struct PointXYZ:
        float x
        float y
        float z
        float data[4]
```

## Testing

```sh
pip install -e .[test]
pytest
```

The test suite includes an end-to-end check that runs the real `cython`
compiler over generated pxd files (including a mini-PCL `PointCloud<PointT>`
template) to prove they are valid Cython, not just plausible text.

## Architecture

```
C++ header --(libclang parser: parser.py)--> IR (ir.py)
                                              |
              type spellings --(typemap.py)---+--> emitter.py --> .pxd
```

The IR layer is backend-agnostic: a future backend can consume the AST dump
of the [cppast](https://github.com/sirokujira/cppast) tool instead of using
libclang bindings directly. See `docs/design.md`.

## License

MIT License (see `LICENSE`).
