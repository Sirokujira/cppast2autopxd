"""compile_commands.json driven generation.

Covers the loader (both entry forms, relative-path resolution), flag
extraction, best-entry matching for headers, and end-to-end generation
where ALL parse flags come from a CMake-style database.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

from cppast2autopxd import generate_pxd
from cppast2autopxd.compiledb import (
    CompileDbError,
    flags_for,
    load_compile_db,
)


def _write_db(tmp_path, entries):
    db = tmp_path / "compile_commands.json"
    db.write_text(json.dumps(entries))
    return str(db)


def test_load_command_and_arguments_forms(tmp_path):
    db = _write_db(tmp_path, [
        {
            "directory": str(tmp_path),
            "command": "g++ -Iinc -DFOO=1 -std=c++17 -c a.cpp -o a.o",
            "file": "a.cpp",
        },
        {
            "directory": str(tmp_path),
            "arguments": ["clang++", "-I", "inc2", "-DBAR", "-c", "b.cpp"],
            "file": "b.cpp",
        },
    ])
    commands = load_compile_db(db)
    assert len(commands) == 2
    # relative file resolved against directory
    assert commands[0].file == str(tmp_path / "a.cpp")

    flags_a = flags_for(str(tmp_path / "a.cpp"), commands)
    assert flags_a.include_dirs == [str(tmp_path / "inc")]
    assert flags_a.defines == ["FOO=1"]
    assert flags_a.std == "c++17"

    flags_b = flags_for(str(tmp_path / "b.cpp"), commands)
    assert flags_b.include_dirs == [str(tmp_path / "inc2")]
    assert flags_b.defines == ["BAR"]


def test_load_accepts_build_directory(tmp_path):
    _write_db(tmp_path, [
        {"directory": str(tmp_path), "command": "cc -c x.c", "file": "x.c"}
    ])
    assert len(load_compile_db(str(tmp_path))) == 1


def test_missing_db_raises(tmp_path):
    with pytest.raises(CompileDbError):
        load_compile_db(str(tmp_path / "nope"))


def test_best_entry_by_path_proximity(tmp_path):
    (tmp_path / "modA").mkdir()
    (tmp_path / "modB").mkdir()
    db = _write_db(tmp_path, [
        {
            "directory": str(tmp_path),
            "command": "g++ -IincA -c modA/a.cpp",
            "file": "modA/a.cpp",
        },
        {
            "directory": str(tmp_path),
            "command": "g++ -IincB -c modB/b.cpp",
            "file": "modB/b.cpp",
        },
    ])
    commands = load_compile_db(db)
    flags = flags_for(str(tmp_path / "modB" / "header.h"), commands)
    assert flags.include_dirs == [str(tmp_path / "incB")]


def test_dash_c_takes_no_value_and_dash_o_takes_one(tmp_path):
    # -c directly before a real flag must not swallow it; -o consumes
    # exactly its output path.
    db = _write_db(tmp_path, [{
        "directory": str(tmp_path),
        "command": "cc -c -Iinc -o out.o -DX=1 x.c",
        "file": "x.c",
    }])
    flags = flags_for(str(tmp_path / "x.c"), load_compile_db(db))
    assert flags.include_dirs == [str(tmp_path / "inc")]
    assert flags.defines == ["X=1"]


def test_sysroot_separate_and_joined_forms(tmp_path):
    db = _write_db(tmp_path, [
        {
            "directory": str(tmp_path),
            "arguments": ["cc", "--sysroot", "sr", "-c", "a.c"],
            "file": "a.c",
        },
        {
            "directory": str(tmp_path),
            "arguments": ["cc", "--sysroot=sr", "-c", "b.c"],
            "file": "b.c",
        },
    ])
    commands = load_compile_db(db)
    sr = str(tmp_path / "sr")
    flags_a = flags_for(str(tmp_path / "a.c"), commands)
    assert flags_a.extra_args == ["--sysroot", sr]
    flags_b = flags_for(str(tmp_path / "b.c"), commands)
    assert flags_b.extra_args == ["--sysroot=" + sr]


def test_response_file_expansion_and_missing_warning(tmp_path):
    (tmp_path / "flags.rsp").write_text("-Iinc -DRSP=1")
    db = _write_db(tmp_path, [
        {
            "directory": str(tmp_path),
            "command": "cc @flags.rsp -c a.c",
            "file": "a.c",
        },
        {
            "directory": str(tmp_path),
            "command": "cc @missing.rsp -c b.c",
            "file": "b.c",
        },
    ])
    commands = load_compile_db(db)
    flags_a = flags_for(str(tmp_path / "a.c"), commands)
    assert flags_a.include_dirs == [str(tmp_path / "inc")]
    assert flags_a.defines == ["RSP=1"]
    assert flags_a.warnings == []
    flags_b = flags_for(str(tmp_path / "b.c"), commands)
    assert any("missing.rsp" in w for w in flags_b.warnings)


def test_db_std_applies_and_explicit_std_wins(tmp_path):
    """std=None takes the database's -std=; an explicit std beats it."""
    header = tmp_path / "cpp20.h"
    header.write_text(textwrap.dedent("""\
        #pragma once
        namespace demo {
        struct Modern {
            int ok;
            char8_t c8;   // char8_t exists only in C++20
        };
        }
    """))
    (tmp_path / "cpp20.cpp").write_text('#include "cpp20.h"\n')
    db = _write_db(tmp_path, [{
        "directory": str(tmp_path),
        "command": "g++ -std=c++20 -c cpp20.cpp",
        "file": "cpp20.cpp",
    }])

    result = generate_pxd(
        str(header), extern_from="cpp20.h", namespaces=["demo"],
        compile_db=db,
    )
    assert "Modern" in result.text

    from cppast2autopxd.parser import ParseError

    with pytest.raises(ParseError):
        generate_pxd(
            str(header), extern_from="cpp20.h", namespaces=["demo"],
            std="c++14", compile_db=db,
        )


def test_db_warnings_surface_in_generation_result(tmp_path):
    header = tmp_path / "plain.h"
    header.write_text(
        "#pragma once\nnamespace demo { struct P { int v; }; }\n"
    )
    (tmp_path / "plain.cpp").write_text('#include "plain.h"\n')
    db = _write_db(tmp_path, [{
        "directory": str(tmp_path),
        "command": "g++ @gone.rsp -std=c++14 -c plain.cpp",
        "file": "plain.cpp",
    }])
    result = generate_pxd(
        str(header), extern_from="plain.h", namespaces=["demo"],
        compile_db=db,
    )
    assert "cdef struct P:" in result.text
    assert any("gone.rsp" in w for w in result.warnings)


def test_generation_driven_entirely_by_db(tmp_path):
    """No explicit include_dirs: the include path comes from the db."""
    inc = tmp_path / "include"
    inc.mkdir()
    (inc / "types_mini.h").write_text(textwrap.dedent("""\
        #pragma once
        namespace demo { typedef unsigned int handle_t; }
    """))
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    header = src_dir / "api.h"
    header.write_text(textwrap.dedent("""\
        #pragma once
        #include <types_mini.h>
        namespace demo {
        struct Api {
            handle_t handle;
        };
        }
    """))
    (src_dir / "api.cpp").write_text('#include "api.h"\n')
    # CMake writes forward-slash paths on every platform; mirror that so
    # the 'command' string stays shell-splittable on Windows too.
    db = _write_db(tmp_path, [{
        "directory": str(tmp_path),
        "command": f"g++ -I{inc.as_posix()} -DUNUSED=1 -std=c++17 -c src/api.cpp",
        "file": "src/api.cpp",
    }])

    result = generate_pxd(
        str(header), extern_from="api.h", namespaces=["demo"],
        compile_db=db,
    )
    assert "cdef struct Api:" in result.text
    # handle_t resolves (db include dir) -> canonical unsigned int
    assert "unsigned int handle" in result.text


CMAKE_AVAILABLE = (
    subprocess.run(
        ["cmake", "--version"], capture_output=True
    ).returncode == 0
)
import glob

PCL_ROOTS = sorted(glob.glob("/usr/include/pcl-*"))


@pytest.mark.skipif(
    not (CMAKE_AVAILABLE and PCL_ROOTS),
    reason="cmake or a system PCL install missing",
)
def test_real_pcl_via_cmake_compile_db(tmp_path):
    """The real-world loop: CMake configure exports compile_commands.json,
    and pxd generation for a REAL PCL header takes every flag from it."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "CMakeLists.txt").write_text(textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.16)
        project(dbprobe CXX)
        set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
        find_package(PCL REQUIRED COMPONENTS common)
        add_library(probe STATIC probe.cpp)
        target_include_directories(probe PRIVATE ${PCL_INCLUDE_DIRS})
        target_compile_definitions(probe PRIVATE ${PCL_DEFINITIONS})
        set_target_properties(probe PROPERTIES CXX_STANDARD 14)
    """))
    (proj / "probe.cpp").write_text(
        "#include <pcl/PCLHeader.h>\n"
        "pcl::PCLHeader h;\n"
    )
    build = tmp_path / "build"
    conf = subprocess.run(
        ["cmake", "-S", str(proj), "-B", str(build)],
        capture_output=True, text=True,
    )
    assert conf.returncode == 0, conf.stderr
    assert (build / "compile_commands.json").exists()

    header = os.path.join(PCL_ROOTS[-1], "pcl", "PCLHeader.h")
    result = generate_pxd(
        header,
        extern_from="pcl/PCLHeader.h",
        namespaces=["pcl"],
        compile_db=str(build),
    )
    assert "PCLHeader" in result.text

    (tmp_path / "pclheader.pxd").write_text(result.text)
    pyx = tmp_path / "use_db.pyx"
    pyx.write_text("from pclheader cimport PCLHeader\n")
    proc = subprocess.run(
        [sys.executable, "-m", "cython", "--cplus", "-3",
         "-I", str(tmp_path), str(pyx)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
