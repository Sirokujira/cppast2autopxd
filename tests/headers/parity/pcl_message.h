// Self-contained stand-in for PCL's common message headers
// (PCLPointField.h / PCLPointCloud2.h / PolygonMesh.h shapes) — the
// constructs behind FEASIBILITY #42-#46: a nested enum with non-literal
// values (whose expressions carry identifiers/keywords of their own),
// globally-qualified self references (` ::pcl::...`), an operator+=
// overload Cython cannot express, a std::bitset member with no libcpp
// module, and an <algorithm> include that must not become a bogus
// self-import.
#pragma once

#include <algorithm>
#include <bitset>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace pcl {

namespace traits {
template <typename T> constexpr std::uint8_t asEnum_v = 0;
}

struct PCLField {
    std::string name;
    std::uint32_t offset = 0;

    enum FieldTypes {
        BOOL = traits::asEnum_v<bool>,
        INT8 = traits::asEnum_v<std::int8_t>,
        FLOAT32 = traits::asEnum_v<float>,
        UNSET = 0
    };

    std::bitset<8> flags;

    typedef std::shared_ptr< ::pcl::PCLField> Ptr;
    typedef std::shared_ptr<const ::pcl::PCLField> ConstPtr;
};

struct PCLMesh {
    std::vector<PCLField> fields;

    PCLMesh& operator+=(const PCLMesh& rhs);
    PCLMesh operator+(const PCLMesh& rhs);
};

using PCLFieldPtr = PCLField::Ptr;

}  // namespace pcl
