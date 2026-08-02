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
from .generator import generate_pxd, run_config
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
    p.add_argument("--std", default="c++14", help="C++ standard (default: c++14)")
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

        result = generate_pxd(
            args.header,
            extern_from=args.extern_from,
            include_dirs=args.include_dirs,
            defines=args.defines,
            std=args.std,
            namespaces=args.namespaces,
            include_names=args.include_names,
            exclude_names=args.exclude_names,
            nogil=not args.no_nogil,
            except_plus=not args.no_except_plus,
        )
    except ParseError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(result.text)
    else:
        sys.stdout.write(result.text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
