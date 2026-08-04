"""libclang-based parser backend.

Parses a C++ header with clang.cindex and lowers the exported declarations
into the backend-agnostic IR (:mod:`cppast2autopxd.ir`).

Design notes
------------
* The target header is parsed through a synthetic wrapper TU
  (``#include "<header>"``) so ``#pragma once`` and include guards behave
  exactly as in a normal compilation — headers that are transitively
  re-included by their own ``impl/*.hpp`` files parse fine.
* Only cursors located in the target header itself are exported; includes
  are parsed (so types resolve) but not re-declared.
* Private/protected members, deleted/move members, rvalue-reference and
  function-pointer signatures, specializations, member templates and other
  non-declarable constructs are skipped, each with a recorded warning, so a
  generation run is reproducible and auditable.
* Anonymous unions/structs (ubiquitous in PCL point types) are flattened into
  their enclosing class: for declaration purposes Cython only needs member
  names and types, the real memory layout always comes from the C++ header.
* Type names must resolve against what the pxd actually declares (or maps):
  when a sugared spelling references something from an included header, the
  canonical spelling is tried before giving up, so ``uindex_t`` resolves to
  ``unsigned int`` and ``Indices`` to ``vector[int]``.
"""

from __future__ import annotations

import functools
import glob
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field as dc_field
from typing import List, Optional, Set

from clang import cindex
from clang.cindex import CursorKind, TypeKind, AccessSpecifier

from . import ir
from .typemap import TypeMapper, UnsupportedTypeError

#: C++ operator methods Cython can declare inside a cppclass.
_SUPPORTED_OPERATORS = {
    "operator+", "operator-", "operator*", "operator/", "operator%",
    "operator&", "operator|", "operator^", "operator<<", "operator>>",
    "operator==", "operator!=", "operator<", "operator>", "operator<=",
    "operator>=", "operator++", "operator--", "operator()", "operator[]",
    "operator=",
}

_WRAPPER_NAME = "__cppast2autopxd_wrapper.cpp"


@dataclass
class ParseOptions:
    """Options controlling one parse+lower run."""

    include_dirs: List[str] = dc_field(default_factory=list)
    defines: List[str] = dc_field(default_factory=list)
    std: str = "c++14"
    # "c++" or "c" (plain C headers: no namespaces, bint for _Bool, ...).
    language: str = "c++"
    # Export simple object-like integer macro constants as an anonymous enum.
    macros: bool = True
    extra_args: List[str] = dc_field(default_factory=list)
    # Namespaces to export; empty means every namespace found in the file.
    namespaces: List[str] = dc_field(default_factory=list)
    # Whitelist/blacklist of top-level entity names (unqualified).
    include_names: List[str] = dc_field(default_factory=list)
    exclude_names: List[str] = dc_field(default_factory=list)
    # Header path to write into ``cdef extern from"..."``; defaults to the
    # parsed file's basename.
    extern_from: Optional[str] = None


class ParseError(Exception):
    """Raised when libclang reports fatal diagnostics."""


@functools.lru_cache(maxsize=1)
def _builtin_include_args() -> tuple:
    """Locate clang's builtin headers (stddef.h & co).

    The pip ``libclang`` wheel ships only the shared library, so the resource
    directory containing clang's builtin headers has to be discovered from a
    system clang installation.  Overridable via the environment variable
    ``CPPAST2AUTOPXD_RESOURCE_DIR``.
    """
    override = os.environ.get("CPPAST2AUTOPXD_RESOURCE_DIR")
    if override:
        return (f"-resource-dir={override}",)

    clang_exe = shutil.which("clang") or shutil.which("clang++")
    if clang_exe:
        try:
            out = subprocess.run(
                [clang_exe, "-print-resource-dir"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            resource_dir = out.stdout.strip()
            if out.returncode == 0 and os.path.isdir(resource_dir):
                return (f"-resource-dir={resource_dir}",)
        except (OSError, subprocess.SubprocessError):
            pass

    # Fall back to well-known llvm install layouts.
    candidates = sorted(
        glob.glob("/usr/lib/llvm-*/lib/clang/*")
        + glob.glob("/usr/lib/clang/*")
        + glob.glob("/usr/local/opt/llvm/lib/clang/*")
    )
    for cand in reversed(candidates):
        if os.path.isfile(os.path.join(cand, "include", "stddef.h")):
            return (f"-resource-dir={cand}",)
    return ()


def parse_header(path: str, options: ParseOptions, mapper: TypeMapper) -> ir.Module:
    """Parse *path* and lower it into an :class:`ir.Module`."""
    if not os.path.isfile(path):
        raise ParseError(f"header not found: {path}")
    main_abs = os.path.realpath(path)

    std = options.std
    if options.language == "c" and std.startswith("c++"):
        std = "c11"

    index = cindex.Index.create()
    args = ["-x", options.language, f"-std={std}"]
    args += list(_builtin_include_args())
    args += [f"-I{d}" for d in options.include_dirs]
    args += [f"-D{d}" for d in options.defines]
    args += options.extra_args

    parse_flags = cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
    if options.macros:
        parse_flags |= cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD

    try:
        tu = index.parse(
            _WRAPPER_NAME,
            args=args,
            unsaved_files=[(_WRAPPER_NAME, f'#include "{main_abs}"\n')],
            options=parse_flags,
        )
    except cindex.TranslationUnitLoadError as err:
        raise ParseError(f"libclang failed to parse {path}: {err}") from err

    module = ir.Module(
        extern_from=options.extern_from or os.path.basename(path)
    )

    fatal = []
    for diag in tu.diagnostics:
        if diag.severity >= cindex.Diagnostic.Error:
            fatal.append(str(diag))
        elif diag.severity == cindex.Diagnostic.Warning:
            module.warnings.append(f"clang: {diag.spelling}")
    if fatal:
        raise ParseError(
            "libclang reported errors while parsing "
            f"{path}:\n  " + "\n  ".join(fatal)
        )

    lowering = _Lowering(module, options, mapper, main_abs)
    lowering.visit_children(tu.cursor, namespace="")
    if options.macros:
        _collect_macro_constants(tu, module, main_abs)
    return module


#: Integer literal (dec/hex/oct/bin) with optional C suffixes.
_INT_LITERAL_RE = re.compile(r"(0[xX][0-9a-fA-F]+|0[bB][01]+|\d+)[uUlL]*$")


def _collect_macro_constants(tu, module: ir.Module, main_file: str) -> None:
    """Export ``#define NAME <int>`` macros as an anonymous enum block.

    Only simple object-like macros whose replacement is a (possibly signed
    or parenthesized) integer literal qualify — the reliable subset that an
    anonymous ``cdef enum:`` can carry.
    """
    items: List[ir.EnumItem] = []
    for cursor in tu.cursor.get_children():
        if cursor.kind != CursorKind.MACRO_DEFINITION:
            continue
        loc = cursor.location
        if loc.file is None or os.path.realpath(loc.file.name) != main_file:
            continue
        tokens = [t.spelling for t in cursor.get_tokens()]
        if len(tokens) < 2 or tokens[0] != cursor.spelling:
            continue
        body = tokens[1:]
        # strip one level of parentheses: #define X (42)
        if len(body) >= 3 and body[0] == "(" and body[-1] == ")":
            body = body[1:-1]
        sign = ""
        if body and body[0] in ("-", "+"):
            sign = body[0] if body[0] == "-" else ""
            body = body[1:]
        if len(body) != 1:
            continue
        m = _INT_LITERAL_RE.match(body[0])
        if not m:
            continue
        items.append(ir.EnumItem(name=cursor.spelling, value=sign + m.group(1)))
    if items:
        block = ir.NamespaceBlock(namespace="")
        block.entities.append(ir.Enum(name="", items=items))
        module.blocks.append(block)


class _SkipEntity(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class _Lowering:
    def __init__(
        self,
        module: ir.Module,
        options: ParseOptions,
        mapper: TypeMapper,
        main_file: str,
    ):
        self.module = module
        self.options = options
        self.mapper = mapper
        self.main_file = main_file
        # Names of records/enums/typedefs declared so far.  Shared with the
        # type mapper so bare identifiers only resolve against what this pxd
        # really declares (plus cimports/substitutions).
        self.declared: Set[str] = mapper.known_names

    # ------------------------------------------------------------ traversal
    def visit_children(self, cursor, namespace: str) -> None:
        for child in cursor.get_children():
            if not self._in_main_file(child):
                continue
            self._visit(child, namespace)

    def _visit(self, cursor, namespace: str) -> None:
        kind = cursor.kind
        if kind == CursorKind.NAMESPACE:
            inner = (
                f"{namespace}::{cursor.spelling}" if namespace else cursor.spelling
            )
            # Register both the full namespace path and its top component so
            # qualified spellings strip correctly at any nesting depth.
            self.mapper.local_namespaces.add(inner)
            self.mapper.local_namespaces.add(inner.split("::")[0])
            self.visit_children(cursor, inner)
            return

        if not self._namespace_selected(namespace):
            return

        try:
            if kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL):
                self._visit_record(cursor, namespace)
            elif kind == CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION:
                raise _SkipEntity(
                    f"partial specialization {cursor.displayname!r} "
                    "(Cython declares only the primary template)"
                )
            elif kind == CursorKind.UNION_DECL:
                if (
                    cursor.is_definition()
                    and not cursor.is_anonymous()
                    and self._name_selected(cursor.spelling)
                ):
                    self._add(namespace, self._lower_union(cursor))
            elif kind == CursorKind.CLASS_TEMPLATE:
                if cursor.is_definition() and self._name_selected(cursor.spelling):
                    self._add(namespace, self._lower_class(cursor, template=True))
            elif kind == CursorKind.ENUM_DECL:
                if cursor.is_definition():
                    enum = self._lower_enum(cursor)
                    if self._name_selected(enum.name) or not enum.name:
                        self._add(namespace, enum)
            elif kind in (CursorKind.TYPEDEF_DECL, CursorKind.TYPE_ALIAS_DECL):
                if self._name_selected(cursor.spelling):
                    self._add(namespace, self._lower_typedef(cursor))
            elif kind == CursorKind.FUNCTION_DECL:
                if self._name_selected(cursor.spelling):
                    self._add(namespace, self._lower_function(cursor))
            elif kind == CursorKind.VAR_DECL:
                if self._name_selected(cursor.spelling):
                    self._add(
                        namespace,
                        ir.Variable(
                            type=self._type(cursor.type),
                            name=cursor.spelling,
                        ),
                    )
            elif kind == CursorKind.FUNCTION_TEMPLATE:
                if self._name_selected(cursor.spelling):
                    self._add(
                        namespace, self._lower_function_template(cursor)
                    )
            elif kind == CursorKind.TYPE_ALIAS_TEMPLATE_DECL:
                raise _SkipEntity(
                    f"alias template {cursor.spelling!r} "
                    "(not declarable in Cython pxd)"
                )
            # extern "C" / extern "C++" blocks -> recurse transparently.
            elif kind in (
                CursorKind.UNEXPOSED_DECL,
                getattr(CursorKind, "LINKAGE_SPEC", CursorKind.UNEXPOSED_DECL),
            ):
                self.visit_children(cursor, namespace)
        except _SkipEntity as skip:
            self.module.warnings.append(f"skipped: {skip.reason}")
        except UnsupportedTypeError as err:
            self.module.warnings.append(
                f"skipped {cursor.spelling!r}: {err}"
            )

    def _visit_record(self, cursor, namespace: str) -> None:
        name = cursor.spelling
        if cursor.is_definition() and cursor.is_anonymous():
            # `typedef struct {...} Name;` — the typedef visit names and
            # lowers it; a truly anonymous top-level record is unreachable.
            return
        if not cursor.is_definition():
            # Forward declaration.  When the definition follows in this same
            # file it will be lowered there; otherwise declare the name as
            # an opaque type so pointer/reference uses stay valid.
            definition = cursor.get_definition()
            if definition is not None and self._in_main_file(definition):
                return
            if name and self._name_selected(name) and name not in self.declared:
                self.declared.add(name)
                self._add(
                    namespace,
                    ir.Class(
                        name=name,
                        # C has no classes; an opaque C record is a struct.
                        is_pod_struct=self.options.language == "c",
                    ),
                )
            return
        if not self._name_selected(name):
            return
        # Explicit full specializations reuse the primary template's name;
        # emitting them would declare a duplicate plain class.
        n_targs = getattr(cursor, "get_num_template_arguments", lambda: -1)()
        if n_targs >= 0:
            raise _SkipEntity(
                f"explicit specialization {cursor.displayname!r} "
                "(Cython declares only the primary template)"
            )
        self._add(namespace, self._lower_class(cursor, template=False))

    # ------------------------------------------------------------- lowering
    def _lower_class(self, cursor, template: bool) -> ir.Class:
        cls = ir.Class(name=cursor.spelling)
        self.declared.add(cursor.spelling)

        children = list(cursor.get_children())

        # Records that are the *type of a named field* (``union {...} u;``)
        # must not be flattened into the parent — their members live behind
        # the field name in C++.  Truly anonymous members have no such
        # sibling FIELD_DECL.
        field_type_hashes = {
            ch.type.get_declaration().hash
            for ch in children
            if ch.kind == CursorKind.FIELD_DECL
        }

        # Class-local scope: template parameters now, nested type names and
        # member typedef names as they are lowered (pass order matches the
        # emitter's declare-before-use emission order).
        scope: Set[str] = set()
        self.mapper.push_scope(scope)
        try:
            # ---- template parameters and bases
            for child in children:
                kind = child.kind
                if kind in (
                    CursorKind.TEMPLATE_TYPE_PARAMETER,
                    CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
                ):
                    if any(t.spelling == "..." for t in child.get_tokens()):
                        raise _SkipEntity(
                            f"variadic class template {cursor.spelling!r} "
                            "(parameter packs not declarable in Cython)"
                        )
                    # Non-type parameters are declared by NAME (Cython's
                    # numeric-template-parameter convention, e.g.
                    # VectorD[ScalarT, dimension_t]); defaulted parameters
                    # must carry `=*` (the one legitimate use of that
                    # marker) or use sites passing fewer arguments fail.
                    param = child.spelling
                    scope.add(param)
                    if any(t.spelling == "=" for t in child.get_tokens()):
                        param += "=*"
                    cls.template_params.append(param)
                elif kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
                    raise _SkipEntity(
                        f"class template {cursor.spelling!r} uses a "
                        "template template parameter "
                        "(not declarable in Cython)"
                    )
                elif kind == CursorKind.CXX_BASE_SPECIFIER:
                    if child.access_specifier == AccessSpecifier.PUBLIC:
                        try:
                            cls.bases.append(self._type(child.type))
                        except UnsupportedTypeError as err:
                            self.module.warnings.append(
                                f"{cursor.spelling}: dropped base class: {err}"
                            )

            # ---- pass 1: nested types (enums, classes, unions)
            for child in children:
                if not self._is_public(child):
                    continue
                kind = child.kind
                try:
                    if kind == CursorKind.ENUM_DECL and child.is_definition():
                        enum = self._lower_enum(child, register=False)
                        cls.enums.append(enum)
                        if enum.name:
                            scope.add(enum.name)
                    elif kind == CursorKind.UNION_DECL and child.is_definition():
                        if child.is_anonymous():
                            continue  # handled with fields (flattening)
                        nested = self._lower_union(child, register=False)
                        cls.nested_classes.append(nested)
                        scope.add(nested.name)
                    elif kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL):
                        if child.is_definition() and not child.is_anonymous():
                            nested = self._lower_class(child, template=False)
                            cls.nested_classes.append(nested)
                            scope.add(nested.name)
                except (UnsupportedTypeError, _SkipEntity) as err:
                    reason = getattr(err, "reason", None) or str(err)
                    self.module.warnings.append(
                        f"{cursor.spelling}.{child.spelling}: skipped ({reason})"
                    )

            # ---- pass 2: member typedefs
            for child in children:
                if not self._is_public(child):
                    continue
                if child.kind in (CursorKind.TYPEDEF_DECL, CursorKind.TYPE_ALIAS_DECL):
                    try:
                        try:
                            underlying = self._type(
                                child.underlying_typedef_type
                            )
                            td = ir.MemberTypedef(
                                name=child.spelling, underlying=underlying
                            )
                        except UnsupportedTypeError:
                            fp = self._function_pointer_decl(
                                child.underlying_typedef_type,
                                child.spelling, source_cursor=child,
                            )
                            if fp is None:
                                raise
                            td = ir.MemberTypedef(
                                name=child.spelling, underlying="", raw=fp
                            )
                        cls.typedefs.append(td)
                        scope.add(child.spelling)
                    except UnsupportedTypeError as err:
                        self.module.warnings.append(
                            f"{cursor.spelling}.{child.spelling}: "
                            f"skipped ({err})"
                        )

            # ---- pass 3: constructors, fields, methods
            # const/non-const overload pairs collapse to one declaration
            # (Cython rejects two methods differing only in constness).
            seen_signatures: Set[tuple] = set()
            for child in children:
                if not self._is_public(child):
                    continue
                kind = child.kind
                try:
                    if kind == CursorKind.FIELD_DECL:
                        self._lower_field(child, cls)
                    elif kind in (
                        CursorKind.UNION_DECL,
                        CursorKind.STRUCT_DECL,
                    ) and child.is_anonymous() and child.is_definition():
                        if child.hash in field_type_hashes:
                            raise _SkipEntity(
                                "unnamed record typing a named field "
                                "(not declarable in Cython)"
                            )
                        self._flatten_anonymous(child, cls)
                    elif kind == CursorKind.CXX_METHOD:
                        method = self._lower_method(child)
                        if method is not None:
                            sig = (
                                method.name,
                                tuple(p.raw or p.type for p in method.params),
                            )
                            if sig not in seen_signatures:
                                seen_signatures.add(sig)
                                cls.methods.append(method)
                    elif kind == CursorKind.CONVERSION_FUNCTION:
                        cls.methods.append(self._lower_conversion(child))
                    elif kind == CursorKind.CONSTRUCTOR:
                        ctor = self._lower_constructor(child)
                        if ctor is not None:
                            cls.constructors.append(ctor)
                    elif kind == CursorKind.FUNCTION_TEMPLATE:
                        raise _SkipEntity(
                            f"member function template {child.spelling!r} "
                            "(not declarable in Cython pxd)"
                        )
                    elif kind == CursorKind.VAR_DECL:
                        raise _SkipEntity(
                            f"static data member {child.spelling!r} (declare "
                            "it in a separate extern block with its "
                            "qualified name if needed)"
                        )
                    # DESTRUCTOR / access specifiers / static asserts: ignore.
                except (UnsupportedTypeError, _SkipEntity) as err:
                    reason = getattr(err, "reason", None) or str(err)
                    self.module.warnings.append(
                        f"{cursor.spelling}.{child.spelling}: skipped ({reason})"
                    )
        finally:
            self.mapper.pop_scope()

        has_members = bool(
            cls.methods or cls.constructors or cls.bases or cls.template_params
            or cls.typedefs or cls.nested_classes or cls.enums
        )
        cls.is_pod_struct = (
            cursor.kind == CursorKind.STRUCT_DECL and not template and not has_members
        )
        return cls

    def _lower_union(self, cursor, register: bool = True) -> ir.Class:
        """Lower a NAMED union to a fields-only ``cdef union`` declaration."""
        union = ir.Class(name=cursor.spelling, is_union=True)
        if register:
            self.declared.add(cursor.spelling)
        for child in cursor.get_children():
            if child.kind != CursorKind.FIELD_DECL:
                if child.kind in (
                    CursorKind.CXX_METHOD,
                    CursorKind.CONSTRUCTOR,
                ):
                    self.module.warnings.append(
                        f"union {cursor.spelling}: skipped member "
                        f"{child.spelling!r} (Cython unions hold fields only)"
                    )
                continue
            try:
                self._lower_field(child, union)
            except UnsupportedTypeError as err:
                self.module.warnings.append(
                    f"union {cursor.spelling}.{child.spelling}: skipped ({err})"
                )
        return union

    def _lower_field(self, cursor, cls: ir.Class) -> None:
        # Bit-fields emit as plain fields: Cython has no width syntax, but
        # access still compiles against the real header's layout.
        ftype = cursor.type
        dims: List[str] = []
        while ftype.kind == TypeKind.CONSTANTARRAY:
            dims.append(str(ftype.get_array_size()))
            ftype = ftype.get_array_element_type()
        if ftype.kind in (
            TypeKind.INCOMPLETEARRAY,
            TypeKind.DEPENDENTSIZEDARRAY,
            TypeKind.VARIABLEARRAY,
        ):
            raise UnsupportedTypeError("unsupported array field")
        try:
            spelled = self._type(ftype)
        except UnsupportedTypeError:
            fp = self._function_pointer_decl(
                ftype, cursor.spelling, source_cursor=cursor
            )
            if fp is None or dims:
                raise
            cls.fields.append(
                ir.Field(type="", name=cursor.spelling, raw=fp)
            )
            return
        cls.fields.append(
            ir.Field(
                type=spelled,
                name=cursor.spelling,
                array_dims=dims,
            )
        )

    def _flatten_anonymous(self, cursor, cls: ir.Class) -> None:
        """Flatten fields of an anonymous union/struct into the parent.

        Records that type a named field at THIS level are not flattened
        (their members are only reachable through the field name in C++).
        """
        field_type_hashes = {
            ch.type.get_declaration().hash
            for ch in cursor.get_children()
            if ch.kind == CursorKind.FIELD_DECL
        }
        for child in cursor.get_children():
            if child.kind == CursorKind.FIELD_DECL:
                try:
                    self._lower_field(child, cls)
                except UnsupportedTypeError as err:
                    self.module.warnings.append(
                        f"{cls.name}.{child.spelling}: skipped ({err})"
                    )
            elif child.kind in (CursorKind.UNION_DECL, CursorKind.STRUCT_DECL):
                if not child.is_anonymous():
                    continue
                if child.hash in field_type_hashes:
                    self.module.warnings.append(
                        f"{cls.name}: skipped unnamed record typing a named "
                        "field (not declarable in Cython)"
                    )
                    continue
                self._flatten_anonymous(child, cls)

    def _lower_method(self, cursor) -> Optional[ir.Method]:
        name = cursor.spelling
        if name.startswith("operator"):
            if name not in _SUPPORTED_OPERATORS:
                raise _SkipEntity(f"operator {name!r} not declarable in Cython")
            is_operator = True
        else:
            is_operator = False
        if self._is_deleted(cursor):
            return None
        return ir.Method(
            name=name,
            return_type=self._type(cursor.result_type),
            params=self._lower_params(cursor),
            is_static=cursor.is_static_method(),
            is_const=cursor.is_const_method(),
            is_operator=is_operator,
        )

    def _lower_conversion(self, cursor) -> ir.Method:
        """``operator bool()`` is the one conversion Cython can declare."""
        if cursor.result_type.spelling not in ("bool", "_Bool"):
            raise _SkipEntity(
                f"conversion operator {cursor.spelling!r} "
                "(only operator bool() is declarable in Cython)"
            )
        return ir.Method(
            name="operator bool",
            return_type=self.mapper.cython_type("bool"),
            params=[],
            is_const=cursor.is_const_method(),
            is_operator=True,
        )

    def _lower_constructor(self, cursor) -> Optional[ir.Constructor]:
        if self._is_deleted(cursor):
            return None
        if cursor.is_move_constructor():
            return None
        if cursor.type.is_function_variadic():
            return None
        return ir.Constructor(params=self._lower_params(cursor))

    def _lower_function(self, cursor) -> ir.Function:
        return ir.Function(
            name=cursor.spelling,
            return_type=self._type(cursor.result_type),
            params=self._lower_params(cursor),
        )

    def _lower_function_template(self, cursor) -> ir.Function:
        """Free function templates: ``T clamp[T](T v, T lo, T hi)``."""
        tparams: List[str] = []
        scope: Set[str] = set()
        for child in cursor.get_children():
            kind = child.kind
            if kind in (
                CursorKind.TEMPLATE_TYPE_PARAMETER,
                CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
            ):
                if any(t.spelling == "..." for t in child.get_tokens()):
                    raise _SkipEntity(
                        f"variadic function template {cursor.spelling!r} "
                        "(parameter packs not declarable in Cython)"
                    )
                param = child.spelling
                scope.add(param)
                if any(t.spelling == "=" for t in child.get_tokens()):
                    param += "=*"
                tparams.append(param)
            elif kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
                raise _SkipEntity(
                    f"function template {cursor.spelling!r} uses a template "
                    "template parameter (not declarable in Cython)"
                )
        self.mapper.push_scope(scope)
        try:
            return ir.Function(
                name=cursor.spelling,
                return_type=self._type(cursor.result_type),
                params=self._lower_params(cursor),
                template_params=tparams,
            )
        finally:
            self.mapper.pop_scope()

    def _lower_params(self, cursor) -> List[ir.Param]:
        params = []
        args = list(cursor.get_arguments())
        if not args:
            # FUNCTION_TEMPLATE cursors expose no arguments(); their
            # parameters are PARM_DECL children.
            args = [
                c for c in cursor.get_children()
                if c.kind == CursorKind.PARM_DECL
            ]
        for i, arg in enumerate(args):
            # A real default argument introduces a top-level '=' token in the
            # parameter declaration.  Expression *children* alone are not
            # evidence: array dimensions (float mat[16]) and non-type
            # template arguments (Histogram<32>) also appear as expression
            # children and must not fabricate overloads.
            has_default = any(
                tok.spelling == "=" for tok in arg.get_tokens()
            )
            atype = arg.type
            name = arg.spelling or ""
            dims: List[str] = []
            if atype.kind == TypeKind.INCOMPLETEARRAY:
                dims.append("")
                atype = atype.get_array_element_type()
            while atype.kind == TypeKind.CONSTANTARRAY:
                dims.append(str(atype.get_array_size()))
                atype = atype.get_array_element_type()
            try:
                spelled = self._type(atype)
            except UnsupportedTypeError:
                fp = self._function_pointer_decl(
                    atype, name or f"arg{i}", source_cursor=arg
                )
                if fp is None or dims:
                    raise
                params.append(
                    ir.Param(type="", name=name, raw=fp,
                             has_default=has_default)
                )
                continue
            if len(dims) == 1 and dims[0] != "":
                # 1-D arrays decay to a pointer (semantically identical).
                spelled += "*"
                dims = []
            elif dims and not name:
                # Multi-dim arrays keep their dims and need a declarator name.
                name = f"arg{i}"
            params.append(
                ir.Param(
                    type=spelled,
                    name=name,
                    has_default=has_default,
                    array_dims=dims,
                )
            )
        if cursor.type.kind in (
            TypeKind.FUNCTIONPROTO,
            TypeKind.FUNCTIONNOPROTO,
        ) and cursor.type.is_function_variadic():
            # C varargs: Cython supports a trailing `...`.
            params.append(ir.Param(type="..."))
        return params

    def _lower_enum(self, cursor, register: bool = True) -> ir.Enum:
        # Anonymous enums must not leak libclang's "(unnamed enum at ...)"
        # placeholder; an empty name renders as `cdef enum:` / `enum:`.
        name = cursor.spelling
        if cursor.is_anonymous() or name.startswith("("):
            name = ""
        elif register:
            self.declared.add(name)
        enum = ir.Enum(
            name=name,
            is_scoped=getattr(cursor, "is_scoped_enum", lambda: False)(),
        )
        for child in cursor.get_children():
            if child.kind == CursorKind.ENUM_CONSTANT_DECL:
                enum.items.append(
                    ir.EnumItem(
                        name=child.spelling, value=str(child.enum_value)
                    )
                )
        return enum

    def _lower_typedef(self, cursor):
        name = cursor.spelling
        ut = cursor.underlying_typedef_type

        # `typedef struct {...} Name;` / `typedef enum {...} Name;` — the C
        # idiom: name the anonymous definition after the typedef.
        decl = ut.get_declaration()
        if (
            decl is not None
            and decl.kind in (
                CursorKind.STRUCT_DECL,
                CursorKind.UNION_DECL,
                CursorKind.ENUM_DECL,
                CursorKind.CLASS_DECL,
            )
            and decl.is_definition()
            and decl.is_anonymous()
            and self._in_main_file(decl)
        ):
            if decl.kind == CursorKind.ENUM_DECL:
                entity = self._lower_enum(decl, register=False)
            elif decl.kind == CursorKind.UNION_DECL:
                entity = self._lower_union(decl, register=False)
            else:
                entity = self._lower_class(decl, template=False)
            entity.name = name
            self.declared.add(name)
            return entity

        try:
            underlying = self._type(ut)
        except UnsupportedTypeError:
            fp = self._function_pointer_decl(ut, name, source_cursor=cursor)
            if fp is None:
                raise
            self.declared.add(name)
            return ir.Typedef(name=name, underlying="", raw=fp)

        if underlying == name:
            # `typedef struct Foo Foo;` — the name is already declared;
            # Cython would reject the self-referential ctypedef.
            return None
        self.declared.add(name)
        return ir.Typedef(name=name, underlying=underlying)

    def _function_pointer_decl(
        self, t, name: str, source_cursor=None
    ) -> Optional[str]:
        """Render a function-pointer/function type as a Cython declarator
        (``int (*name)(int a, ...)``), or None when *t* is not one.

        Parameter names are recovered from *source_cursor*'s PARM_DECL
        children when available (types alone carry no names).
        """
        # Prefer the sugared type so parameter types keep their declared
        # names (item_id, not unsigned int); fall back to canonical when the
        # sugar hides the function shape behind another alias.
        probe = t
        if probe.kind not in (
            TypeKind.POINTER,
            TypeKind.FUNCTIONPROTO,
            TypeKind.FUNCTIONNOPROTO,
        ):
            probe = t.get_canonical()
        pointer = False
        if probe.kind == TypeKind.POINTER:
            pointee = probe.get_pointee()
            if pointee.kind not in (
                TypeKind.FUNCTIONPROTO,
                TypeKind.FUNCTIONNOPROTO,
            ):
                return None
            fn = pointee
            pointer = True
        elif probe.kind in (
            TypeKind.FUNCTIONPROTO,
            TypeKind.FUNCTIONNOPROTO,
        ):
            fn = probe
        else:
            return None
        ret = self._type(fn.get_result())
        param_names: List[str] = []
        if source_cursor is not None:
            param_names = [
                c.spelling
                for c in source_cursor.get_children()
                if c.kind == CursorKind.PARM_DECL
            ]
        args = []
        if fn.kind == TypeKind.FUNCTIONPROTO:
            for j, at in enumerate(fn.argument_types()):
                spelled = self._type(at)
                pname = param_names[j] if j < len(param_names) else ""
                args.append(f"{spelled} {pname}".strip())
            if fn.is_function_variadic():
                args.append("...")
        declarator = f"(*{name})" if pointer else name
        return f"{ret} {declarator}({', '.join(args)})"

    # ------------------------------------------------------------- helpers
    def _type(self, t) -> str:
        """Translate a clang Type, falling back to its canonical spelling.

        The sugared spelling is preferred (it keeps declared typedef names),
        but when it references something this pxd does not declare — e.g. a
        typedef living in an included header — the canonical spelling often
        resolves to declarable types (``uindex_t`` -> ``unsigned int``,
        ``Indices`` -> ``std::vector<int, ...>`` -> ``vector[int]``).
        """
        try:
            return self.mapper.cython_type(t.spelling)
        except UnsupportedTypeError as first_err:
            canonical = t.get_canonical()
            if canonical.spelling != t.spelling:
                try:
                    return self.mapper.cython_type(canonical.spelling)
                except UnsupportedTypeError:
                    raise first_err from None
            raise

    def _in_main_file(self, cursor) -> bool:
        loc = cursor.location
        if loc.file is None:
            return False
        return os.path.realpath(loc.file.name) == self.main_file

    def _namespace_selected(self, namespace: str) -> bool:
        """Strict namespace filter: when a list is configured, only those
        namespaces are exported (add "" to the list for the global one)."""
        if not self.options.namespaces:
            return True
        return namespace in self.options.namespaces

    def _name_selected(self, name: str) -> bool:
        if name in self.options.exclude_names:
            return False
        if self.options.include_names:
            return name in self.options.include_names
        return True

    def _add(self, namespace: str, entity) -> None:
        if entity is None:
            return
        self.module.block_for(namespace).entities.append(entity)

    @staticmethod
    def _is_public(cursor) -> bool:
        access = cursor.access_specifier
        if access == AccessSpecifier.INVALID:
            return True
        return access == AccessSpecifier.PUBLIC

    @staticmethod
    def _is_deleted(cursor) -> bool:
        checker = getattr(cursor, "is_deleted_method", None)
        if checker is not None:
            try:
                return bool(checker())
            except Exception:
                return False
        return False
