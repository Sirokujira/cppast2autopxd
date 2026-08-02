import pytest

from cppast2autopxd.typemap import (
    Substitution,
    TypeMapper,
    UnsupportedTypeError,
)


def make_mapper(**kwargs):
    m = TypeMapper(**kwargs)
    m.local_namespaces.add("pcl")
    return m


def test_builtins_pass_through():
    m = make_mapper()
    assert m.cython_type("int") == "int"
    assert m.cython_type("unsigned long long") == "unsigned long long"
    assert m.cython_type("void") == "void"


def test_pointers_and_references():
    m = make_mapper()
    assert m.cython_type("int *") == "int*"
    assert m.cython_type("const float &") == "const float&"
    assert m.cython_type("char **") == "char**"


def test_std_string_and_vector():
    m = make_mapper()
    assert m.cython_type("std::string") == "string"
    assert "from libcpp.string cimport string" in m.cimports
    assert m.cython_type("std::vector<int>") == "vector[int]"
    assert "from libcpp.vector cimport vector" in m.cimports


def test_vector_allocator_dropped():
    m = make_mapper()
    spelled = "std::vector<pcl::PointXYZ, Eigen::aligned_allocator<pcl::PointXYZ>>"
    assert m.cython_type(spelled) == "vector[PointXYZ]"


def test_map_keeps_two_args():
    m = make_mapper()
    assert (
        m.cython_type("std::map<std::string, int, std::less<std::string>>")
        == "map[string, int]"
    )


def test_shared_ptr_variants():
    m = make_mapper()
    assert m.cython_type("std::shared_ptr<pcl::PointCloud<pcl::PointXYZ>>") == (
        "shared_ptr[PointCloud[PointXYZ]]"
    )
    assert m.cython_type("boost::shared_ptr<pcl::PointXYZ>") == (
        "shared_ptr[PointXYZ]"
    )
    assert m.cython_type("pcl::shared_ptr<pcl::PointXYZ>") == (
        "shared_ptr[PointXYZ]"
    )
    assert "from libcpp.memory cimport shared_ptr" in m.cimports


def test_stdint():
    m = make_mapper()
    assert m.cython_type("std::uint8_t") == "uint8_t"
    assert m.cython_type("uint32_t") == "uint32_t"
    assert "from libc.stdint cimport uint8_t" in m.cimports


def test_local_namespace_stripped():
    m = make_mapper()
    assert m.cython_type("pcl::PointXYZ") == "PointXYZ"
    assert m.cython_type("const pcl::PointXYZ &") == "const PointXYZ&"


def test_unknown_namespace_rejected():
    m = make_mapper()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("Eigen::Vector4f")


def test_substitution():
    m = make_mapper(
        substitutions={
            "Eigen::Vector4f": Substitution(
                cython="Vector4f",
                cimport="from pcl.eigen cimport Vector4f",
            )
        }
    )
    assert m.cython_type("Eigen::Vector4f") == "Vector4f"
    assert "from pcl.eigen cimport Vector4f" in m.cimports


def test_rvalue_reference_rejected():
    m = make_mapper()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("Widget &&")


def test_function_pointer_rejected():
    m = make_mapper()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("void (*)(int)")


def test_bool_maps_to_libcpp_bool():
    m = make_mapper()
    assert m.cython_type("bool") == "bool"
    assert "from libcpp cimport bool" in m.cimports
