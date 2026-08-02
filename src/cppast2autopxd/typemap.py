"""C++ type expression -> Cython type expression translation.

Works on the *spelling* of a type (e.g. ``const std::vector<pcl::PointXYZ> &``)
rather than on libclang Type objects, so the same code also serves a future
cppast text-dump backend.  Template argument lists are tokenized at the top
level, translated recursively, and rendered with Cython's ``[]`` syntax.

Along the way the mapper records which ``cimport`` lines the resulting pxd
needs (``from libcpp.vector cimport vector`` and friends).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


class UnsupportedTypeError(Exception):
    """Raised when a type cannot be expressed in Cython."""


#: Known std:: (and compatible) templates: cython name, cimport line, and how
#: many leading template arguments to keep (allocator/comparator/hash tails
#: are defaulted in C++ and must be dropped for the libcpp declarations).
_STD_TEMPLATES: Dict[str, Tuple[str, str, int]] = {
    "std::vector": ("vector", "from libcpp.vector cimport vector", 1),
    "std::deque": ("deque", "from libcpp.deque cimport deque", 1),
    "std::list": ("list", "from libcpp.list cimport list", 1),
    "std::set": ("set", "from libcpp.set cimport set", 1),
    "std::multiset": ("multiset", "from libcpp.set cimport multiset", 1),
    "std::map": ("map", "from libcpp.map cimport map", 2),
    "std::multimap": ("multimap", "from libcpp.map cimport multimap", 2),
    "std::unordered_map": (
        "unordered_map",
        "from libcpp.unordered_map cimport unordered_map",
        2,
    ),
    "std::unordered_set": (
        "unordered_set",
        "from libcpp.unordered_set cimport unordered_set",
        1,
    ),
    "std::pair": ("pair", "from libcpp.pair cimport pair", 2),
    "std::shared_ptr": ("shared_ptr", "from libcpp.memory cimport shared_ptr", 1),
    "std::unique_ptr": ("unique_ptr", "from libcpp.memory cimport unique_ptr", 1),
    "std::weak_ptr": ("weak_ptr", "from libcpp.memory cimport weak_ptr", 1),
    # PCL >= 1.11 aliases pcl::shared_ptr to std::shared_ptr.
    "pcl::shared_ptr": ("shared_ptr", "from libcpp.memory cimport shared_ptr", 1),
    # boost::shared_ptr is ABI-compatible enough for declaration purposes on
    # PCL < 1.11; users can override via [typemap.substitutions] if they need
    # a dedicated boost pxd.
    "boost::shared_ptr": ("shared_ptr", "from libcpp.memory cimport shared_ptr", 1),
}

#: Non-template std types.
_STD_SIMPLE: Dict[str, Tuple[str, Optional[str]]] = {
    "std::string": ("string", "from libcpp.string cimport string"),
    "std::size_t": ("size_t", None),
    "size_t": ("size_t", None),
    "std::ptrdiff_t": ("ptrdiff_t", None),
    "ptrdiff_t": ("ptrdiff_t", None),
    "std::ostream": ("ostream", "from libcpp.iostream cimport ostream"),
    "std::istream": ("istream", "from libcpp.iostream cimport istream"),
    "bool": ("bool", "from libcpp cimport bool"),
}

#: stdint types -> libc.stdint cimport.
_STDINT = {
    "int8_t",
    "int16_t",
    "int32_t",
    "int64_t",
    "uint8_t",
    "uint16_t",
    "uint32_t",
    "uint64_t",
    "intptr_t",
    "uintptr_t",
}

#: Builtin C types passed through untouched (possibly multi-word).
_BUILTINS = {
    "void",
    "char",
    "signed char",
    "unsigned char",
    "short",
    "unsigned short",
    "int",
    "unsigned int",
    "unsigned",
    "long",
    "unsigned long",
    "long long",
    "unsigned long long",
    "float",
    "double",
    "long double",
    "wchar_t",
    "short int",
    "long int",
    "long long int",
    "unsigned short int",
    "unsigned long int",
    "unsigned long long int",
}


@dataclass
class Substitution:
    """User-configured mapping of a C++ type name to a Cython name."""

    cython: str
    cimport: Optional[str] = None


@dataclass
class TypeMapper:
    """Translate C++ type spellings and collect required cimports."""

    # Namespaces whose prefix is stripped because their contents are declared
    # in the generated pxd itself (e.g. {"pcl"}).
    local_namespaces: Set[str] = field(default_factory=set)
    # Extra user mappings, keyed by fully qualified C++ name.
    substitutions: Dict[str, Substitution] = field(default_factory=dict)
    cimports: Set[str] = field(default_factory=set)

    # ------------------------------------------------------------------ API
    def cython_type(self, spelling: str) -> str:
        """Translate a C++ type spelling into a Cython type expression.

        Raises :class:`UnsupportedTypeError` for constructs Cython cannot
        declare (rvalue references, function pointers, ...).
        """
        return self._translate(spelling.strip())

    # ------------------------------------------------------------ internals
    def _translate(self, s: str) -> str:
        s = _normalize_ws(s)
        if not s:
            raise UnsupportedTypeError("empty type spelling")
        if "&&" in s:
            raise UnsupportedTypeError(f"rvalue reference not supported: {s!r}")
        if "(" in s:
            raise UnsupportedTypeError(f"function/array type not supported: {s!r}")

        # Split trailing pointer/reference declarators off the base type.
        base, suffix = _split_declarators(s)

        # Leading/trailing const.  Cython understands `const T`, so keep one
        # leading const on the base type; drop `volatile`.
        const = False
        words = base.split(" ")
        while words and words[0] in ("const", "volatile"):
            const = const or words[0] == "const"
            words.pop(0)
        while words and words[-1] in ("const", "volatile"):
            const = const or words[-1] == "const"
            words.pop()
        base = " ".join(words)
        if not base:
            raise UnsupportedTypeError(f"could not parse type: {s!r}")

        base = _strip_elaboration(base)
        translated = self._translate_base(base)
        if const:
            translated = "const " + translated
        return translated + suffix

    def _translate_base(self, base: str) -> str:
        if base in _BUILTINS:
            return base

        name, args = _split_template(base)

        # User substitutions win over the builtin tables.
        sub = self.substitutions.get(name) or self.substitutions.get(base)
        if sub is not None:
            if sub.cimport:
                self.cimports.add(sub.cimport)
            if args is None:
                return sub.cython
            return sub.cython + self._render_args(args, keep=len(args))

        if args is None:
            if base in _STD_SIMPLE:
                cy, imp = _STD_SIMPLE[base]
                if imp:
                    self.cimports.add(imp)
                return cy
            if base in _STDINT or base.removeprefix("std::") in _STDINT:
                short = base.removeprefix("std::")
                self.cimports.add(f"from libc.stdint cimport {short}")
                return short
            return self._strip_local_namespace(base)

        if name in _STD_TEMPLATES:
            cy, imp, keep = _STD_TEMPLATES[name]
            self.cimports.add(imp)
            return cy + self._render_args(args, keep=keep)

        return self._strip_local_namespace(name) + self._render_args(
            args, keep=len(args)
        )

    def _render_args(self, args: List[str], keep: int) -> str:
        kept = args[:keep] if keep else args
        rendered = ", ".join(self._translate(a) for a in kept)
        return f"[{rendered}]"

    def _strip_local_namespace(self, name: str) -> str:
        """Strip namespace qualifiers that the pxd declares locally.

        ``pcl::PointXYZ`` -> ``PointXYZ`` when "pcl" is a local namespace.
        Unknown qualified names keep only their last component (Cython has no
        ``::`` syntax; cross-pxd references must go through substitutions or
        cimports).
        """
        if "::" not in name:
            return name
        parts = name.split("::")
        if parts[0] in self.local_namespaces:
            return parts[-1]
        raise UnsupportedTypeError(
            f"unmapped qualified type {name!r}: add it to "
            f"[typemap.substitutions] or wrap its namespace"
        )


# ---------------------------------------------------------------- helpers
def _normalize_ws(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    s = s.replace(" <", "<").replace("< ", "<")
    s = s.replace(" >", ">")
    s = s.replace(" *", " *").replace("* ", "*")
    s = s.replace(" &", " &").replace("& ", "&")
    s = s.replace(" ,", ",").replace(",", ", ")
    s = re.sub(r"\s+", " ", s)
    return s


def _split_declarators(s: str) -> Tuple[str, str]:
    """Split ``std::vector<int> *&`` into (``std::vector<int>``, ``*&``)."""
    suffix = ""
    s = s.strip()
    while True:
        stripped = s.rstrip()
        if stripped.endswith("*"):
            suffix = "*" + suffix
            s = stripped[:-1]
        elif stripped.endswith("&"):
            suffix = "&" + suffix
            s = stripped[:-1]
        elif stripped.endswith("const") and suffix:
            # `int *const` -> the pointer itself is const; Cython cannot say
            # that, drop the qualifier.
            s = stripped[: -len("const")]
        else:
            break
    return s.strip(), suffix


def _strip_elaboration(s: str) -> str:
    for kw in ("struct ", "class ", "enum ", "union "):
        if s.startswith(kw):
            return s[len(kw):]
    return s


def _split_template(s: str) -> Tuple[str, Optional[List[str]]]:
    """Split ``std::map<K, V>`` into (``std::map``, [``K``, ``V``])."""
    lt = s.find("<")
    if lt == -1:
        return s, None
    if not s.endswith(">"):
        raise UnsupportedTypeError(f"unbalanced template brackets: {s!r}")
    name = s[:lt]
    inner = s[lt + 1 : -1]
    args: List[str] = []
    depth = 0
    current = []
    for ch in inner:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        args.append("".join(current).strip())
    # Drop non-type template arguments that are plain integer literals; the
    # caller decides how many args to keep anyway.
    return name, args
