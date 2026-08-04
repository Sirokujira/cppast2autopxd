"""Tests for general C/C++ coverage: plain C headers, function pointers,
varargs, typedef-struct idioms, macro constants, enum values, operator bool,
and the expanded std:: mapping."""

import os
import subprocess
import sys
import textwrap

from cppast2autopxd import generate_pxd


def _cython_ok(tmp_path, pxd_name, pxd_text, pyx_body, cplus=True):
    (tmp_path / f"{pxd_name}.pxd").write_text(pxd_text)
    pyx = tmp_path / "use.pyx"
    pyx.write_text(pyx_body)
    cmd = [sys.executable, "-m", "cython", "-3", "-I", str(tmp_path)]
    if cplus:
        cmd.append("--cplus")
    proc = subprocess.run(cmd + [str(pyx)], capture_output=True, text=True)
    return proc.returncode == 0, proc.stderr


C_HEADER = """\
#ifndef DEMO_C_H
#define DEMO_C_H

#define MAX_ITEMS 128
#define FLAG_HEX 0x10
#define NEG_OFFSET (-4)
#define VERSION_STR "1.0"          /* non-integer: skipped */
#define TWICE(x) ((x) * 2)         /* function-like: skipped */

typedef unsigned int item_id;

typedef struct {
    double x;
    double y;
} point2d;

typedef enum {
    MODE_OFF,
    MODE_ON = 7
} run_mode;

struct node;                        /* opaque forward declaration */

typedef int (*compare_fn)(const void* a, const void* b);

struct registry {
    point2d origin;
    item_id next_id;
    int (*on_change)(item_id id);
    unsigned flags : 3;             /* bitfield: skipped with warning */
    int plain;
};

int registry_count(const struct registry* r);
void registry_sort(struct registry* r, compare_fn cmp);
int registry_log(const char* fmt, ...);
_Bool registry_ok(const struct registry* r);

#endif
"""


def test_plain_c_header(tmp_path):
    (tmp_path / "demo_c.h").write_text(C_HEADER)
    result = generate_pxd(
        str(tmp_path / "demo_c.h"), extern_from="demo_c.h", language="c"
    )
    text = result.text

    # C mode: no C++ distutils line, no except +
    assert "language = c++" not in text
    assert "except +" not in text

    # macro constants exported as an anonymous enum (with values)
    assert "MAX_ITEMS = 128" in text
    assert "FLAG_HEX = 0x10" in text
    assert "NEG_OFFSET = -4" in text
    assert "VERSION_STR" not in text
    assert "TWICE" not in text

    # typedef struct/enum idioms named after the typedef
    assert "cdef struct point2d:" in text
    assert "cdef enum run_mode:" in text
    assert "MODE_ON = 7" in text
    assert "ctypedef unsigned int item_id" in text

    # opaque forward declaration
    assert "cppclass node" in text or "struct node" in text

    # function-pointer typedef, field, and parameter
    assert "ctypedef int (*compare_fn)(const void* a, const void* b)" in text
    assert "int (*on_change)(item_id id)" in text
    assert "void registry_sort(registry* r, compare_fn cmp)" in text

    # bitfields emit as plain width-less fields (layout comes from C)
    assert "unsigned int flags" in text
    assert ": 3" not in text
    assert "int plain" in text

    # varargs and _Bool
    assert "int registry_log(const char* fmt, ...)" in text
    assert "bint registry_ok(const registry* r)" in text

    ok, err = _cython_ok(
        tmp_path, "demo_c", text,
        textwrap.dedent("""\
            from demo_c cimport (
                point2d, registry, run_mode, MODE_ON, MAX_ITEMS,
                compare_fn, registry_count, registry_log,
            )
            def f():
                cdef point2d p
                p.x = 1.0
                cdef registry r
                r.plain = 2
                r.origin = p
                cdef compare_fn cmp = NULL
                return MAX_ITEMS + <int> MODE_ON
        """),
        cplus=False,
    )
    assert ok, err


def test_cpp_function_pointers_and_varargs(tmp_path):
    (tmp_path / "fp.hpp").write_text(textwrap.dedent("""\
        #pragma once
        #include <cstddef>
        namespace demo {
        typedef double (*unary_fn)(double);
        void apply(double* data, std::size_t n, unary_fn fn);
        void apply_inline(double* data, std::size_t n,
                          double (*fn)(double, void*));
        int logf(const char* fmt, ...);
        }
    """))
    result = generate_pxd(
        str(tmp_path / "fp.hpp"), extern_from="fp.hpp", namespaces=["demo"]
    )
    text = result.text
    assert "ctypedef double (*unary_fn)(double)" in text
    assert "void apply(double* data, size_t n, unary_fn fn) except +" in text
    assert (
        "void apply_inline(double* data, size_t n, "
        "double (*fn)(double, void*)) except +" in text
    )
    assert "int logf(const char* fmt, ...) except +" in text
    ok, err = _cython_ok(
        tmp_path, "fp", text,
        "from fp cimport unary_fn, apply, logf\n",
    )
    assert ok, err


def test_operator_bool_conversion(tmp_path):
    (tmp_path / "ob.hpp").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        class Handle {
        public:
            Handle();
            explicit operator bool() const;
            operator int() const;    // unsupported conversion: skipped
        };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "ob.hpp"), extern_from="ob.hpp", namespaces=["demo"]
    )
    text = result.text
    assert "bool operator bool() except +" in text
    assert "operator int" not in text
    assert any("operator int" in w for w in result.warnings)
    ok, err = _cython_ok(
        tmp_path, "ob", text,
        "from ob cimport Handle\ndef f():\n"
        "    cdef Handle* h = new Handle()\n"
        "    ok = True if h[0] else False\n    del h\n    return ok\n",
    )
    assert ok, err


def test_expanded_std_mappings(tmp_path):
    (tmp_path / "stdx.hpp").write_text(textwrap.dedent("""\
        #pragma once
        #include <atomic>
        #include <complex>
        #include <functional>
        #include <optional>
        #include <string>
        namespace demo {
        struct Box {
            std::function<int(int)> op;
            std::optional<int> maybe;
            std::atomic<int> counter;
            std::complex<double> z;
        };
        std::optional<std::string> find(int key);
        }
    """))
    result = generate_pxd(
        str(tmp_path / "stdx.hpp"),
        extern_from="stdx.hpp",
        namespaces=["demo"],
        std="c++17",
    )
    text = result.text
    assert "function[int(int)]" in text or "function[" in text
    assert "optional[int] maybe" in text
    assert "atomic[int] counter" in text
    assert "complex[double] z" in text
    assert "optional[string] find(int key) except +" in text
    assert "from libcpp.optional cimport optional" in text
    assert "from libcpp.atomic cimport atomic" in text


def test_enum_values_emitted():
    here = os.path.dirname(os.path.abspath(__file__))
    result = generate_pxd(
        os.path.join(here, "headers", "features.hpp"),
        extern_from="features.hpp",
        namespaces=["demo"],
    )
    assert "GREEN = 5" in result.text
    assert "RED = 0" in result.text
