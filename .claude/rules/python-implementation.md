---
paths: "src/**,tests/**"
---
# Python implementation rules (src/cppast2autopxd)

## Architecture (do not blur the layers)

```
compiledb.py (compile_commands.json -> parse flags)
parser.py (libclang AST -> IR)  ->  ir.py (dataclasses)  ->  emitter.py (pxd text)
              \-> typemap.py (C++ type spelling -> Cython type + cimports)
pyx_scaffold.py (IR -> starting-point .pyx; never overwrites, always
                 compiles — un-scaffoldable members become TODO comments)
```

- typemap is TEXTUAL and backend-agnostic; never import clang there.
- compiledb extraction keeps only parse-relevant flags (-I/-D/-std/
  -isystem/-isysroot/-target); explicit user values take precedence,
  database values append.
- New construct = parser lowers to IR + emitter renders + BOTH a text-level
  test (test_generate.py) and an E2E cython test (test_cython_compile.py).

## Cython grammar facts (proven by probes — do not re-litigate)

1. `const` method qualifier and `except +` cannot be combined; `except +`
   wins (`emitter._one_signature`).
2. `=*` is ONLY for template parameter defaults; C++ default arguments
   expand into overloads (`emitter._signatures`).
3. Methods returning non-const `T&` never get `except +` — the try/catch
   wrapper stores a by-value temp and writes through `&x[i]` are lost.
4. Nested declarations inside `cdef cppclass` drop the `cdef` keyword.
5. Anonymous unions/structs flatten into the parent (PCL point types).

## Name resolution discipline

- Bare identifiers must resolve against `TypeMapper.known_names`/scopes;
  unknown names raise (parser warn-skips) — never pass through "on faith".
- The parser retries with the canonical spelling before giving up
  (`uindex_t` -> `unsigned int`).

## Environment

- Headers parse through a wrapper TU (`#include "..."`) so `#pragma once`
  works; the pip libclang wheel needs a clang install for builtin headers
  (auto-discovered; override with `CPPAST2AUTOPXD_RESOURCE_DIR`).
- `tests/test_real_pcl.py` auto-skips without a PCL install; when PCL is
  present it MUST stay green.
