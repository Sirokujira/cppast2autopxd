#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""scikit-build packaging for the cppast-based C++ pxd generator.

`pip install .` (from this cpp/ directory) configures CMake, builds the
`cppast_autopxd` binary (fetching the cppast sources automatically when
.deps/cppast is absent), and ships it inside the cppast_autopxd_native
package with a `cppast-autopxd` console script.

Requires LLVM/libclang development files: apt `llvm-dev libclang-dev clang`,
brew `llvm`, or an `LLVM_CONFIG_BINARY`/`CPPAST_DIR` handed through
CMAKE_ARGS. Build layout follows sirokujira/cython-scikit-build-template.
"""
import os
import platform

from skbuild import setup

cmake_args = []
# Same discovery contract as bootstrap.sh: honor LLVM_PREFIX when set, and
# never hard-code machine paths.
llvm_prefix = os.environ.get("LLVM_PREFIX", "")
if llvm_prefix:
    cmake_args.append(
        "-DLLVM_CONFIG_BINARY=" + os.path.join(llvm_prefix, "bin", "llvm-config")
    )
elif platform.system() == "Darwin":
    for keg in ("/opt/homebrew/opt/llvm", "/usr/local/opt/llvm"):
        candidate = os.path.join(keg, "bin", "llvm-config")
        if os.path.exists(candidate):
            cmake_args.append("-DLLVM_CONFIG_BINARY=" + candidate)
            break

setup(
    name="cppast-autopxd",
    version="0.0.2",
    description="C/C++ header -> Cython .pxd generator "
                "(cppast/libclang C++ implementation)",
    long_description=open("FEASIBILITY.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/sirokujira/cppast2autopxd",
    author="Tooru Oonuma",
    author_email="t753github@gmail.com",
    license="MIT",
    packages=["cppast_autopxd_native"],
    package_dir={"": "python"},
    cmake_install_dir="python/cppast_autopxd_native",
    cmake_args=cmake_args,
    entry_points={
        "console_scripts": [
            "cppast-autopxd = cppast_autopxd_native:main",
        ]
    },
    zip_safe=False,
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: C++",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Code Generators",
    ],
)
