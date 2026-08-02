"""cppast2autopxd: generate Cython .pxd declarations from C++ headers.

The parser backend is libclang (the same infrastructure the cppast C++
library builds on); the emitter produces ``cdef extern from`` blocks suitable
for wrapping C++ libraries such as PCL with Cython.
"""

__version__ = "0.1.0"

from .generator import generate_pxd, run_config  # noqa: E402,F401
from .config import load_config  # noqa: E402,F401

__all__ = ["generate_pxd", "run_config", "load_config", "__version__"]
