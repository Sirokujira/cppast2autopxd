"""IR -> Cython ``.pxd`` text emitter."""

from __future__ import annotations

import keyword
from dataclasses import dataclass
from typing import List, Set

from . import ir

_INDENT = "    "


@dataclass
class EmitOptions:
    """Options controlling pxd rendering."""

    # Add `nogil` to every extern block (methods stay callable without the GIL).
    nogil: bool = True
    # Add `except +` to functions/methods/constructors so C++ exceptions
    # propagate as Python exceptions instead of terminating the process.
    except_plus: bool = True
    # C++ mode: emit the `# distutils: language = c++` header. False for
    # plain C headers.
    cplus: bool = True
    # Extra verbatim cimport lines (from user config).
    extra_cimports: List[str] = None
    # Banner comment; set to "" to disable.
    banner: str = ""

    def __post_init__(self):
        if self.extra_cimports is None:
            self.extra_cimports = []


def emit_module(
    module: ir.Module, cimports: Set[str], options: EmitOptions
) -> str:
    """Render a :class:`ir.Module` (plus collected cimports) as pxd text."""
    out: List[str] = []
    if options.banner:
        for line in options.banner.splitlines():
            out.append(f"# {line}".rstrip())
        out.append("")
    if options.cplus:
        out.append("# distutils: language = c++")
        out.append("")

    all_cimports = sorted(set(cimports) | set(options.extra_cimports))
    if all_cimports:
        out.extend(all_cimports)
        out.append("")

    for block in module.blocks:
        if not block.entities:
            continue
        out.extend(_emit_block(module.extern_from, block, options))
        out.append("")

    text = "\n".join(out).rstrip() + "\n"
    return text


def _emit_block(
    extern_from: str, block: ir.NamespaceBlock, options: EmitOptions
) -> List[str]:
    header = f'cdef extern from "{extern_from}"'
    if block.namespace:
        header += f' namespace "{block.namespace}"'
    if options.nogil:
        header += " nogil"
    header += ":"
    lines = [header]
    for i, entity in enumerate(block.entities):
        if i:
            lines.append("")
        lines.extend(_emit_entity(entity, options))
    return lines


def _emit_entity(entity, options: EmitOptions) -> List[str]:
    if isinstance(entity, ir.Class):
        return _emit_class(entity, options, indent=1)
    if isinstance(entity, ir.Enum):
        return _emit_enum(entity, indent=1)
    if isinstance(entity, ir.Typedef):
        if entity.raw:
            return [f"{_INDENT}ctypedef {entity.raw}"]
        return [f"{_INDENT}ctypedef {entity.underlying} {entity.name}"]
    if isinstance(entity, ir.Function):
        name = entity.name
        if entity.template_params:
            name += "[" + ", ".join(entity.template_params) + "]"
        return [
            _INDENT + sig
            for sig in _signatures(entity.return_type, name,
                                   entity.params, options)
        ]
    if isinstance(entity, ir.Variable):
        return [f"{_INDENT}{entity.type} {entity.name}"]
    raise TypeError(f"cannot emit {entity!r}")


def _emit_class(cls: ir.Class, options: EmitOptions, indent: int) -> List[str]:
    # `cdef` only introduces TOP-LEVEL declarations inside the extern block;
    # nested declarations (indent > 1) must omit it or Cython errors out.
    top = indent == 1
    cdef = "cdef " if top else ""
    pad = _INDENT * indent
    body_pad = _INDENT * (indent + 1)
    lines: List[str] = []

    name = cls.name
    if cls.template_params:
        name += "[" + ", ".join(cls.template_params) + "]"
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""

    if cls.is_union:
        lines.append(f"{pad}{cdef}union {name}:")
        if not cls.fields:
            lines.append(f"{body_pad}pass")
        for f in cls.fields:
            lines.append(body_pad + _field_decl(f))
        return lines

    if cls.is_pod_struct and not cls.bases:
        lines.append(f"{pad}{cdef}struct {name}:")
        if not cls.fields:
            lines.append(f"{body_pad}pass")
        for f in cls.fields:
            lines.append(body_pad + _field_decl(f))
        return lines

    lines.append(f"{pad}{cdef}cppclass {name}{bases}:")
    body: List[str] = []

    # Declare-before-use order: nested types first, then the typedefs that
    # commonly alias them, then constructors/fields/methods.  (C++ allows
    # members to reference types declared later in the class; Cython does
    # not, so kind-ordering is safer than source order.)
    for enum in cls.enums:
        body.extend(_emit_enum(enum, indent + 1))
    for nested in cls.nested_classes:
        body.extend(_emit_class(nested, options, indent + 1))
    for td in cls.typedefs:
        if td.raw:
            body.append(f"{body_pad}ctypedef {td.raw}")
        else:
            body.append(f"{body_pad}ctypedef {td.underlying} {td.name}")
    for ctor in cls.constructors:
        for sig in _signatures("", cls.name, ctor.params, options):
            body.append(body_pad + sig)
    for f in cls.fields:
        body.append(body_pad + _field_decl(f))
    for m in cls.methods:
        name = m.name
        if m.template_params:
            name += "[" + ", ".join(m.template_params) + "]"
        for sig in _signatures(m.return_type, name, m.params, options,
                               is_const=m.is_const):
            if m.is_static:
                body.append(f"{body_pad}@staticmethod")
            body.append(body_pad + sig)

    if not body:
        body.append(f"{body_pad}pass")
    lines.extend(body)
    return lines


def _emit_enum(enum: ir.Enum, indent: int) -> List[str]:
    top = indent == 1
    pad = _INDENT * indent
    body_pad = _INDENT * (indent + 1)
    kw = "enum class" if enum.is_scoped else "enum"
    if top:
        kw = "cdef " + kw
    name = f" {enum.name}" if enum.name else ""
    lines = [f"{pad}{kw}{name}:"]
    if not enum.items:
        lines.append(f"{body_pad}pass")
    for item in enum.items:
        if item.value is not None:
            lines.append(f"{body_pad}{item.name} = {item.value}")
        else:
            lines.append(f"{body_pad}{item.name}")
    return lines


def _field_decl(f: ir.Field) -> str:
    if f.raw:
        return f.raw
    dims = "".join(f"[{d}]" for d in f.array_dims)
    return f"{f.type} {f.name}{dims}"


def _signatures(
    return_type: str,
    name: str,
    params: List[ir.Param],
    options: EmitOptions,
    is_const: bool = False,
) -> List[str]:
    """Render one C++ signature as one or more Cython declarations.

    C++ default arguments have no direct pxd syntax (`=*` is reserved for
    template parameter defaults), so a signature with trailing defaults is
    expanded into overloads with the defaulted parameters dropped - the same
    convention Cython's own libcpp declarations use.
    """
    first_default = len(params)
    for i, p in enumerate(params):
        if p.has_default:
            first_default = i
            break

    variants = []
    for count in range(first_default, len(params) + 1):
        variants.append(_one_signature(
            return_type, name, params[:count], options, is_const
        ))
    return variants


def _one_signature(
    return_type: str,
    name: str,
    params: List[ir.Param],
    options: EmitOptions,
    is_const: bool,
) -> str:
    rendered = []
    for p in params:
        if p.raw:
            rendered.append(p.raw)
            continue
        if p.type == "...":
            rendered.append("...")
            continue
        part = p.type
        if p.name:
            # Parameter names in extern declarations are documentation
            # only, but Cython still parses them: Python keywords (legal
            # C++ names like `from`) must be renamed.
            pname = p.name + "_" if keyword.iskeyword(p.name) else p.name
            part += f" {pname}"
        part += "".join(f"[{d}]" for d in p.array_dims)
        rendered.append(part)
    sig = f"{name}({', '.join(rendered)})"
    if return_type:
        sig = f"{return_type} {sig}"
    # Cython's grammar rejects `const` combined with `except +` (in either
    # order), so exception propagation wins; the const qualifier is only
    # emitted when except+ is disabled.
    if options.except_plus and not _returns_mutable_reference(return_type):
        sig += " except +"
    elif is_const:
        sig += " const"
    return sig


def _returns_mutable_reference(return_type: str) -> bool:
    """True for non-const lvalue-reference returns (``T&``).

    Such accessors (operator[], front, back, at, ...) must NOT carry
    ``except +``: Cython's try/catch wrapping stores the call result in a
    BY-VALUE temporary, so ``&cloud[i]`` would silently point at a copy and
    writes through it would be lost.  This matches Cython's own libcpp
    declarations (``T& operator[](size_type)`` has no ``except +``).  The
    trade-off: a C++ exception thrown by such a method terminates instead of
    propagating - bounds-check in the wrapper layer.
    """
    return (
        return_type.endswith("&")
        and not return_type.startswith("const ")
    )
