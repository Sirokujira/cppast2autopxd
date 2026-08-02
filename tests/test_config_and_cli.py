import os
import subprocess
import sys
import textwrap

from cppast2autopxd import load_config, run_config
from cppast2autopxd.cli import main

HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = os.path.join(HERE, "headers")


def _write_config(tmp_path):
    cfg = tmp_path / "pxdgen.toml"
    headers_rel = os.path.relpath(HEADERS, str(tmp_path))
    cfg.write_text(
        textwrap.dedent(
            f"""
            [generator]
            std = "c++14"
            include_dirs = ["{headers_rel}/mini_pcl"]

            [[headers]]
            path = "{headers_rel}/mini_pcl/pcl/point_types.h"
            extern_from = "pcl/point_types.h"
            output = "out/point_types.pxd"
            namespaces = ["pcl"]

            [[headers]]
            path = "{headers_rel}/mini_pcl/pcl/point_cloud.h"
            extern_from = "pcl/point_cloud.h"
            output = "out/point_cloud.pxd"
            namespaces = ["pcl"]
            """
        )
    )
    return str(cfg)


def test_load_and_run_config(tmp_path):
    cfg_path = _write_config(tmp_path)
    cfg = load_config(cfg_path)
    assert cfg.std == "c++14"
    assert len(cfg.headers) == 2
    assert cfg.headers[0].extern_from == "pcl/point_types.h"

    run_config(cfg, verbose=False)
    out = tmp_path / "out" / "point_types.pxd"
    assert out.exists()
    assert "cdef struct PointXYZ:" in out.read_text()
    assert (tmp_path / "out" / "point_cloud.pxd").exists()


def test_cli_single_header(tmp_path, capsys):
    out = tmp_path / "rect.pxd"
    rc = main(
        [
            os.path.join(HEADERS, "rectangle.hpp"),
            "-o",
            str(out),
            "--namespace",
            "shapes",
        ]
    )
    assert rc == 0
    assert "cdef cppclass Rectangle:" in out.read_text()


def test_cli_config_mode(tmp_path):
    cfg_path = _write_config(tmp_path)
    rc = main(["--config", cfg_path])
    assert rc == 0
    assert (tmp_path / "out" / "point_types.pxd").exists()


def test_cli_requires_exactly_one_mode(capsys):
    assert main([]) == 2


def test_cli_module_invocation(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "cppast2autopxd",
            os.path.join(HEADERS, "rectangle.hpp"),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "cdef cppclass Rectangle:" in proc.stdout
