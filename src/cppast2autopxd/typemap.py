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


#: Non-type template arguments: integer/char/bool literals (with suffixes).
_NONTYPE_ARG_RE = re.compile(r"[+-]?\d+[uUlL]*|true|false|'[^']*'")


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
    "std::function": ("function", "from libcpp.functional cimport function", 1),
    "std::optional": ("optional", "from libcpp.optional cimport optional", 1),
    "std::atomic": ("atomic", "from libcpp.atomic cimport atomic", 1),
    "std::complex": ("complex", "from libcpp.complex cimport complex", 1),
    "std::forward_list": (
        "forward_list",
        "from libcpp.forward_list cimport forward_list",
        1,
    ),
    "std::queue": ("queue", "from libcpp.queue cimport queue", 1),
    "std::priority_queue": (
        "priority_queue",
        "from libcpp.queue cimport priority_queue",
        1,
    ),
    "std::stack": ("stack", "from libcpp.stack cimport stack", 1),
    "std::span": ("span", "from libcpp.span cimport span", 1),
    # PCL >= 1.11 aliases pcl::shared_ptr to std::shared_ptr.
    "pcl::shared_ptr": ("shared_ptr", "from libcpp.memory cimport shared_ptr", 1),
    # boost::shared_ptr is ABI-compatible enough for declaration purposes on
    # PCL < 1.11; users can override via [typemap.substitutions] if they need
    # a dedicated boost pxd.
    "boost::shared_ptr": ("shared_ptr", "from libcpp.memory cimport shared_ptr", 1),
}

#: Non-template std types.  NOTE: std::ostream/std::istream are deliberately
#: absent — Cython ships no libcpp.iostream, so they fall through to the
#: unmapped-qualified-name error (skip-with-warning at the parser level);
#: users can map them via [typemap.substitutions] to a pxd they provide.
_STD_SIMPLE: Dict[str, Tuple[str, Optional[str]]] = {
    "std::string": ("string", "from libcpp.string cimport string"),
    "std::size_t": ("size_t", None),
    "size_t": ("size_t", None),
    "std::ptrdiff_t": ("ptrdiff_t", None),
    "ptrdiff_t": ("ptrdiff_t", None),
    "bool": ("bool", "from libcpp cimport bool"),
    "_Bool": ("bint", None),
    "wchar_t": ("wchar_t", "from libc.stddef cimport wchar_t"),
    "std::string_view": (
        "string_view",
        "from libcpp.string_view cimport string_view",
    ),
    "std::any": ("any", "from libcpp.any cimport any"),
    # Curated libc/posix symbols commonly seen in C APIs.
    "time_t": ("time_t", "from libc.time cimport time_t"),
    "std::time_t": ("time_t", "from libc.time cimport time_t"),
    "clock_t": ("clock_t", "from libc.time cimport clock_t"),
    "std::clock_t": ("clock_t", "from libc.time cimport clock_t"),
    "FILE": ("FILE", "from libc.stdio cimport FILE"),
    "ssize_t": ("ssize_t", "from posix.types cimport ssize_t"),
}

#: stdint types -> libc.stdint cimport (all families libc/stdint.pxd covers).
_STDINT = (
    {f"int{w}_t" for w in (8, 16, 32, 64)}
    | {f"uint{w}_t" for w in (8, 16, 32, 64)}
    | {f"int_least{w}_t" for w in (8, 16, 32, 64)}
    | {f"uint_least{w}_t" for w in (8, 16, 32, 64)}
    | {f"int_fast{w}_t" for w in (8, 16, 32, 64)}
    | {f"uint_fast{w}_t" for w in (8, 16, 32, 64)}
    | {"intptr_t", "uintptr_t", "intmax_t", "uintmax_t"}
)

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
    # Names declared in the generated pxd (shared with the parser) plus
    # names brought in via extra cimports.  A bare identifier that is not a
    # builtin, not in a mapping table, and not in here is NOT quietly passed
    # through: it would produce a pxd Cython rejects, so it raises instead
    # (the parser then skips the enclosing declaration with a warning).
    known_names: Set[str] = field(default_factory=set)
    # Scope stack for template parameters and class-local names.
    scopes: List[Set[str]] = field(default_factory=list)

    # ------------------------------------------------------------------ API
    def cython_type(self, spelling: str) -> str:
        """Translate a C++ type spelling into a Cython type expression.

        Raises :class:`UnsupportedTypeError` for constructs Cython cannot
        declare (rvalue references, function pointers, undeclared names...).
        """
        return self._translate(spelling.strip())

    def push_scope(self, names: Set[str]) -> None:
        self.scopes.append(names)

    def pop_scope(self) -> None:
        self.scopes.pop()

    def _is_known(self, name: str) -> bool:
        if name in self.known_names:
            return True
        return any(name in scope for scope in self.scopes)

    # ------------------------------------------------------------ internals
    def _translate(self, s: str) -> str:
        s = _normalize_ws(s)
        if not s:
            raise UnsupportedTypeError("empty type spelling")
        if "&&" in s:
            raise UnsupportedTypeError(f"rvalue reference not supported: {s!r}")
        if "anonymous" in s or "unnamed" in s:
            raise UnsupportedTypeError(f"anonymous type not supported: {s!r}")
        if "(*" in s or "(&" in s:
            raise UnsupportedTypeError(
                f"function-pointer type not supported here: {s!r}"
            )
        if "(" in s:
            lt = s.find("<")
            if lt == -1 or s.find("(") < lt:
                # A bare function type: valid only as a template argument
                # (std::function<int(int)> -> function[int(int)]).
                return self._translate_function_type(s)
            # otherwise the parens live inside template args; the recursive
            # argument translation handles them.

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

        # User substitutions win over the builtin tables.  A substitution
        # keyed by the FULL instantiation spelling ("pcl::PointCloud<pcl::
        # PointXYZ>") maps the whole thing to one Cython name; a substitution
        # keyed by the template name alone keeps the translated arguments.
        if args is not None:
            sub_full = self.substitutions.get(base)
            if sub_full is not None:
                if sub_full.cimport:
                    self.cimports.add(sub_full.cimport)
                return sub_full.cython
        sub = self.substitutions.get(name)
        if sub is not None:
            if sub.cimport:
                self.cimports.add(sub.cimport)
            if args is None:
                return sub.cython
            return sub.cython + self._render_args(args, keep=len(args))

        if args is None:
            hit = self._std_simple(base)
            if hit is not None:
                return hit
            if base in _STDINT or base.removeprefix("std::") in _STDINT:
                short = base.removeprefix("std::")
                self.cimports.add(f"from libc.stdint cimport {short}")
                return short
            return self._resolve_plain(base)

        hit = self._std_template(name, args)
        if hit is not None:
            return hit
        return self._resolve_plain(name) + self._render_args(
            args, keep=len(args)
        )

    def _std_simple(self, name: str) -> Optional[str]:
        """Look up a non-template std type, resolving unqualified aliases
        spelled inside a wrapped namespace against the qualified keys."""
        candidates = [name]
        if "::" not in name:
            candidates += [f"{ns}::{name}" for ns in sorted(self.local_namespaces)]
            candidates.append(f"std::{name}")
        for cand in candidates:
            if cand in _STD_SIMPLE:
                cy, imp = _STD_SIMPLE[cand]
                if imp:
                    self.cimports.add(imp)
                return cy
        return None

    def _std_template(self, name: str, args: List[str]) -> Optional[str]:
        """Look up a std/smart-pointer template, resolving unqualified alias
        template names (``shared_ptr<T>`` spelled inside namespace pcl)
        against the qualified keys (``pcl::shared_ptr``)."""
        candidates = [name]
        if "::" not in name:
            candidates += [f"{ns}::{name}" for ns in sorted(self.local_namespaces)]
            candidates.append(f"std::{name}")
        for cand in candidates:
            if cand in _STD_TEMPLATES:
                cy, imp, keep = _STD_TEMPLATES[cand]
                self.cimports.add(imp)
                return cy + self._render_args(args, keep=keep)
        return None

    def _translate_function_type(self, s: str) -> str:
        """Translate a bare function type (``int (Foo&, double)``), which is
        only expressible inside template argument lists."""
        m = re.fullmatch(r"([^()]+?)\s*\((.*)\)", s)
        if m is None:
            raise UnsupportedTypeError(
                f"function/array type not supported: {s!r}"
            )
        ret = self._translate(m.group(1))
        inner = m.group(2).strip()
        if not inner or inner == "void":
            return f"{ret}()"
        args = ", ".join(
            self._translate(a) for a in _split_top_level(inner)
        )
        return f"{ret}({args})"

    def _render_args(self, args: List[str], keep: int) -> str:
        kept = args[:keep] if keep else args
        for a in kept:
            # Non-type template arguments (Histogram<32>, Matrix<float,4,1>)
            # cannot be declared in Cython; fail loudly so the parser can
            # skip the enclosing declaration with a warning instead of
            # emitting an uncompilable pxd.
            if _NONTYPE_ARG_RE.fullmatch(a):
                raise UnsupportedTypeError(
                    f"non-type template argument {a!r} not declarable "
                    "in Cython"
                )
        rendered = ", ".join(self._translate(a) for a in kept)
        return f"[{rendered}]"

    def _resolve_plain(self, name: str) -> str:
        """Resolve a (possibly qualified) record/enum/typedef name.

        - Bare identifiers must be declared in this pxd (``known_names``, a
          scope, or brought in via cimports) — anything else raises so the
          parser can skip the enclosing declaration WITH a warning instead
          of emitting text Cython rejects.
        - ``pcl::PointXYZ`` -> ``PointXYZ`` when "pcl" is a local namespace.
        - ``Outer::Inner`` -> ``Outer.Inner`` when ``Outer`` is a class
          declared in this pxd (Cython's nested-type syntax).
        - ``pcl::PointXYZ`` -> ``PointXYZ`` when the header being wrapped
          lives in a DIFFERENT namespace but the name was brought in with
          an extra cimport (a C++ shim in its own namespace referring to
          the library's types).
        """
        parts = [p for p in name.split("::") if p]
        if not parts:
            raise UnsupportedTypeError(f"could not resolve type {name!r}")
        # Strip the longest local-namespace prefix (handles nested wrapped
        # namespaces like pcl::io as well as plain pcl).
        for cut in range(len(parts) - 1, 0, -1):
            if "::".join(parts[:cut]) in self.local_namespaces:
                parts = parts[cut:]
                break
        if not parts:
            raise UnsupportedTypeError(f"could not resolve type {name!r}")
        head = parts[0]
        if not self._is_known(head):
            # A qualifier that is not a local namespace still resolves when
            # the unqualified name is one this pxd knows -- the case of a
            # shim declared in its own namespace whose signatures name the
            # wrapped library's types (`pclcompat::CloudCallback::connect
            # (pcl::PCDGrabber<pcl::PointXYZ>*)`). Cython has no namespace
            # qualification for cimported names anyway: the cimport IS the
            # statement of what the bare name means. Only the tail is
            # accepted, and only when it is already known, so an unknown
            # type still raises and the caller still skips with a warning.
            if len(parts) > 1 and self._is_known(parts[-1]):
                return parts[-1]
            raise UnsupportedTypeError(
                f"{name!r} is not declared in this pxd: wrap its header, "
                "add a [typemap.substitutions] entry, or bring it in via "
                "extra cimports"
            )
        return ".".join(parts)


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


def _split_top_level(s: str) -> List[str]:
    """Split on commas that sit outside any ``<>`` or ``()`` nesting."""
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in s:
        if ch in "<(":
            depth += 1
        elif ch in ">)":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


def _split_template(s: str) -> Tuple[str, Optional[List[str]]]:
    """Split ``std::map<K, V>`` into (``std::map``, [``K``, ``V``])."""
    lt = s.find("<")
    if lt == -1:
        return s, None
    if not s.endswith(">"):
        raise UnsupportedTypeError(f"unbalanced template brackets: {s!r}")
    name = s[:lt]
    inner = s[lt + 1 : -1]
    return name, _split_top_level(inner)
