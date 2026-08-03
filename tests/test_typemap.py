import pytest

from cppast2autopxd.typemap import (
    Substitution,
    TypeMapper,
    UnsupportedTypeError,
)


def make_mapper(**kwargs):
    m = TypeMapper(**kwargs)
    m.local_namespaces.add("pcl")
    # Names the hypothetical pxd declares (the parser shares its declared
    # set with the mapper; unit tests seed it directly).
    m.known_names.update({"PointXYZ", "PointCloud"})
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


def test_ostream_rejected_not_silently_broken():
    m = make_mapper()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("std::ostream &")
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("std::istream &")


def test_wchar_t_maps_to_libc_stddef():
    m = make_mapper()
    assert m.cython_type("wchar_t") == "wchar_t"
    assert "from libc.stddef cimport wchar_t" in m.cimports


def test_nontype_template_args_rejected():
    m = make_mapper()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("pcl::Histogram<32>")
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("Matrix<float, 4, 1>")


def test_undeclared_bare_name_rejected():
    m = make_mapper()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("MysteryType")
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("__m128")


def test_scope_names_resolve():
    m = make_mapper()
    m.push_scope({"PointT"})
    assert m.cython_type("PointT&") == "PointT&"
    m.pop_scope()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("PointT&")


def test_nested_class_qualified_name_dotted():
    m = make_mapper()
    m.known_names.add("Machine")
    assert m.cython_type("Machine::Mode") == "Machine.Mode"
    assert m.cython_type("pcl::PointCloud::Ptr") == "PointCloud.Ptr"


def test_unqualified_shared_ptr_alias_resolves():
    """pcl::shared_ptr spelled bare inside namespace pcl still maps."""
    m = make_mapper()
    assert m.cython_type("shared_ptr<PointXYZ>") == "shared_ptr[PointXYZ]"
    assert "from libcpp.memory cimport shared_ptr" in m.cimports


def test_enum_constant_template_arg_rejected():
    """Non-literal non-type template args (enum constants) must not slip
    through as bogus type arguments."""
    m = make_mapper()
    with pytest.raises(UnsupportedTypeError):
        m.cython_type("PointCloud<LIMIT>")


def test_substitution_full_instantiation_replaces_whole_type():
    m = make_mapper(
        substitutions={
            "pcl::PointCloud<pcl::PointXYZ>": Substitution(
                cython="PointCloudXYZ",
                cimport="from pcl.cloud cimport PointCloudXYZ",
            )
        }
    )
    assert m.cython_type("pcl::PointCloud<pcl::PointXYZ>") == "PointCloudXYZ"
    assert "from pcl.cloud cimport PointCloudXYZ" in m.cimports
    # template-name-keyed substitution still keeps translated args
    m2 = make_mapper(
        substitutions={"Eigen::Map": Substitution(cython="Map")}
    )
    assert m2.cython_type("Eigen::Map<pcl::PointXYZ>") == "Map[PointXYZ]"
