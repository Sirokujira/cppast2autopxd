"""Regression tests for defects found by stress-testing against real
PCL 1.14 headers.  Each case reproduces a confirmed defect class; the
common validation is: generation must not crash, must not emit text that
references undeclared names, and must warn whenever it drops something.
"""

import os
import platform
import subprocess
import sys
import textwrap

import pytest

from cppast2autopxd import generate_pxd


def _cython_ok(tmp_path, pxd_name, pxd_text, pyx_body):
    (tmp_path / f"{pxd_name}.pxd").write_text(pxd_text)
    pyx = tmp_path / "use.pyx"
    pyx.write_text(pyx_body)
    proc = subprocess.run(
        [sys.executable, "-m", "cython", "--cplus", "-3",
         "-I", str(tmp_path), str(pyx)],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, proc.stderr


def test_reinclusion_via_impl_header(tmp_path):
    """A header re-included by its own impl/*.hpp must parse (wrapper TU
    keeps #pragma once effective) instead of raising ParseError."""
    (tmp_path / "impl").mkdir()
    (tmp_path / "top.h").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo { struct Item { int id; }; }
        #include "impl/top_impl.hpp"
    """))
    (tmp_path / "impl" / "top_impl.hpp").write_text(textwrap.dedent("""\
        #pragma once
        #include "../top.h"
        namespace demo { inline int impl_helper(const Item& i) { return i.id; } }
    """))
    result = generate_pxd(
        str(tmp_path / "top.h"),
        extern_from="top.h",
        namespaces=["demo"],
        include_dirs=[str(tmp_path)],
    )
    assert "cdef struct Item:" in result.text


def test_included_typedef_resolves_via_canonical(tmp_path):
    """Members typed with an alias from an INCLUDED header must resolve to
    the canonical type instead of emitting an undeclared bare name."""
    (tmp_path / "types_mini.h").write_text(textwrap.dedent("""\
        #pragma once
        #include <cstdint>
        #include <vector>
        namespace pcl {
        using uindex_t = std::uint32_t;
        using Indices = std::vector<int>;
        }
    """))
    (tmp_path / "uses.h").write_text(textwrap.dedent("""\
        #pragma once
        #include "types_mini.h"
        namespace pcl {
        struct S2 {
            uindex_t offset;
            Indices indices;
        };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "uses.h"),
        extern_from="uses.h",
        namespaces=["pcl"],
        include_dirs=[str(tmp_path)],
    )
    text = result.text
    assert "uindex_t" not in text
    # canonicalization fully resolves the alias chain
    assert "unsigned int offset" in text
    assert "vector[int] indices" in text
    ok, err = _cython_ok(
        tmp_path, "uses", text,
        "from uses cimport S2\ndef f():\n    cdef S2 s\n    s.offset = 1\n",
    )
    assert ok, err


def test_unqualified_shared_ptr_alias(tmp_path):
    """pcl::shared_ptr referenced unqualified in a nested Ptr typedef must
    map to libcpp.memory's shared_ptr with the cimport recorded."""
    (tmp_path / "sp.hpp").write_text(textwrap.dedent("""\
        #pragma once
        #include <memory>
        namespace pcl {
        template <typename T> using shared_ptr = std::shared_ptr<T>;
        struct S {
            using Ptr = shared_ptr<S>;
            int v;
        };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "sp.hpp"),
        extern_from="sp.hpp",
        namespaces=["pcl"],
    )
    text = result.text
    assert "ctypedef shared_ptr[S] Ptr" in text
    assert "from libcpp.memory cimport shared_ptr" in text
    ok, err = _cython_ok(
        tmp_path, "sp", text,
        "from sp cimport S\ndef f():\n    cdef S.Ptr p\n",
    )
    assert ok, err


def test_member_function_template_emitted(tmp_path):
    """Member function templates ARE declarable and callable in Cython
    (``host.convert[int]()``) — verified against the real cython compiler,
    overturning the earlier skip whose reason claimed otherwise. Packs and
    template template parameters still warn-skip via the shared guard."""
    (tmp_path / "mft.hpp").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        class Host {
        public:
            Host();
            template <typename T> T convert() const;
            template <typename... Ts> void absorb(Ts... vs);
            int plain() const;
        };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "mft.hpp"), extern_from="mft.hpp", namespaces=["demo"]
    )
    assert "T convert[T]() except +" in result.text
    assert "int plain() except +" in result.text
    # the variadic member template still warn-skips
    assert "absorb" not in result.text
    assert any("parameter packs" in w for w in result.warnings)


def test_function_pointer_member_typedef_supported(tmp_path):
    """Function-pointer member typedefs are declarable in Cython and must be
    emitted (with methods referencing them intact)."""
    (tmp_path / "cb.hpp").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        class Runner {
        public:
            Runner();
            typedef void (*Callback)(int);
            void setCallback(Callback cb);
            int run();
        };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "cb.hpp"), extern_from="cb.hpp", namespaces=["demo"]
    )
    text = result.text
    assert "ctypedef void (*Callback)(int)" in text
    assert "void setCallback(Callback cb) except +" in text
    assert "int run() except +" in text
    ok, err = _cython_ok(
        tmp_path, "cb", text,
        "from cb cimport Runner\ndef f():\n"
        "    cdef Runner* r = new Runner()\n    r.run()\n    del r\n",
    )
    assert ok, err


def test_forward_declared_class_emitted_opaque(tmp_path):
    (tmp_path / "fwd.hpp").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        class Hidden;
        class User {
        public:
            User();
            Hidden* handle();
        };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "fwd.hpp"), extern_from="fwd.hpp", namespaces=["demo"]
    )
    text = result.text
    assert "cdef cppclass Hidden:" in text
    assert "Hidden* handle() except +" in text
    ok, err = _cython_ok(
        tmp_path, "fwd", text,
        "from fwd cimport User, Hidden\ndef f():\n"
        "    cdef User* u = new User()\n    cdef Hidden* h = u.handle()\n"
        "    del u\n",
    )
    assert ok, err


def test_variadic_class_template_skipped(tmp_path):
    (tmp_path / "var.hpp").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        template <typename... Args>
        class Tuplish {
        public:
            Tuplish();
        };
        struct Plain { int x; };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "var.hpp"), extern_from="var.hpp", namespaces=["demo"]
    )
    assert "Tuplish" not in result.text
    assert "cdef struct Plain:" in result.text
    assert any("variadic" in w for w in result.warnings)


def test_multidim_array_param_kept_verbatim(tmp_path):
    (tmp_path / "mat.hpp").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        void transform(const float matrix[4][4]);
        void flat(const float vec[16]);
        }
    """))
    result = generate_pxd(
        str(tmp_path / "mat.hpp"), extern_from="mat.hpp", namespaces=["demo"]
    )
    text = result.text
    # multi-dim keeps dims verbatim; 1-D decays to a pointer
    assert "void transform(const float matrix[4][4]) except +" in text
    assert "void flat(const float* vec) except +" in text
    ok, err = _cython_ok(
        tmp_path, "mat", text,
        "from mat cimport transform, flat\n",
    )
    assert ok, err


@pytest.mark.skipif(
    platform.machine().lower() not in ("x86_64", "amd64", "i386", "i686", "x86"),
    reason="xmmintrin/-msse2 are x86-only",
)
def test_compiler_builtin_vector_type_warns(tmp_path):
    (tmp_path / "simd.hpp").write_text(textwrap.dedent("""\
        #pragma once
        #include <xmmintrin.h>
        namespace demo {
        struct Wide {
            __m128 lanes;
            float scalar;
        };
        }
    """))
    result = generate_pxd(
        str(tmp_path / "simd.hpp"),
        extern_from="simd.hpp",
        namespaces=["demo"],
        extra_args=["-msse2"],
    )
    text = result.text
    assert "__m128" not in text
    assert "float scalar" in text
    assert any("lanes" in w for w in result.warnings)
