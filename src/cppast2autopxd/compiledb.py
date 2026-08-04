"""compile_commands.json (CMake compilation database) support.

CMake writes a compilation database when configured with
``-DCMAKE_EXPORT_COMPILE_COMMANDS=ON``. Every entry records the exact
compiler invocation for one translation unit — include directories,
defines, the language standard, sysroot — which is precisely what header
parsing needs. This module lets the generator take ALL of that from the
database instead of hand-maintained ``include_dirs``/``defines`` lists:

    cppast2autopxd pcl/point_types.h --compile-db build/ --namespace pcl

Headers themselves do not appear in a compilation database (only .c/.cpp
TUs do), so flags are taken from the best-matching source entry: the one
whose file/directory shares the longest path prefix with the requested
header — same-target sources sit in the same directory subtree and carry
the right flags. Falling back to the first entry still beats guessing:
CMake projects overwhelmingly share one flag set per target tree.
"""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass, field
from typing import List, Optional


class CompileDbError(Exception):
    """Raised when the database cannot be loaded or is empty."""


@dataclass
class CompileCommand:
    """One entry of the database, with args normalized to a list."""

    file: str          # absolute path of the TU
    directory: str     # working directory of the invocation
    args: List[str]    # full argv (compiler included)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExtractedFlags:
    """Parse-relevant flags recovered from a compile command."""

    include_dirs: List[str] = field(default_factory=list)
    defines: List[str] = field(default_factory=list)
    std: Optional[str] = None
    # -isystem/-isysroot/--sysroot and friends, passed through verbatim.
    extra_args: List[str] = field(default_factory=list)
    source_file: str = ""
    warnings: List[str] = field(default_factory=list)


def load_compile_db(path: str) -> List[CompileCommand]:
    """Load a compilation database.

    *path* may be the ``compile_commands.json`` file itself or a directory
    containing one (e.g. a CMake build directory).
    """
    if os.path.isdir(path):
        path = os.path.join(path, "compile_commands.json")
    if not os.path.isfile(path):
        raise CompileDbError(f"compilation database not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as err:
            raise CompileDbError(f"invalid JSON in {path}: {err}") from err

    commands: List[CompileCommand] = []
    for entry in raw:
        directory = entry.get("directory", ".")
        file_path = entry.get("file", "")
        if not os.path.isabs(file_path):
            file_path = os.path.normpath(os.path.join(directory, file_path))
        if "arguments" in entry:
            args = list(entry["arguments"])
        elif "command" in entry:
            args = _split_command(entry["command"])
        else:
            continue
        args, warnings = _expand_response_files(args, directory)
        commands.append(
            CompileCommand(
                file=file_path, directory=directory, args=args,
                warnings=warnings,
            )
        )
    if not commands:
        raise CompileDbError(f"compilation database is empty: {path}")
    return commands


def _split_command(command: str) -> List[str]:
    """Split a 'command'-form entry into argv.

    POSIX shlex treats backslashes as escapes, which destroys Windows
    paths (``C:\\Users\\...``); split in non-POSIX mode there and strip
    the quotes shlex then leaves on quoted tokens.
    """
    if os.name == "nt":
        parts = shlex.split(command, posix=False)
        return [
            p[1:-1]
            if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'"
            else p
            for p in parts
        ]
    return shlex.split(command)


def _expand_response_files(args, directory):
    """Expand ``@file.rsp`` arguments (CMake/Ninja long-command-line form).

    Unreadable response files surface as warnings — flags silently lost to
    an unexpanded @file would otherwise yield confusing parse failures or
    silently wrong output.
    """
    out: List[str] = []
    warnings: List[str] = []
    for arg in args:
        if not arg.startswith("@") or len(arg) < 2:
            out.append(arg)
            continue
        rsp_path = _resolve(directory, arg[1:])
        try:
            with open(rsp_path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as err:
            warnings.append(
                f"compile db: response file {arg!r} could not be read "
                f"({err}); its flags are missing"
            )
            continue
        out.extend(_split_command(content))
    return out, warnings


def flags_for(header: str, commands: List[CompileCommand]) -> ExtractedFlags:
    """Extract parse flags from the entry best matching *header*."""
    best = max(
        commands,
        key=lambda c: _common_prefix_len(
            os.path.realpath(header), os.path.realpath(c.file)
        ),
    )
    return _extract(best)


def _common_prefix_len(a: str, b: str) -> int:
    a_parts = a.replace("\\", "/").split("/")
    b_parts = b.replace("\\", "/").split("/")
    n = 0
    for x, y in zip(a_parts, b_parts):
        if x != y:
            break
        n += 1
    return n


def _extract(cmd: CompileCommand) -> ExtractedFlags:
    out = ExtractedFlags(
        source_file=cmd.file, warnings=list(cmd.warnings)
    )
    args = cmd.args[1:]  # drop the compiler executable
    i = 0
    while i < len(args):
        arg = args[i]

        def _value() -> str:
            nonlocal i
            i += 1
            return args[i] if i < len(args) else ""

        if arg == "-I":
            out.include_dirs.append(_resolve(cmd.directory, _value()))
        elif arg.startswith("-I"):
            out.include_dirs.append(_resolve(cmd.directory, arg[2:]))
        elif arg == "-D":
            out.defines.append(_value())
        elif arg.startswith("-D"):
            out.defines.append(arg[2:])
        elif arg == "-U" or arg == "-include":
            flag, value = arg, _value()
            out.extra_args += [flag, _resolve(cmd.directory, value)
                               if flag == "-include" else value]
        elif arg.startswith("-std="):
            out.std = arg[len("-std="):]
        elif arg in ("-isystem", "-isysroot"):
            out.extra_args += [arg, _resolve(cmd.directory, _value())]
        elif arg == "--sysroot":
            # clang's separate-argument spelling
            out.extra_args += [arg, _resolve(cmd.directory, _value())]
        elif arg.startswith("--sysroot="):
            out.extra_args.append(
                "--sysroot="
                + _resolve(cmd.directory, arg[len("--sysroot="):])
            )
        elif arg.startswith("--target=") or arg.startswith("-target"):
            if arg == "-target":
                out.extra_args += [arg, _value()]
            else:
                out.extra_args.append(arg)
        elif arg == "-o":
            i += 1  # -o takes a value; irrelevant for parsing
        elif arg == "-c":
            pass    # compile-only marker: takes NO value
        # everything else (warnings, optimization, deps generation, the
        # source file itself) is irrelevant for header parsing
        i += 1
    return out


def _resolve(directory: str, p: str) -> str:
    if not p or os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(directory, p))
