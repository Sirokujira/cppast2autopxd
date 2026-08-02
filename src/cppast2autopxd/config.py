"""TOML batch-generation config.

A single config file drives the whole pxd generation for a project.  All
relative paths resolve against the CONFIG FILE'S OWN DIRECTORY — for a
config living at ``pxdgen/pcl_headers.toml``::

    [generator]
    std = "c++14"
    include_dirs = ["headers"]              # -> pxdgen/headers
    defines = []
    nogil = true
    except_plus = true

    [typemap.substitutions."Eigen::Vector4f"]
    cython = "Vector4f"
    cimport = "from pcl.eigen cimport Vector4f"

    [[headers]]
    path = "headers/pcl/point_types.h"      # -> pxdgen/headers/pcl/...
    extern_from = "pcl/point_types.h"
    output = "../src/pcl/pxd/point_types.pxd"   # -> src/pcl/pxd/...
    namespaces = ["pcl"]
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from .typemap import Substitution


@dataclass
class HeaderJob:
    """One header -> one pxd."""

    path: str
    output: str
    extern_from: Optional[str] = None
    namespaces: List[str] = field(default_factory=list)
    include_names: List[str] = field(default_factory=list)
    exclude_names: List[str] = field(default_factory=list)
    extra_cimports: List[str] = field(default_factory=list)


@dataclass
class GeneratorConfig:
    std: str = "c++14"
    include_dirs: List[str] = field(default_factory=list)
    defines: List[str] = field(default_factory=list)
    extra_args: List[str] = field(default_factory=list)
    nogil: bool = True
    except_plus: bool = True
    substitutions: Dict[str, Substitution] = field(default_factory=dict)
    headers: List[HeaderJob] = field(default_factory=list)
    # Directory all relative paths resolve against.
    base_dir: str = "."


def load_config(path: str) -> GeneratorConfig:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    base_dir = os.path.dirname(os.path.abspath(path))
    gen = data.get("generator", {})
    cfg = GeneratorConfig(
        std=gen.get("std", "c++14"),
        include_dirs=[_resolve(base_dir, p) for p in gen.get("include_dirs", [])],
        defines=list(gen.get("defines", [])),
        extra_args=list(gen.get("extra_args", [])),
        nogil=bool(gen.get("nogil", True)),
        except_plus=bool(gen.get("except_plus", True)),
        base_dir=base_dir,
    )

    subs = data.get("typemap", {}).get("substitutions", {})
    for cpp_name, sub in subs.items():
        if isinstance(sub, str):
            cfg.substitutions[cpp_name] = Substitution(cython=sub)
        else:
            cfg.substitutions[cpp_name] = Substitution(
                cython=sub["cython"], cimport=sub.get("cimport")
            )

    for h in data.get("headers", []):
        cfg.headers.append(
            HeaderJob(
                path=_resolve(base_dir, h["path"]),
                output=_resolve(base_dir, h["output"]),
                extern_from=h.get("extern_from"),
                namespaces=list(h.get("namespaces", [])),
                include_names=list(h.get("include", [])),
                exclude_names=list(h.get("exclude", [])),
                extra_cimports=list(h.get("extra_cimports", [])),
            )
        )
    return cfg


def _resolve(base_dir: str, p: str) -> str:
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base_dir, p))
