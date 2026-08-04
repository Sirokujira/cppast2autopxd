"""Generate a STARTING-POINT ``.pyx`` wrapper from the lowered IR.

A ``.pxd`` is a mechanical projection of C/C++ declarations, so it can be
fully generated. A ``.pyx`` wrapper is a DESIGN artifact — ownership,
error handling, and a pythonic API are human decisions — so full
automation is out of scope. What CAN be automated is the boilerplate
starting point: a wrapper class per concrete C++ class holding an owned
pointer, constructor/destructor plumbing, and direct forwarding for every
method whose signature only uses primitive/string types. Everything else
is emitted as a TODO comment so the scaffold always compiles.

The scaffolder never overwrites an existing file: a scaffold is generated
once and then owned by humans.
"""

from __future__ import annotations

from typing import List, Optional, Set

from . import ir

#: Types a scaffold can forward without conversion glue.
_SIMPLE_TYPES = {
    "int", "long", "long long", "short", "char",
    "unsigned", "unsigned int", "unsigned long", "unsigned long long",
    "unsigned short", "unsigned char", "signed char",
    "float", "double", "long double",
    "size_t", "ptrdiff_t", "bint", "bool",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "void",
}


def _is_simple(type_str: str) -> bool:
    t = type_str.strip()
    for prefix in ("const ",):
        if t.startswith(prefix):
            t = t[len(prefix):]
    t = t.rstrip("&").strip()
    if t.endswith("*"):
        return False
    return t in _SIMPLE_TYPES or t == "string"


def _uses_string(type_str: str) -> bool:
    return type_str.strip().rstrip("&").strip().removeprefix("const ").strip() == "string"


#: stdint spellings that need a libc.stdint cimport in the pyx.
_STDINT_TYPES = {
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
}


def _base_type(type_str: str) -> str:
    t = type_str.strip()
    if t.startswith("const "):
        t = t[len("const "):]
    return t.rstrip("&").strip()


def _cy_param_type(type_str: str) -> str:
    """Cython parameter declaration type for a simple C++ type."""
    t = _base_type(type_str)
    if t == "string":
        return "str"
    if t == "bool":
        return "bint"
    return t


def render_scaffold(
    module: ir.Module,
    pxd_module: str,
    header_name: str,
) -> str:
    """Render the scaffold pyx text for *module*.

    *pxd_module* is the cimport path of the generated pxd (e.g.
    ``point_types`` or ``pcl.pxd.point_types``).
    """
    classes: List[ir.Class] = []
    for block in module.blocks:
        for entity in block.entities:
            if isinstance(entity, ir.Class) and not entity.is_union:
                classes.append(entity)

    out: List[str] = []
    out.append("# distutils: language = c++")
    out.append("# cython: language_level=3")
    out.append('"""')
    out.append(f"STARTING-POINT wrapper for {header_name}, scaffolded by")
    out.append("cppast2autopxd. Unlike the pxd, this file is YOURS: refine")
    out.append("the API, add conversions, and delete what you do not need.")
    out.append("Re-running the scaffolder never overwrites this file.")
    out.append('"""')
    out.append("")
    out.append(f"cimport {pxd_module} as cpp")
    if _module_uses_string(classes):
        out.append("from libcpp.string cimport string")
    stdints = _module_stdint_types(classes)
    if stdints:
        out.append(
            "from libc.stdint cimport " + ", ".join(sorted(stdints))
        )
    out.append("")

    emitted_any = False
    for cls in classes:
        rendered = _render_class(cls)
        if rendered:
            out.extend(rendered)
            out.append("")
            emitted_any = True

    if not emitted_any:
        out.append("# No scaffoldable classes were found in this header.")
        out.append("# (Templates and PODs are declared in the pxd; use them")
        out.append("#  from your own cdef code.)")
    return "\n".join(out).rstrip() + "\n"


def _module_stdint_types(classes: List[ir.Class]) -> Set[str]:
    used: Set[str] = set()
    for cls in classes:
        for m in cls.methods:
            for p in m.params:
                if _base_type(p.type) in _STDINT_TYPES:
                    used.add(_base_type(p.type))
        for c in cls.constructors:
            for p in c.params:
                if _base_type(p.type) in _STDINT_TYPES:
                    used.add(_base_type(p.type))
    return used


def _module_uses_string(classes: List[ir.Class]) -> bool:
    for cls in classes:
        for m in cls.methods:
            if _uses_string(m.return_type) or any(
                _uses_string(p.type) for p in m.params
            ):
                return True
        for c in cls.constructors:
            if any(_uses_string(p.type) for p in c.params):
                return True
    return False


def _render_class(cls: ir.Class) -> Optional[List[str]]:
    if cls.template_params:
        return [
            f"# TODO: {cls.name} is a class template "
            f"({', '.join(cls.template_params)}).",
            "# Pick concrete instantiations and wrap each one, e.g.:",
            f"#   cdef class {cls.name}_double:",
            f"#       cdef cpp.{cls.name}[double]* thisptr",
        ]
    if cls.is_pod_struct:
        return [
            f"# {cls.name} is a plain struct: usable directly from cdef",
            f"# code (cdef cpp.{cls.name} value). Wrap it in a cdef class",
            "# only if Python-level access is needed.",
        ]

    lines: List[str] = []
    lines.append(f"cdef class {cls.name}:")
    lines.append(f'    """Wraps C++ {cls.name} (owned pointer)."""')
    lines.append(f"    cdef cpp.{cls.name}* thisptr")
    lines.append("")

    # constructor: prefer the first fully-simple one
    ctor = _pick_ctor(cls)
    if ctor is not None:
        args = _py_params(ctor.params)
        call = ", ".join(p.name or f"arg{i}" for i, p in enumerate(ctor.params))
        lines.append(f"    def __cinit__(self{args}):")
        lines.append(f"        self.thisptr = new cpp.{cls.name}({call})")
    else:
        lines.append("    def __cinit__(self):")
        lines.append(f"        # TODO: no constructor with only simple-typed")
        lines.append(f"        # parameters was found; construct explicitly.")
        lines.append(f"        self.thisptr = NULL")
    lines.append("")
    lines.append("    def __dealloc__(self):")
    lines.append("        if self.thisptr != NULL:")
    lines.append("            del self.thisptr")
    lines.append("")

    seen: Set[str] = set()
    for m in cls.methods:
        if m.is_static or m.is_operator or m.name in seen:
            continue
        seen.add(m.name)
        simple = (
            not m.params or all(p.raw is None and p.type != "..." and
                                _is_simple(p.type) for p in m.params)
        ) and (_is_simple(m.return_type))
        if simple:
            args = _py_params(m.params)
            call = ", ".join(
                _to_cpp_arg(p, i) for i, p in enumerate(m.params)
            )
            ret = "" if m.return_type.strip() == "void" else "return "
            expr = f"self.thisptr.{m.name}({call})"
            if _uses_string(m.return_type):
                expr = f"(<bytes> {expr}).decode()"
            lines.append(f"    def {m.name}(self{args}):")
            lines.append(f"        {ret}{expr}")
        else:
            sig_hint = ", ".join(p.raw or p.type for p in m.params)
            lines.append(
                f"    # TODO: wrap {m.return_type} {m.name}({sig_hint})"
            )
    return lines


def _pick_ctor(cls: ir.Class) -> Optional[ir.Constructor]:
    best = None
    for ctor in cls.constructors:
        if all(p.raw is None and _is_simple(p.type) for p in ctor.params):
            if best is None or len(ctor.params) > len(best.params):
                best = ctor
    return best


def _py_params(params: List[ir.Param]) -> str:
    parts = []
    for i, p in enumerate(params):
        name = p.name or f"arg{i}"
        # C-typed parameters both disambiguate C++ overloads and document
        # the expected Python types.
        parts.append(f"{_cy_param_type(p.type)} {name}")
    return (", " + ", ".join(parts)) if parts else ""


def _to_cpp_arg(p: ir.Param, i: int) -> str:
    name = p.name or f"arg{i}"
    if _uses_string(p.type):
        return f"<string> {name}.encode()"
    return name
