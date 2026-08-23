// Generated with:
//   --extra_cimport "from cross_base cimport Vec3"
//   --typemap "myindex_t=uint32_t"
// mirroring how PCLPointCloud2.h needs PCLHeader/PCLPointField from
// sibling pxds and uindex_t (declared in the unparseable pcl/types.h)
// substituted to its underlying type.
#pragma once
#include "cross_base.h"
#include "cross_types.h"
namespace xh {
struct Path {
    Vec3 origin;
    myindex_t count = 0;
};
}
