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
