"""Smoke tests against a real PCL installation (skipped when absent).

These are the ground truth for "the generator handles real-world headers":
generation must succeed, warn about what it drops, and the emitted pxd must
be accepted by the real cython compiler.
"""

import glob
import os
import subprocess
import sys

import pytest

from cppast2autopxd import generate_pxd

PCL_ROOTS = sorted(glob.glob("/usr/include/pcl-*"))
pytestmark = pytest.mark.skipif(
    not PCL_ROOTS, reason="real PCL headers not installed"
)
PCL = PCL_ROOTS[-1] if PCL_ROOTS else ""
EIGEN = "/usr/include/eigen3"

#: Message-style headers: modest API, must produce compiling pxd.
MESSAGE_HEADERS = [
    "PCLHeader.h",
    "PCLPointField.h",
    "PCLImage.h",
    "ModelCoefficients.h",
    "PointIndices.h",
    "Vertices.h",
]


def _generate(header_rel):
    return generate_pxd(
        os.path.join(PCL, "pcl", header_rel),
        extern_from=f"pcl/{header_rel}",
        namespaces=["pcl"],
        include_dirs=[PCL, EIGEN],
        std="c++14",
    )


def _cython_accepts(tmp_path, name, pxd_text, cimports):
    (tmp_path / f"{name}.pxd").write_text(pxd_text)
    pyx = tmp_path / f"use_{name}.pyx"
    pyx.write_text(f"from {name} cimport {', '.join(cimports)}\n")
    proc = subprocess.run(
        [sys.executable, "-m", "cython", "--cplus", "-3",
         "-I", str(tmp_path), str(pyx)],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("header", MESSAGE_HEADERS)
def test_message_headers_generate_valid_pxd(tmp_path, header):
    result = _generate(header)
    main_type = header[:-2]  # strip ".h"
    assert f"cppclass {main_type}" in result.text or (
        f"struct {main_type}" in result.text
    )
    name = main_type.lower()
    ok, err = _cython_accepts(tmp_path, name, result.text, [main_type])
    assert ok, f"cython rejected generated pxd for {header}:\n{err}"


def test_point_cloud_header_parses_without_crash(tmp_path):
    """pcl/point_cloud.h is Eigen-heavy; generation must not crash and the
    output must be cython-valid (heavy skipping with warnings is fine)."""
    result = _generate("point_cloud.h")
    assert "PointCloud" in result.text
    ok, err = _cython_accepts(
        tmp_path, "point_cloud_real", result.text, ["PointCloud"]
    )
    assert ok, f"cython rejected generated pxd:\n{err}"


def test_point_types_header_parses_without_crash(tmp_path):
    """pcl/point_types.h re-includes itself via impl headers; the wrapper-TU
    parse must survive it."""
    result = _generate("point_types.h")
    # The macro-generated point types mostly live in included impl headers,
    # so the pxd may be sparse — the requirements are: no crash, and valid
    # output for whatever was exported.
    if "cdef" in result.text:
        first = result.text.split("cppclass ")
        cimports = []
        if len(first) > 1:
            cimports = [first[1].split("[")[0].split("(")[0].split(":")[0].strip()]
        if cimports:
            ok, err = _cython_accepts(
                tmp_path, "point_types_real", result.text, cimports
            )
            assert ok, f"cython rejected generated pxd:\n{err}"
