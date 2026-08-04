"""Command line interface.

Single-header mode::

    cppast2autopxd path/to/header.hpp -o out.pxd -I include --namespace pcl

Batch mode driven by a TOML config::

    cppast2autopxd --config pxdgen/pcl_headers.toml
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import load_config
from .generator import (
    derive_pxd_module,
    generate_pxd,
    run_config,
    scaffold_collides,
)
from .parser import ParseError


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cppast2autopxd",
        description="Generate Cython .pxd declarations from C++ headers.",
    )
    p.add_argument("header", nargs="?", help="C++ header file to parse")
    p.add_argument("-o", "--output", help="output .pxd path (default: stdout)")
    p.add_argument(
        "--config", help="TOML config for batch generation (see docs)"
    )
    p.add_argument(
        "-I", dest="include_dirs", action="append", default=[],
        metavar="DIR", help="add an include search directory",
    )
    p.add_argument(
        "-D", dest="defines", action="append", default=[],
        metavar="MACRO[=VAL]", help="define a preprocessor macro",
    )
    p.add_argument(
        "--std", default=None,
        help="C++ standard (default: c++14, or the -std= of the matched "
             "entry when --compile-db is given; explicit values win)",
    )
    p.add_argument(
        "--language", choices=["c++", "c"], default="c++",
        help="input language; 'c' parses plain C headers "
             "(no except+, no distutils c++ line)",
    )
    p.add_argument(
        "--no-macros", action="store_true",
        help="do not export simple integer #define constants",
    )
    p.add_argument(
        "--compile-db", metavar="PATH",
        help="CMake compile_commands.json (or the build directory holding "
             "it); include dirs/defines/std/sysroot come from the best-"
             "matching entry",
    )
    p.add_argument(
        "--pyx-scaffold", metavar="PATH",
        help="also write a starting-point .pyx wrapper (refuses to "
             "overwrite an existing file)",
    )
    p.add_argument(
        "--pxd-module", metavar="NAME",
        help="cimport path of the generated pxd used inside the scaffold "
             "(default: the output pxd basename)",
    )
    p.add_argument(
        "--extern-from", metavar="HEADER",
        help='header path used in `cdef extern from "..."` '
             "(default: input basename)",
    )
    p.add_argument(
        "--namespace", dest="namespaces", action="append", default=[],
        help="only export this namespace (repeatable; default: all)",
    )
    p.add_argument(
        "--include-name", dest="include_names", action="append", default=[],
        help="only export entities with this name (repeatable)",
    )
    p.add_argument(
        "--exclude-name", dest="exclude_names", action="append", default=[],
        help="skip entities with this name (repeatable)",
    )
    p.add_argument(
        "--no-nogil", action="store_true",
        help="do not mark extern blocks nogil",
    )
    p.add_argument(
        "--no-except-plus", action="store_true",
        help="do not append `except +` to signatures",
    )
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if bool(args.config) == bool(args.header):
        print(
            "error: pass exactly one of a header file or --config",
            file=sys.stderr,
        )
        return 2

    try:
        if args.config:
            run_config(load_config(args.config))
            return 0

        if args.pyx_scaffold and args.output and scaffold_collides(
            args.pyx_scaffold, args.output
        ):
            print(
                f"error: --pyx-scaffold {args.pyx_scaffold} and -o "
                f"{args.output} would form the same Cython module; "
                "name the scaffold differently (e.g. _wrap.pyx)",
                file=sys.stderr,
            )
            return 2

        result = generate_pxd(
            args.header,
            extern_from=args.extern_from,
            include_dirs=args.include_dirs,
            defines=args.defines,
            std=args.std,
            language=args.language,
            macros=not args.no_macros,
            namespaces=args.namespaces,
            include_names=args.include_names,
            exclude_names=args.exclude_names,
            nogil=not args.no_nogil,
            except_plus=False if args.no_except_plus else None,
            compile_db=args.compile_db,
        )
    except (ParseError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(result.text)
    else:
        sys.stdout.write(result.text)

    if args.pyx_scaffold:
        import os

        if os.path.exists(args.pyx_scaffold):
            print(
                f"error: scaffold target exists, not overwriting: "
                f"{args.pyx_scaffold}",
                file=sys.stderr,
            )
            return 1
        from .pyx_scaffold import render_scaffold

        if args.pxd_module:
            pxd_module = args.pxd_module
        elif args.output:
            pxd_module = derive_pxd_module(args.output)
        else:
            pxd_module = os.path.splitext(os.path.basename(args.header))[0]
        text = render_scaffold(
            result.module,
            pxd_module,
            args.extern_from or os.path.basename(args.header),
        )
        with open(args.pyx_scaffold, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
