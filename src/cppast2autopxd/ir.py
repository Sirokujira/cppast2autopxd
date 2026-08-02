"""Intermediate representation of the subset of C++ declarations that can be
expressed in a Cython ``.pxd`` file.

The parser backend (currently libclang) produces these nodes; the emitter
turns them into ``cdef extern from`` blocks.  Keeping the IR backend-agnostic
is what will later allow a cppast (AST dump) based backend to slot in without
touching the emitter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Param:
    """A function/method parameter."""

    type: str
    name: str = ""
    has_default: bool = False


@dataclass
class Field:
    """A public data member."""

    type: str
    name: str
    # For constant-size arrays: ["4"] renders as ``float data[4]``.
    array_dims: List[str] = field(default_factory=list)


@dataclass
class Method:
    """A public member function."""

    name: str
    return_type: str
    params: List[Param] = field(default_factory=list)
    is_static: bool = False
    is_const: bool = False
    is_operator: bool = False


@dataclass
class Constructor:
    params: List[Param] = field(default_factory=list)


@dataclass
class MemberTypedef:
    """A typedef/using alias declared inside a class body."""

    name: str
    underlying: str


@dataclass
class EnumItem:
    name: str
    # Explicit values are preserved so the pxd matches the header.
    value: Optional[str] = None


@dataclass
class Enum:
    name: str
    items: List[EnumItem] = field(default_factory=list)
    is_scoped: bool = False


@dataclass
class Typedef:
    name: str
    underlying: str


@dataclass
class Function:
    name: str
    return_type: str
    params: List[Param] = field(default_factory=list)


@dataclass
class Variable:
    """A namespace-scope variable/constant declaration."""

    type: str
    name: str


@dataclass
class Class:
    """A class/struct/union/class-template definition."""

    name: str
    # Template parameter names, e.g. ["PointT"] for PointCloud<PointT>.
    template_params: List[str] = field(default_factory=list)
    # Cython type expressions for public bases, e.g. ["PCLBase[PointT]"].
    bases: List[str] = field(default_factory=list)
    # True when the record has no methods/ctors/bases/templates and can be
    # declared as a plain ``cdef struct``.
    is_pod_struct: bool = False
    # True for named unions: rendered as ``cdef union`` (fields only).
    is_union: bool = False
    typedefs: List[MemberTypedef] = field(default_factory=list)
    enums: List["Enum"] = field(default_factory=list)
    fields: List[Field] = field(default_factory=list)
    constructors: List[Constructor] = field(default_factory=list)
    methods: List[Method] = field(default_factory=list)
    nested_classes: List["Class"] = field(default_factory=list)


# Entities that may appear at namespace scope, in source order.
TopLevel = object  # documentation alias: Class | Enum | Typedef | Function | Variable


@dataclass
class NamespaceBlock:
    """All exported declarations for one (header, namespace) pair."""

    # C++ namespace, "" for the global namespace.
    namespace: str
    entities: List[object] = field(default_factory=list)


@dataclass
class Module:
    """Everything generated from a single header file."""

    # Header path as it should appear in ``cdef extern from "<...>"``.
    extern_from: str
    blocks: List[NamespaceBlock] = field(default_factory=list)
    # Warnings accumulated during parsing (skipped entities etc.).
    warnings: List[str] = field(default_factory=list)

    def block_for(self, namespace: str) -> NamespaceBlock:
        """Return the trailing block for *namespace*, appending a new one
        when the namespace changes.

        Only the LAST block is ever reused: merging all same-namespace
        declarations into one block would reorder interleaved namespaces
        (``ns X { P } ns Y { Q } ns X { R uses Q }`` would emit R before Q).
        Cython accepts multiple extern blocks for the same namespace, so one
        block per contiguous source region preserves declaration order.
        """
        if self.blocks and self.blocks[-1].namespace == namespace:
            return self.blocks[-1]
        b = NamespaceBlock(namespace=namespace)
        self.blocks.append(b)
        return b
