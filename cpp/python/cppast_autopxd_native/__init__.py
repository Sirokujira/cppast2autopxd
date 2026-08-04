"""cppast_autopxd_native: the cppast-based C++ pxd generator, pip-packaged.

The native ``cppast_autopxd`` binary is built by scikit-build + CMake at
install time and shipped inside this package. Use :func:`tool_path` to
locate it programmatically, or the ``cppast-autopxd`` console script to run
it directly:

    cppast-autopxd header.h --output_dir out --xml_dir "" --std c++14
"""

from __future__ import annotations

import os
import subprocess
import sys

__version__ = "0.0.2"

__all__ = ["tool_path", "run", "main", "__version__"]


def tool_path() -> str:
    """Absolute path of the packaged ``cppast_autopxd`` binary."""
    exe = "cppast_autopxd.exe" if os.name == "nt" else "cppast_autopxd"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), exe)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"packaged cppast_autopxd binary not found at {path}; "
            "the wheel was built without the native tool"
        )
    return path


def run(args, **kwargs) -> "subprocess.CompletedProcess":
    """Run the native tool with *args* (a list of CLI arguments)."""
    return subprocess.run([tool_path(), *args], **kwargs)


def main(argv=None) -> int:
    """Console-script entry point: forward argv to the native binary."""
    argv = list(sys.argv[1:] if argv is None else argv)
    return subprocess.call([tool_path(), *argv])
