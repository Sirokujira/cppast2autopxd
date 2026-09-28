"""cppast2autopxd: generate Cython .pxd declarations from C++ headers.

The default parser backend is libclang (the same infrastructure the cppast
C++ library builds on); the emitter produces ``cdef extern from`` blocks
suitable for wrapping C++ libraries such as PCL with Cython.  A second
backend, :func:`generate_pxd_cppast`, delegates to the ``cppast_autopxd``
binary (the C++ implementation in ``cpp/``, built on the real cppast
library) — see :mod:`cppast2autopxd.cppast_backend` for what it can and
cannot honor.
"""

__version__ = "0.1.0"

from .generator import generate_pxd, run_config  # noqa: E402,F401
from .config import load_config  # noqa: E402,F401
from .cppast_backend import (  # noqa: E402,F401
    find_cppast_tool,
    generate_pxd_cppast,
)

__all__ = [
    "generate_pxd", "generate_pxd_cppast", "find_cppast_tool",
    "run_config", "load_config", "__version__",
]
