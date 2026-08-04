"""pyx scaffold generation: the scaffold must always be VALID Cython that
compiles against the generated pxd, with un-scaffoldable pieces left as
TODO comments — and it must never overwrite an existing file."""

import os
import subprocess
import sys

from cppast2autopxd import generate_pxd
from cppast2autopxd.cli import main
from cppast2autopxd.pyx_scaffold import render_scaffold

HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = os.path.join(HERE, "headers")


def _compile(tmp_path, pyx_name):
    proc = subprocess.run(
        [sys.executable, "-m", "cython", "--cplus", "-3",
         "-I", str(tmp_path), str(tmp_path / pyx_name)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_rectangle_scaffold_compiles(tmp_path):
    result = generate_pxd(
        os.path.join(HEADERS, "rectangle.hpp"),
        extern_from="rectangle.hpp",
        namespaces=["shapes"],
    )
    (tmp_path / "rectangle.pxd").write_text(result.text)
    scaffold = render_scaffold(result.module, "rectangle", "rectangle.hpp")

    assert "cdef class Rectangle:" in scaffold
    assert "cdef cpp.Rectangle* thisptr" in scaffold
    # 4-arg constructor forwarded
    assert "new cpp.Rectangle(x0, y0, x1, y1)" in scaffold
    assert "def getArea(self):" in scaffold
    assert "return self.thisptr.getArea()" in scaffold

    (tmp_path / "rectangle_wrap.pyx").write_text(scaffold)
    _compile(tmp_path, "rectangle_wrap.pyx")


def test_features_scaffold_strings_and_todos(tmp_path):
    result = generate_pxd(
        os.path.join(HEADERS, "features.hpp"),
        extern_from="features.hpp",
        namespaces=["demo"],
    )
    (tmp_path / "features.pxd").write_text(result.text)
    scaffold = render_scaffold(result.module, "features", "features.hpp")

    assert "cdef class Widget:" in scaffold
    # string parameters/returns get encode/decode glue
    assert "def rename(self, str name):" in scaffold
    assert ".encode()" in scaffold
    assert ".decode()" in scaffold
    # pointer-returning method stays a TODO, not broken code
    assert "# TODO: wrap Widget* clone()" in scaffold

    (tmp_path / "features_wrap.pyx").write_text(scaffold)
    _compile(tmp_path, "features_wrap.pyx")


def test_template_class_becomes_todo(tmp_path):
    result = generate_pxd(
        os.path.join(HEADERS, "mini_pcl", "pcl", "point_cloud.h"),
        extern_from="pcl/point_cloud.h",
        namespaces=["pcl"],
    )
    (tmp_path / "point_cloud.pxd").write_text(result.text)
    scaffold = render_scaffold(result.module, "point_cloud", "point_cloud.h")
    assert "class template" in scaffold
    assert "cdef class PointCloud:" not in scaffold
    (tmp_path / "pc_wrap.pyx").write_text(scaffold)
    _compile(tmp_path, "pc_wrap.pyx")


def test_cli_scaffold_and_no_overwrite(tmp_path):
    out_pxd = tmp_path / "rectangle.pxd"
    out_pyx = tmp_path / "rectangle_wrap.pyx"
    rc = main([
        os.path.join(HEADERS, "rectangle.hpp"),
        "-o", str(out_pxd),
        "--namespace", "shapes",
        "--pyx-scaffold", str(out_pyx),
    ])
    assert rc == 0
    assert out_pyx.exists()
    content = out_pyx.read_text()
    assert "cdef class Rectangle:" in content

    # a second run must refuse to clobber the (now human-owned) file
    out_pyx.write_text(content + "\n# my edits\n")
    rc = main([
        os.path.join(HEADERS, "rectangle.hpp"),
        "-o", str(out_pxd),
        "--namespace", "shapes",
        "--pyx-scaffold", str(out_pyx),
    ])
    assert rc == 1
    assert "# my edits" in out_pyx.read_text()
