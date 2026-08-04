"""pyx scaffold generation: the scaffold must always be VALID Cython that
compiles against the generated pxd, with un-scaffoldable pieces left as
TODO comments — and it must never overwrite an existing file."""

import os
import subprocess
import sys
import textwrap

import pytest

from cppast2autopxd import generate_pxd, run_config
from cppast2autopxd.cli import main
from cppast2autopxd.config import GeneratorConfig, HeaderJob
from cppast2autopxd.generator import derive_pxd_module, scaffold_collides
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


def test_ctor_string_param_gets_encode_glue(tmp_path):
    header = tmp_path / "named.h"
    header.write_text(textwrap.dedent("""\
        #pragma once
        #include <string>
        namespace demo {
        class Named {
        public:
            Named(const std::string& name);
            int id() const;
        };
        }
    """))
    result = generate_pxd(
        str(header), extern_from="named.h", namespaces=["demo"]
    )
    (tmp_path / "named.pxd").write_text(result.text)
    scaffold = render_scaffold(result.module, "named", "named.h")

    assert "def __cinit__(self, str name):" in scaffold
    # the constructor call needs the same encode glue as method calls
    assert "new cpp.Named(<string> name.encode())" in scaffold

    (tmp_path / "named_wrap.pyx").write_text(scaffold)
    _compile(tmp_path, "named_wrap.pyx")


def test_self_and_keyword_params_are_sanitized(tmp_path):
    # 'self' and Python keywords are legal C++ parameter names; the
    # scaffold must rename them or it will not compile.
    header = tmp_path / "mover.h"
    header.write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        class Mover {
        public:
            Mover(int self, int from);
            int shift(int def, int global) const;
        };
        }
    """))
    result = generate_pxd(
        str(header), extern_from="mover.h", namespaces=["demo"]
    )
    (tmp_path / "mover.pxd").write_text(result.text)
    scaffold = render_scaffold(result.module, "mover", "mover.h")

    assert "def __cinit__(self, int self_, int from_):" in scaffold
    assert "new cpp.Mover(self_, from_)" in scaffold
    assert "def shift(self, int def_, int global_):" in scaffold
    assert "self.thisptr.shift(def_, global_)" in scaffold

    (tmp_path / "mover_wrap.pyx").write_text(scaffold)
    _compile(tmp_path, "mover_wrap.pyx")


def test_derive_pxd_module_walks_package_dirs(tmp_path):
    pkg = tmp_path / "src" / "pcl" / "pxd"
    pkg.mkdir(parents=True)
    (tmp_path / "src" / "pcl" / "__init__.py").write_text("")
    (pkg / "__init__.pxd").write_text("")
    out = pkg / "point_types.pxd"
    assert derive_pxd_module(str(out)) == "pcl.pxd.point_types"
    # outside any package: plain basename
    assert derive_pxd_module(str(tmp_path / "plain.pxd")) == "plain"


def test_scaffold_collision_is_refused(tmp_path):
    assert scaffold_collides(
        str(tmp_path / "rect.pyx"), str(tmp_path / "rect.pxd")
    )
    assert not scaffold_collides(
        str(tmp_path / "rect_wrap.pyx"), str(tmp_path / "rect.pxd")
    )

    # CLI mode: refused up front, nothing written
    rc = main([
        os.path.join(HEADERS, "rectangle.hpp"),
        "-o", str(tmp_path / "rect.pxd"),
        "--namespace", "shapes",
        "--pyx-scaffold", str(tmp_path / "rect.pyx"),
    ])
    assert rc == 2
    assert not (tmp_path / "rect.pyx").exists()

    # config mode: raises instead of writing a self-cimporting module
    cfg = GeneratorConfig(base_dir=str(tmp_path))
    cfg.headers.append(HeaderJob(
        path=os.path.join(HEADERS, "rectangle.hpp"),
        output=str(tmp_path / "r2.pxd"),
        extern_from="rectangle.hpp",
        namespaces=["shapes"],
        pyx_scaffold=str(tmp_path / "r2.pyx"),
    ))
    with pytest.raises(ValueError):
        run_config(cfg, verbose=False)


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
