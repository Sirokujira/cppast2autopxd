"""End-to-end validation: generated pxd files must be accepted by Cython.

Generates pxd files for every sample header into a temp dir, writes a .pyx
that cimports and uses them, and runs the real cython compiler (C++ mode).
This is the test that proves the emitted declarations are syntactically and
semantically valid Cython, not just plausible-looking text.
"""

import os
import shutil
import subprocess
import sys

import pytest

from cppast2autopxd import generate_pxd

HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = os.path.join(HERE, "headers")
MINI_PCL = os.path.join(HEADERS, "mini_pcl")

cython = shutil.which("cython")
pytestmark = pytest.mark.skipif(cython is None, reason="cython not installed")

USE_PYX = """\
# distutils: language = c++
from cython.operator cimport dereference as deref
from libcpp.memory cimport shared_ptr
from point_types cimport PointXYZ, PointXYZRGB
from point_cloud cimport PointCloud
from features cimport Widget, Color, Mode, index_t, name_map, split, add
from rectangle cimport Rectangle
from edge_cases cimport (
    CPoint, c_distance, Blob, Holder, Machine, ANON_FIRST, Middle, Second,
)
from templates cimport Box, MyAlloc


def use_everything():
    cdef PointXYZ p
    p.x = 1.0
    p.y = 2.0
    p.z = 3.0

    cdef PointCloud[PointXYZ]* cloud = new PointCloud[PointXYZ]()
    try:
        cloud.resize(8)
        cloud.push_back(p)
        assert cloud.size() == 9
        deref(cloud)[0].x = 4.0
    finally:
        del cloud

    cdef shared_ptr[PointCloud[PointXYZ]] sp
    cdef PointCloud[PointXYZ].Ptr tp

    cdef Widget* w = new Widget(3)
    try:
        assert w.id() == 3
    finally:
        del w

    cdef Color c = Color.RED
    cdef Mode m = Mode.Fast
    cdef index_t idx = 0

    cdef Rectangle* r = new Rectangle(0, 0, 2, 2)
    try:
        assert r.getArea() == 4
    finally:
        del r

    cdef CPoint cp
    cp.cx = 1.0
    cp.cy = 2.0
    cdef Blob b
    b.i = 3
    cdef Holder h
    h.fast = 1.0
    h.precise = 2.0
    h.blob.f = 3.0
    cdef Machine* mach = new Machine()
    try:
        mach.tune(1)
        mach.tune(1, 2.0)
    finally:
        del mach
    cdef Second s
    s.payload.b = 2
    cdef Middle mid = s.payload

    # defaulted template parameter: usable with one arg AND with two
    cdef Box[double]* box1 = new Box[double]()
    try:
        box1.put(1.5)
    finally:
        del box1
    cdef Box[double, MyAlloc[double]]* box2 = new Box[double, MyAlloc[double]]()
    del box2

    return int(idx) + <int> c + <int> m + <int> ANON_FIRST
"""


def _generate_all(outdir):
    jobs = [
        (os.path.join(MINI_PCL, "pcl", "point_types.h"),
         "pcl/point_types.h", ["pcl"], "point_types.pxd"),
        (os.path.join(MINI_PCL, "pcl", "point_cloud.h"),
         "pcl/point_cloud.h", ["pcl"], "point_cloud.pxd"),
        (os.path.join(HEADERS, "features.hpp"),
         "features.hpp", ["demo"], "features.pxd"),
        (os.path.join(HEADERS, "rectangle.hpp"),
         "rectangle.hpp", ["shapes"], "rectangle.pxd"),
        (os.path.join(HEADERS, "edge_cases.hpp"),
         "edge_cases.hpp", [], "edge_cases.pxd"),
        (os.path.join(HEADERS, "templates.hpp"),
         "templates.hpp", ["tpl"], "templates.pxd"),
    ]
    for header, extern_from, namespaces, out_name in jobs:
        result = generate_pxd(
            header, extern_from=extern_from, namespaces=namespaces
        )
        with open(os.path.join(outdir, out_name), "w") as fh:
            fh.write(result.text)


def test_generated_pxd_passes_cython(tmp_path):
    outdir = str(tmp_path)
    _generate_all(outdir)

    pyx = os.path.join(outdir, "use_everything.pyx")
    with open(pyx, "w") as fh:
        fh.write(USE_PYX)

    proc = subprocess.run(
        [sys.executable, "-m", "cython", "--cplus", "-3", "-I", outdir, pyx],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"cython rejected generated pxd files:\n{proc.stdout}\n{proc.stderr}"
    )
    assert os.path.exists(os.path.join(outdir, "use_everything.cpp"))
