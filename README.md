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

- `cdef extern from "header" namespace "ns" nogil:` blocks per namespace
- Classes / structs → `cdef cppclass` (plain data structs → `cdef struct`)
- Class templates → `cdef cppclass Name[T]`, member typedefs (`Ptr` aliases)
- Enums (plain and `enum class`), typedefs, `using` aliases, free functions
- `std::` type mapping with automatic cimports (`vector`, `map`, `string`,
  `shared_ptr`, `pair`, stdint types, ...); default template arguments such as
  allocators are dropped to match Cython's `libcpp` declarations
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

```toml
[generator]
std = "c++14"
include_dirs = ["pxdgen/headers"]
nogil = true
except_plus = true

[typemap.substitutions."Eigen::Vector4f"]
cython = "Vector4f"
cimport = "from pcl.eigen cimport Vector4f"

[[headers]]
path = "pxdgen/headers/pcl/point_types.h"
extern_from = "pcl/point_types.h"     # path written into `cdef extern from`
output = "src/pcl/pxd/point_types.pxd"
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
