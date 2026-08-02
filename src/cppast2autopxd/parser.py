"""libclang-based parser backend.

Parses a C++ header with clang.cindex and lowers the exported declarations
into the backend-agnostic IR (:mod:`cppast2autopxd.ir`).

Design notes
------------
* Only cursors located in the parsed file itself are exported; includes are
  parsed (so types resolve) but not re-declared.
* Private/protected members, deleted/move members, rvalue-reference and
  function-pointer signatures are skipped, each with a recorded warning, so a
  generation run is reproducible and auditable.
* Anonymous unions/structs (ubiquitous in PCL point types) are flattened into
  their enclosing class: for declaration purposes Cython only needs member
  names and types, the real memory layout always comes from the C++ header.
"""

from __future__ import annotations

import functools
import glob
import os
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


@dataclass
class ParseOptions:
    """Options controlling one parse+lower run."""

    include_dirs: List[str] = dc_field(default_factory=list)
    defines: List[str] = dc_field(default_factory=list)
    std: str = "c++14"
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

    index = cindex.Index.create()
    # -Wno-pragma-once-outside-header: headers are parsed as main files, so
    # clang would otherwise warn about every `#pragma once`.
    args = [
        "-x", "c++", f"-std={options.std}",
        "-Wno-pragma-once-outside-header",
    ]
    args += list(_builtin_include_args())
    args += [f"-I{d}" for d in options.include_dirs]
    args += [f"-D{d}" for d in options.defines]
    args += options.extra_args

    try:
        tu = index.parse(
            path,
            args=args,
            options=cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
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

    lowering = _Lowering(module, options, mapper, os.path.realpath(path))
    lowering.visit_children(tu.cursor, namespace="")
    return module


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
        # Names of records/enums declared so far, used to resolve bare
        # references and to auto-register local namespaces.
        self.declared: Set[str] = set()

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
            self.mapper.local_namespaces.add(inner.split("::")[0])
            self.visit_children(cursor, inner)
            return

        if not self._namespace_selected(namespace):
            return

        try:
            if kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL):
                if cursor.is_definition() and self._name_selected(cursor.spelling):
                    self._add(namespace, self._lower_class(cursor, template=False))
            elif kind == CursorKind.CLASS_TEMPLATE:
                if cursor.is_definition() and self._name_selected(cursor.spelling):
                    self._add(namespace, self._lower_class(cursor, template=True))
            elif kind == CursorKind.ENUM_DECL:
                if cursor.is_definition() and self._name_selected(cursor.spelling):
                    self._add(namespace, self._lower_enum(cursor))
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
                raise _SkipEntity(
                    f"function template {cursor.spelling!r} "
                    "(not declarable in Cython pxd)"
                )
            elif kind == CursorKind.TYPE_ALIAS_TEMPLATE_DECL:
                raise _SkipEntity(
                    f"alias template {cursor.spelling!r} "
                    "(not declarable in Cython pxd)"
                )
            # UNEXPOSED_DECL (extern "C" blocks) -> recurse transparently.
            elif kind == CursorKind.UNEXPOSED_DECL:
                self.visit_children(cursor, namespace)
        except _SkipEntity as skip:
            self.module.warnings.append(f"skipped: {skip.reason}")
        except UnsupportedTypeError as err:
            self.module.warnings.append(
                f"skipped {cursor.spelling!r}: {err}"
            )

    # ------------------------------------------------------------- lowering
    def _lower_class(self, cursor, template: bool) -> ir.Class:
        cls = ir.Class(name=cursor.spelling)
        self.declared.add(cursor.spelling)
        has_members = False

        for child in cursor.get_children():
            kind = child.kind
            if kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
                cls.template_params.append(child.spelling)
                continue
            if kind in (
                CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
                CursorKind.TEMPLATE_TEMPLATE_PARAMETER,
            ):
                raise _SkipEntity(
                    f"class template {cursor.spelling!r} uses a non-type "
                    "template parameter (not declarable in Cython)"
                )
            if kind == CursorKind.CXX_BASE_SPECIFIER:
                if child.access_specifier == AccessSpecifier.PUBLIC:
                    try:
                        cls.bases.append(self._type(child.type))
                    except UnsupportedTypeError as err:
                        self.module.warnings.append(
                            f"{cursor.spelling}: dropped base class: {err}"
                        )
                continue
            if not self._is_public(child, cursor):
                continue

            try:
                if kind == CursorKind.FIELD_DECL:
                    self._lower_field(child, cls)
                elif kind in (CursorKind.UNION_DECL, CursorKind.STRUCT_DECL) and (
                    child.is_anonymous()
                ):
                    self._flatten_anonymous(child, cls)
                elif kind == CursorKind.CXX_METHOD:
                    method = self._lower_method(child)
                    if method is not None:
                        cls.methods.append(method)
                        has_members = True
                elif kind == CursorKind.CONSTRUCTOR:
                    ctor = self._lower_constructor(child)
                    if ctor is not None:
                        cls.constructors.append(ctor)
                        has_members = True
                elif kind in (CursorKind.TYPEDEF_DECL, CursorKind.TYPE_ALIAS_DECL):
                    cls.typedefs.append(
                        ir.MemberTypedef(
                            name=child.spelling,
                            underlying=self._type(child.underlying_typedef_type),
                        )
                    )
                elif kind == CursorKind.ENUM_DECL and child.is_definition():
                    cls.enums.append(self._lower_enum(child))
                elif kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL):
                    if child.is_definition() and not child.is_anonymous():
                        cls.nested_classes.append(
                            self._lower_class(child, template=False)
                        )
                # DESTRUCTOR / access specifiers / static asserts: ignore.
            except (UnsupportedTypeError, _SkipEntity) as err:
                reason = getattr(err, "reason", None) or str(err)
                self.module.warnings.append(
                    f"{cursor.spelling}.{child.spelling}: skipped ({reason})"
                )

        has_members = has_members or bool(
            cls.methods or cls.constructors or cls.bases or cls.template_params
            or cls.typedefs or cls.nested_classes
        )
        cls.is_pod_struct = (
            cursor.kind == CursorKind.STRUCT_DECL and not template and not has_members
        )
        return cls

    def _lower_field(self, cursor, cls: ir.Class) -> None:
        ftype = cursor.type
        dims: List[str] = []
        while ftype.kind == TypeKind.CONSTANTARRAY:
            dims.append(str(ftype.get_array_size()))
            ftype = ftype.get_array_element_type()
        if ftype.kind == TypeKind.INCOMPLETEARRAY:
            raise UnsupportedTypeError("incomplete array field")
        cls.fields.append(
            ir.Field(
                type=self._type(ftype),
                name=cursor.spelling,
                array_dims=dims,
            )
        )

    def _flatten_anonymous(self, cursor, cls: ir.Class) -> None:
        """Flatten fields of an anonymous union/struct into the parent."""
        for child in cursor.get_children():
            if child.kind == CursorKind.FIELD_DECL:
                self._lower_field(child, cls)
            elif child.kind in (CursorKind.UNION_DECL, CursorKind.STRUCT_DECL):
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
        if cursor.type.is_function_variadic():
            raise _SkipEntity(f"variadic function {name!r}")
        return ir.Method(
            name=name,
            return_type=self._type(cursor.result_type),
            params=self._lower_params(cursor),
            is_static=cursor.is_static_method(),
            is_const=cursor.is_const_method(),
            is_operator=is_operator,
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
        if cursor.type.is_function_variadic():
            raise _SkipEntity(f"variadic function {cursor.spelling!r}")
        return ir.Function(
            name=cursor.spelling,
            return_type=self._type(cursor.result_type),
            params=self._lower_params(cursor),
        )

    def _lower_params(self, cursor) -> List[ir.Param]:
        params = []
        for arg in cursor.get_arguments():
            has_default = any(
                child.kind.is_expression() for child in arg.get_children()
            )
            atype = arg.type
            dims = 0
            while atype.kind == TypeKind.CONSTANTARRAY:
                atype = atype.get_array_element_type()
                dims += 1
            spelled = self._type(atype) + "*" * dims
            params.append(
                ir.Param(
                    type=spelled,
                    name=arg.spelling or "",
                    has_default=has_default,
                )
            )
        return params

    def _lower_enum(self, cursor) -> ir.Enum:
        self.declared.add(cursor.spelling)
        enum = ir.Enum(
            name=cursor.spelling,
            is_scoped=getattr(cursor, "is_scoped_enum", lambda: False)(),
        )
        for child in cursor.get_children():
            if child.kind == CursorKind.ENUM_CONSTANT_DECL:
                enum.items.append(ir.EnumItem(name=child.spelling))
        return enum

    def _lower_typedef(self, cursor) -> ir.Typedef:
        underlying = self._type(cursor.underlying_typedef_type)
        self.declared.add(cursor.spelling)
        return ir.Typedef(name=cursor.spelling, underlying=underlying)

    # ------------------------------------------------------------- helpers
    def _type(self, t) -> str:
        return self.mapper.cython_type(t.spelling)

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
    def _is_public(cursor, parent) -> bool:
        access = cursor.access_specifier
        if access == AccessSpecifier.INVALID:
            return True
        if access == AccessSpecifier.PUBLIC:
            return True
        # struct members default to public but libclang reports the real
        # access, so private/protected always means skip.
        return False

    @staticmethod
    def _is_deleted(cursor) -> bool:
        checker = getattr(cursor, "is_deleted_method", None)
        if checker is not None:
            try:
                return bool(checker())
            except Exception:
                return False
        return False
