"""The cppast delegation backend (the connection ir.py anticipated).

Runs only where the cppast_autopxd binary exists — the in-repo build at
cpp/cppast_autopxd (relative, like every other test path) or whatever
find_cppast_tool discovers — and auto-skips elsewhere, exactly like
tests/test_real_pcl.py does for a PCL install.
"""

import os
import subprocess
import sys

import pytest

from cppast2autopxd.cppast_backend import find_cppast_tool, generate_pxd_cppast

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
IN_REPO_TOOL = os.path.join(REPO, "cpp", "cppast_autopxd")


def _tool():
    if os.path.isfile(IN_REPO_TOOL) and os.access(IN_REPO_TOOL, os.X_OK):
        return IN_REPO_TOOL
    return find_cppast_tool()

pytestmark = pytest.mark.skipif(
    _tool() is None, reason="cppast_autopxd binary not built/installed"
)


def _cython_ok(tmp_path, name, text, pyx_body):
    (tmp_path / f"{name}.pxd").write_text(text)
    pyx = tmp_path / f"use_{name}.pyx"
    pyx.write_text(pyx_body)
    proc = subprocess.run(
        [sys.executable, "-m", "cython", "--cplus", "-3",
         "-I", str(tmp_path), str(pyx)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_delegates_with_option_mapping(tmp_path):
    """extra_cimports and substitutions map onto --extra_cimport/--typemap
    and the result compiles against the sibling pxd."""
    base = generate_pxd_cppast(
        os.path.join(REPO, "cpp", "tests", "input_options", "cross_base.h"),
        tool=_tool(),
    )
    result = generate_pxd_cppast(
        os.path.join(REPO, "cpp", "tests", "input_options", "cross_ref.h"),
        tool=_tool(),
        substitutions={"myindex_t": "uint32_t"},
        extra_cimports=["from cross_base cimport Vec3"],
    )
    assert "from cross_base cimport Vec3" in result.text
    assert "uint32_t count" in result.text
    assert "myindex_t" not in result.text
    (tmp_path / "cross_base.pxd").write_text(base.text)
    _cython_ok(
        tmp_path, "cross_ref", result.text,
        "from cross_ref cimport Path\n"
        "def f():\n    cdef Path p\n    return p.count\n",
    )


def test_parity_fixture_compiles(tmp_path):
    """A shared parity fixture generated through cppast is real Cython."""
    result = generate_pxd_cppast(
        os.path.join(REPO, "cpp", "tests", "input", "smart_returns.h"),
        tool=_tool(),
    )
    assert "shared_ptr[Res] build()" in result.text
    _cython_ok(
        tmp_path, "smart_returns", result.text,
        "from smart_returns cimport Factory\n"
        "def f():\n    cdef Factory fac\n    return fac.build().use_count()\n",
    )


def test_skips_surface_as_warnings():
    """# skipped: comments arrive in GenerationResult.warnings — the
    never-silent contract crosses the delegation boundary."""
    result = generate_pxd_cppast(
        os.path.join(REPO, "cpp", "tests", "input", "pcl_message.h"),
        tool=_tool(),
    )
    assert any("skipped:" in w for w in result.warnings)
    assert any("bitset" in w for w in result.warnings)


def test_missing_tool_is_loud(monkeypatch):
    monkeypatch.setenv("CPPAST2AUTOPXD_CPP_TOOL", "/definitely/not/here")
    assert find_cppast_tool() is None
    with pytest.raises(RuntimeError, match="not found"):
        generate_pxd_cppast(
            os.path.join(REPO, "cpp", "tests", "input", "simple.h")
        )


def test_tool_failure_is_loud():
    with pytest.raises(RuntimeError, match="failed"):
        generate_pxd_cppast(
            os.path.join(REPO, "cpp", "tests", "input", "simple.h"),
            tool=_tool(),
            config="/definitely/not/a.conf",
        )


EMIT_MODES = os.path.join(
    REPO, "cpp", "tests", "input_options", "emit_modes.h"
)


def test_extern_from_and_except_plus(tmp_path):
    """extern_from / except_plus map onto the tool's flags — the pair that
    lets this backend produce what python-pcl_skbuild's pipeline needs:
    parsed from a self-contained mirror header, but declaring the REAL
    include path, with C++ exceptions propagating."""
    result = generate_pxd_cppast(
        EMIT_MODES, tool=_tool(),
        extern_from="demo/store.hpp", except_plus=True,
    )
    assert 'cdef extern from "demo/store.hpp"' in result.text
    assert "emit_modes.h" not in result.text
    assert "Store() except +" in result.text
    # `except + nogil const` is the only ordering cython accepts for a
    # const method; `const except +` and `except + const` are errors.
    assert "size_t size() except + nogil const" in result.text
    # a mutable-reference return must stay exempt: cython's try/catch
    # wrapping would hand back a reference to a by-value temporary.
    assert "Value& at(size_t i) nogil" in result.text
    assert "Value& at(size_t i) except" not in result.text
    _cython_ok(
        tmp_path, "emit_modes", result.text,
        "from emit_modes cimport Store\n"
        "def f():\n    cdef Store s\n    return s.size()\n",
    )


def test_no_nogil_drops_const_with_except_plus(tmp_path):
    """With nogil=False there is no separator between `const` and
    `except +`, so exception propagation wins and the const is dropped —
    the same trade-off the libclang emitter makes."""
    result = generate_pxd_cppast(
        EMIT_MODES, tool=_tool(),
        extern_from="demo/store.hpp", except_plus=True, nogil=False,
    )
    assert " nogil" not in result.text
    assert "size_t size() except +" in result.text
    assert "size_t size() except + const" not in result.text
    _cython_ok(
        tmp_path, "emit_modes", result.text,
        "from emit_modes cimport Store\n"
        "def f():\n    cdef Store s\n    return s.size()\n",
    )


def test_defaults_match_the_tool(tmp_path):
    """Neither flag is passed by default: nogil on, except+ off. A caller
    porting a libclang configuration has to say so explicitly."""
    result = generate_pxd_cppast(EMIT_MODES, tool=_tool())
    assert "except +" not in result.text
    assert "size_t size() nogil const" in result.text
    assert 'cdef extern from "emit_modes.h"' in result.text


def test_cli_emission_defaults_do_not_depend_on_backend(tmp_path, capsys,
                                                        monkeypatch):
    """`--backend cppast` must not silently change what the CLI emits.

    The C++ tool defaults except+ OFF; this CLI (like its libclang path)
    defaults it ON, so the flag is passed explicitly. --extern-from,
    --no-nogil and --no-except-plus are honored rather than refused.
    """
    from cppast2autopxd.cli import main

    monkeypatch.setenv("CPPAST2AUTOPXD_CPP_TOOL", _tool())
    out = tmp_path / "emit_modes.pxd"
    rc = main([
        EMIT_MODES, "--backend", "cppast",
        "--extern-from", "demo/store.hpp", "-o", str(out),
    ])
    assert rc == 0
    text = out.read_text()
    assert 'cdef extern from "demo/store.hpp"' in text
    assert "size_t size() except + nogil const" in text

    rc = main([
        EMIT_MODES, "--backend", "cppast",
        "--no-except-plus", "--no-nogil", "-o", str(out),
    ])
    assert rc == 0
    text = out.read_text()
    assert "except +" not in text
    assert "nogil" not in text


def test_cli_still_refuses_what_the_backend_cannot_do(capsys, monkeypatch):
    """Shrinking the unsupported list must not empty it: name filtering
    and the other libclang-only options stay hard errors."""
    from cppast2autopxd.cli import main

    monkeypatch.setenv("CPPAST2AUTOPXD_CPP_TOOL", _tool())
    for flag in (["--namespace", "demo"], ["--include-name", "Store"],
                 ["--exclude-name", "Store"], ["--no-macros"],
                 ["--language", "c"]):
        assert main([EMIT_MODES, "--backend", "cppast"] + flag) == 2
        assert "cannot honor" in capsys.readouterr().err


def test_operator_names_are_not_angle_brackets(tmp_path):
    """`<` in an operator NAME is not an open angle bracket.

    Every template `<...>` is already `[...]` by the time the except+ pass
    runs, so a `<` in a declaration is always an operator. Counting it as a
    bracket made `operator<` and `operator<=` look like they had no
    parameter list, and they were silently skipped while `operator>=`
    beside them got its `except +` — one comparison operator terminating
    on a C++ exception and its neighbour propagating it.
    """
    result = generate_pxd_cppast(
        EMIT_MODES, tool=_tool(),
        extern_from="demo/store.hpp", except_plus=True,
    )
    for op in ("<", "<=", ">="):
        assert (
            f"bool operator{op}(const Store& rhs) except + nogil const"
            in result.text
        ), f"operator{op} missing except +"
    # `operator` must START a token, or myoperator() is skipped too
    assert "void myoperator(int a) except + nogil" in result.text
    # a function-pointer FIELD is not a callable declaration
    assert "int(* on_change)(int, int)\n" in result.text
    assert "on_change)(int, int) except" not in result.text
    _cython_ok(
        tmp_path, "emit_modes", result.text,
        "from emit_modes cimport Store\n"
        "def f():\n    cdef Store s\n    return s.size()\n",
    )


def test_multi_symbol_extra_cimport_survives(tmp_path):
    """A cimport naming several symbols must reach the pxd as ONE line.

    The option parser split every repeatable value on commas, so
    `cimport A, B` arrived as two entries and the second was written out
    as a stray indented line — invalid Cython at exit 0. It is the form
    python-pcl_skbuild's config uses in five places.
    """
    base = generate_pxd_cppast(
        os.path.join(REPO, "cpp", "tests", "input_options", "cross_base.h"),
        tool=_tool(),
    )
    result = generate_pxd_cppast(
        os.path.join(REPO, "cpp", "tests", "input_options", "cross_ref.h"),
        tool=_tool(),
        substitutions={"myindex_t": "uint32_t"},
        extra_cimports=["from cross_base cimport Vec3, Vec3Alias"],
    )
    assert "from cross_base cimport Vec3, Vec3Alias\n" in result.text
    assert "\n Vec3Alias" not in result.text
    (tmp_path / "cross_base.pxd").write_text(base.text)
    _cython_ok(
        tmp_path, "cross_ref", result.text,
        "from cross_ref cimport Path\n"
        "def f():\n    cdef Path p\n    return p.count\n",
    )


def test_empty_and_quoted_extern_from_are_refused():
    """Both routes to extern_from agree on what is invalid.

    An empty value used to fall through to the config key, so the flag
    documented as winning quietly lost; and a `"` closed the Cython string
    early, emitting broken text with exit 0.
    """
    with pytest.raises(RuntimeError, match="failed"):
        generate_pxd_cppast(
            EMIT_MODES, tool=_tool(), extern_from='a"b.h',
        )


NAME_RES = os.path.join(
    REPO, "cpp", "tests", "input_options", "name_resolution.h"
)


def test_name_resolution_rules(tmp_path):
    """The rules that decide whether generated pxd is usable at all (#56).

    A qualified name from another namespace resolves through the cimport
    (Cython has no qualification for a cimported name, so the cimport IS
    the statement of what the bare name means) and is skipped WITH a
    reason when it does not; an identifier that merely contains "const"
    survives; a Python keyword used as a parameter name is suffixed; and
    a C++ default argument expands into one declaration per arity,
    because a pxd cannot spell a default at all.
    """
    result = generate_pxd_cppast(
        NAME_RES, tool=_tool(),
        include_dirs=[os.path.join(REPO, "cpp", "tests", "input_options")],
        except_plus=True,
        extra_cimports=["from other_types cimport Widget"],
    )
    text = result.text
    # identifiers containing "const"
    assert "void reconstruct(int* out) except + nogil" in text
    assert "int constant_value() except + nogil const" in text
    assert "const int* const_pointer() except + nogil const" in text
    for wrong in ("re ruct(", " ant_value(", "const _pointer("):
        assert wrong not in text, f"{wrong!r}: the const scan split a name"
    # qualified names: resolved when cimported, skipped when not
    assert "void useWidget(const Widget& w) except + nogil" in text
    assert "other::Widget" not in text
    assert any("useGadget" in w and "does not resolve" in w
               for w in result.warnings), result.warnings
    # Python keyword as a parameter name
    assert "void copyInto(const Widget& in_, Widget& out) except + nogil" in text
    # default arguments -> one declaration per arity
    assert "int saveWidget(const Widget& w) except + nogil" in text
    assert "int saveWidget(const Widget& w, bool binary) except + nogil" in text
    assert (
        "int saveWidget(const Widget& w, bool binary, size_t precision)"
        " except + nogil" in text
    )
    assert "false" not in text

    # a `::` appearing ONLY in a default value must not kill the declaration
    assert "void setLimits(Widget& w) except + nogil" in text
    assert "void setLimits(Widget& w, float lo, float hi) except + nogil" in text
    # a function-pointer typedef keeps its parameter TYPES: dropping the
    # template brackets glued the argument onto the name, which the
    # resolution pass then turned into a silently WRONG type
    assert "ctypedef void(*WidgetCb)(shared_ptr[Widget], void*)" in text
    # a dependent name has no qualifier NAME before the `::`
    assert any("firstOf" in w and "does not resolve" in w
               for w in result.warnings), result.warnings
    assert "vector[int]iterator" not in text
    # ctypedef / using / union bind usable names
    assert "void useIndex(Index i) except + nogil" in text
    assert "void useScalar(Scalar s) except + nogil" in text
    assert "void useCell(const Cell& c) except + nogil" in text
    # a keyword-named DATA MEMBER is an "Empty declarator" too
    assert "\n        int in_\n" in text
    assert "\n        float lambda_\n" in text

    (tmp_path / "other_types.pxd").write_text("cdef struct Widget:\n    int id\n")
    _cython_ok(
        tmp_path, "name_resolution", text,
        "from name_resolution cimport Mesh\n"
        "def f():\n    cdef Mesh m\n    return m.constant_value()\n",
    )
