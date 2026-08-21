// Self-contained stand-in mirroring pcl/PCLHeader.h — the header that exposed
// three emission gaps on real PCL (FEASIBILITY #34-#37): C++11 default member
// initializers, member typedefs inside a struct, namespace-scope aliases
// referring to a member typedef (PCLHeader::Ptr), and include-driven
// libcpp.memory imports.
#pragma once

#include <cstdint>
#include <memory>
#include <string>

namespace pcl {

struct PCLHeader {
    std::uint32_t seq = 0;
    std::uint64_t stamp = 0;
    std::string frame_id;

    typedef std::shared_ptr<PCLHeader> Ptr;
    typedef std::shared_ptr<const PCLHeader> ConstPtr;
};

using HeaderPtr = PCLHeader::Ptr;
using HeaderConstPtr = PCLHeader::ConstPtr;

}  // namespace pcl
