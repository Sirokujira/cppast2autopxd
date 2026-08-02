import os

import pytest

from cppast2autopxd import generate_pxd

HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = os.path.join(HERE, "headers")
MINI_PCL = os.path.join(HEADERS, "mini_pcl")


def test_rectangle():
    result = generate_pxd(
        os.path.join(HEADERS, "rectangle.hpp"),
        extern_from="rectangle.hpp",
    )
    text = result.text
    assert 'cdef extern from "rectangle.hpp" namespace "shapes" nogil:' in text
    assert "cdef cppclass Rectangle:" in text
    assert "Rectangle(int x0, int y0, int x1, int y1) except +" in text
    assert "int getArea() except +" in text
    assert "void move(int dx, int dy) except +" in text
    # public data members survive
    assert "int x0" in text


def test_point_types_flattens_anonymous_unions():
    result = generate_pxd(
        os.path.join(MINI_PCL, "pcl", "point_types.h"),
        extern_from="pcl/point_types.h",
        namespaces=["pcl"],
    )
    text = result.text
    assert 'cdef extern from "pcl/point_types.h" namespace "pcl" nogil:' in text
    # plain data structs come out as cdef struct
    assert "cdef struct PointXYZ:" in text
    for member in ("float x", "float y", "float z", "float data[4]"):
        assert member in text
    # nested unions in PointXYZRGB flatten all the way down
    assert "uint8_t r" in text
    assert "float rgb" in text
    assert "uint32_t rgba" in text
    assert "from libc.stdint cimport" in text


def test_point_cloud_template():
    result = generate_pxd(
        os.path.join(MINI_PCL, "pcl", "point_cloud.h"),
        extern_from="pcl/point_cloud.h",
        namespaces=["pcl"],
    )
    text = result.text
    assert "cdef cppclass PointCloud[PointT]:" in text
    assert "ctypedef shared_ptr[PointCloud[PointT]] Ptr" in text
    assert "vector[PointT] points" in text
    assert "size_t size() except +" in text
    # mutable-reference returns must NOT carry `except +` (Cython would
    # store the result in a by-value temp and writes through it get lost)
    assert "PointT& operator[](size_t n)\n" in text
    assert "PointT& at(size_t n)\n" in text
    assert "PointT& front()\n" in text
    assert "PointCloud(unsigned int width_, unsigned int height_) except +" in text
    assert "from libcpp.memory cimport shared_ptr" in text
    assert "from libcpp.vector cimport vector" in text


def test_features_full_matrix():
    result = generate_pxd(
        os.path.join(HEADERS, "features.hpp"),
        extern_from="features.hpp",
        namespaces=["demo"],
    )
    text = result.text
    # enums
    assert "cdef enum Color:" in text
    assert "cdef enum class Mode:" in text
    assert "RED" in text and "Fast" in text
    # typedef and using alias
    assert "ctypedef unsigned int index_t" in text
    assert "ctypedef map[string, int] name_map" in text
    # class surface
    assert "cdef cppclass Widget:" in text
    assert "Widget(int id) except +" in text
    assert "Widget(const Widget& other) except +" in text  # copy ctor kept
    assert text.count("Widget(Widget&&") == 0  # move ctor dropped
    assert "int id() except +" in text
    assert "@staticmethod" in text
    # default arguments expand into overloads (no `=*` for extern functions)
    assert "Widget make() except +" in text
    assert "Widget make(int id) except +" in text
    # mutable-ref return: no except+; const-ref return: keeps except+
    assert "double& operator[](size_t idx)\n" in text
    assert "const string& title() except +" in text
    assert "bool operator==(const Widget& other) except +" in text
    # private members skipped
    assert "secret_" not in text
    assert "hidden" not in text
    # free functions: default args expand into overloads
    assert "vector[string] split(const string& text) except +" in text
    assert "vector[string] split(const string& text, char sep) except +" in text
    assert "int add(int a, int b) except +" in text


def test_const_kept_without_except_plus():
    result = generate_pxd(
        os.path.join(HEADERS, "features.hpp"),
        extern_from="features.hpp",
        namespaces=["demo"],
        except_plus=False,
    )
    text = result.text
    assert "int id() const" in text
    assert "except +" not in text


def test_edge_cases():
    result = generate_pxd(
        os.path.join(HEADERS, "edge_cases.hpp"),
        extern_from="edge_cases.hpp",
    )
    text = result.text

    # extern "C" blocks are transparent (LINKAGE_SPEC)
    assert "cdef struct CPoint:" in text
    assert "int c_distance(const CPoint* a, const CPoint* b) except +" in text

    # named union at namespace scope
    assert "cdef union Blob:" in text
    assert "unsigned char bytes[4]" in text

    # anonymous enum at namespace scope
    assert "cdef enum:\n" in text
    assert "ANON_FIRST" in text

    # named union field kept; truly anonymous union flattened; unnamed
    # union typing a named field NOT flattened (warning instead)
    assert "Blob blob" in text
    assert "float fast" in text
    assert "double precise" in text
    assert "float u" not in text
    assert any("named field" in w for w in result.warnings)

    # nested enum before the typedef that references it, no `cdef` inside
    # the cppclass, nested named union present
    assert "        enum Mode:" in text
    assert "        ctypedef Mode mode_t" in text
    assert text.index("enum Mode:") < text.index("ctypedef Mode mode_t")
    assert "        union Slot:" in text
    assert "        enum:\n" in text  # anonymous enum inside the class
    assert "cdef enum Mode" not in text  # nested: no cdef prefix

    # array parameter: exactly one signature, no phantom overloads
    assert text.count("void configure(") == 1
    assert "void configure(const float* matrix) except +" in text
    # genuine default: two overloads
    assert "void tune(int level) except +" in text
    assert "void tune(int level, double gain) except +" in text

    # interleaved namespaces keep source order (other::Middle before its use)
    assert text.index("cdef struct Middle:") < text.index("Middle payload")


def test_typemap_regressions_in_generation():
    """ostream methods are skipped with a warning, not emitted broken."""
    import textwrap

    tmp = os.path.join(HEADERS, "..", "_tmp_printer.hpp")
    with open(tmp, "w") as fh:
        fh.write(
            textwrap.dedent(
                """
                #include <iosfwd>
                namespace demo {
                class Printer {
                public:
                    void dump(std::ostream& os) const;
                    int level() const;
                };
                }
                """
            )
        )
    try:
        result = generate_pxd(tmp, namespaces=["demo"])
        assert "ostream" not in result.text
        assert "int level() except +" in result.text
        assert any("dump" in w for w in result.warnings)
    finally:
        os.remove(tmp)


def test_banner_and_distutils_header():
    result = generate_pxd(os.path.join(HEADERS, "rectangle.hpp"))
    assert result.text.startswith("# Auto-generated by cppast2autopxd")
    assert "# distutils: language = c++" in result.text


def test_missing_header_raises():
    from cppast2autopxd.parser import ParseError

    with pytest.raises(ParseError):
        generate_pxd(os.path.join(HEADERS, "no_such_file.hpp"))
