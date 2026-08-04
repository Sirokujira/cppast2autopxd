"""setup.py - build the miniz_py extension: real miniz C lib + Cython wrapper.

Project metadata is in pyproject.toml. The cimported miniz.pxd is auto-generated
by cppast_autopxd from src/miniz.h (regenerate with ./gen.sh).

Build:  python -m pip install .            (PEP 517, isolated)
   or:  python setup.py build_ext --inplace
"""
from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        name="miniz_py",
        sources=["miniz_py.pyx", "src/miniz.c"],
        include_dirs=["src", "."],   # src/ for miniz.h, . for miniz.pxd
        language="c++",
    )
]

setup(
    # Top-level extension only — no Python packages. Without this, setuptools
    # auto-discovers src/ as a package and `build_ext --inplace` drops the .so
    # into src/ instead of the project root.
    packages=[],
    py_modules=[],
    ext_modules=cythonize(extensions, language_level="3"),
)
