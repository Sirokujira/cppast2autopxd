"""cppast-based generation backend.

The connection this package's IR docs anticipated: ``cppast_autopxd`` (the
C++ implementation in ``cpp/``, built on the real cppast library) has grown
an option surface that mirrors this package's — ``--extra_cimport`` /
``--typemap`` are the counterparts of ``extra_cimports`` and the typemap's
substitutions — so a header can be generated through cppast by delegating
to that binary and adapting options and warnings at the boundary.

This is deliberately a DELEGATION backend, not the IR-level AST-dump parser
:mod:`cppast2autopxd.ir` once imagined: the C++ tool's emission is a token
pipeline with no externalizable IR, and re-parsing its human-oriented dump
would be a second fragile parser.  Delegation keeps one source of truth per
implementation and connects them at the interface both actually share.

``extern_from``, ``nogil`` and ``except_plus`` map onto the tool's
``--extern_from`` / ``--no_nogil`` / ``--except_plus`` (FEASIBILITY #54),
which is what lets this backend produce the declarations
python-pcl_skbuild's pipeline needs: mirror header in, real PCL include
path out, C++ exceptions propagating.

Differences a caller must know (they raise, never silently degrade):

- name filtering (``namespaces``/``include_names``/``exclude_names``),
  ``macros`` and custom banners have no counterpart flags.

Discovery is environment-driven (never a hard-coded path):
``CPPAST2AUTOPXD_CPP_TOOL``, then ``cppast-autopxd`` on PATH, then the
installed ``cppast_autopxd_native`` wheel package.
"""

import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

from .generator import GenerationResult

__all__ = ["find_cppast_tool", "generate_pxd_cppast"]


def find_cppast_tool() -> Optional[str]:
    """Locate the cppast_autopxd binary, or None when unavailable."""
    explicit = os.environ.get("CPPAST2AUTOPXD_CPP_TOOL")
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    on_path = shutil.which("cppast-autopxd")
    if on_path:
        return on_path
    try:
        import cppast_autopxd_native  # type: ignore
    except ImportError:
        return None
    pkg_dir = os.path.dirname(cppast_autopxd_native.__file__)
    for name in ("cppast_autopxd", "cppast_autopxd.exe"):
        candidate = os.path.join(pkg_dir, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def generate_pxd_cppast(
    header: str,
    *,
    tool: Optional[str] = None,
    include_dirs: Optional[List[str]] = None,
    defines: Optional[List[str]] = None,
    std: Optional[str] = None,
    substitutions: Optional[Dict[str, str]] = None,
    extra_cimports: Optional[List[str]] = None,
    fast_preprocessing: bool = False,
    config: Optional[str] = None,
    extern_from: Optional[str] = None,
    nogil: bool = True,
    except_plus: bool = False,
) -> GenerationResult:
    """Generate pxd text for one header through the cppast_autopxd binary.

    Returns the same :class:`GenerationResult` shape as
    :func:`cppast2autopxd.generate_pxd` (``module`` is ``None`` — there is
    no Python-side IR on this path, so the pyx scaffolder cannot consume
    the result).  Warnings collect the tool's stderr ``warning:`` lines and
    every ``# skipped:`` comment in the output, keeping the never-silent
    contract visible to the caller.

    ``nogil`` and ``except_plus`` default to the C++ tool's own defaults
    (nogil on, except+ off), NOT to :class:`EmitOptions`' — a caller
    porting a libclang configuration passes both explicitly.
    """
    tool = tool or find_cppast_tool()
    if tool is None:
        raise RuntimeError(
            "cppast_autopxd binary not found (set CPPAST2AUTOPXD_CPP_TOOL, "
            "put cppast-autopxd on PATH, or pip install ./cpp)"
        )

    outdir = tempfile.mkdtemp(prefix="cppast_backend_")
    try:
        argv = [tool, "--output_dir", outdir, "--xml_dir", "",
                "--std", std or "c++14"]
        if fast_preprocessing:
            argv.append("--fast_preprocessing")
        for d in include_dirs or []:
            argv += ["-I", d]
        for d in defines or []:
            argv += ["-D", d]
        for line in extra_cimports or []:
            argv += ["--extra_cimport", line]
        for frm, to in (substitutions or {}).items():
            argv += ["--typemap", f"{frm}={to}"]
        if config:
            argv += ["--config", config]
        if extern_from:
            argv += ["--extern_from", extern_from]
        if not nogil:
            argv.append("--no_nogil")
        if except_plus:
            argv.append("--except_plus")
        argv.append(header)

        proc = subprocess.run(argv, capture_output=True, text=True)
        # Two diagnostic formats reach stderr: the tool's own messages
        # (`warning: ignoring malformed --typemap ...`) and cppast/libclang's
        # bracketed logger (`[preprocessor] [warning] ...`, `[libclang]
        # [error] ...` — a parse can degrade and still exit 0). Both must
        # surface, or a degraded run comes back with an empty warning list.
        stderr_warnings = [
            line.strip() for line in proc.stderr.splitlines()
            if "warning:" in line or "[warning]" in line or "[error]" in line
        ]
        if proc.returncode != 0:
            tail = "\n".join(proc.stderr.splitlines()[-8:])
            raise RuntimeError(
                f"cppast_autopxd failed (exit {proc.returncode}) on "
                f"{header}:\n{tail}"
            )

        name = os.path.splitext(os.path.basename(header))[0]
        pxd_path = os.path.join(outdir, name + ".pxd")
        if not os.path.isfile(pxd_path):
            raise RuntimeError(
                f"cppast_autopxd exited 0 but wrote no {name}.pxd for "
                f"{header}"
            )
        with open(pxd_path) as fh:
            text = fh.read()
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    skip_warnings = [
        m.group(1).strip()
        for m in re.finditer(r"# skipped:(.+)", text)
    ]
    warnings = stderr_warnings + [
        f"skipped: {w}" for w in skip_warnings
    ]
    return GenerationResult(text=text, warnings=warnings, module=None)
