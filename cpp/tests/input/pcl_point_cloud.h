// Mirror header: self-contained stand-in reproducing the API surface of
// <pcl/point_cloud.h> (the subset wrapped so far; Eigen-typed members such
// as sensor_origin_ are intentionally omitted until an Eigen pxd exists).
//
// See point_types.h for why mirror headers are used.
#pragma once
// (committed gating fixture: mirror of the python-pcl_skbuild header)

#include <cstddef>
#include <memory>
#include <vector>

namespace pcl {

template <typename PointT>
class PointCloud {
public:
    typedef std::shared_ptr<PointCloud<PointT>> Ptr;
    typedef std::shared_ptr<const PointCloud<PointT>> ConstPtr;

    PointCloud();
    PointCloud(unsigned int width_, unsigned int height_);

    std::vector<PointT> points;
    unsigned int width;
    unsigned int height;
    bool is_dense;

    std::size_t size() const;
    bool empty() const;
    void clear();
    void reserve(std::size_t n);
    void resize(std::size_t count);
    void push_back(const PointT& pt);
    PointT& at(std::size_t n);
    PointT& front();
    PointT& back();
    PointT& operator[](std::size_t n);
    bool isOrganized() const;
    void swap(PointCloud<PointT>& rhs);
};

}  // namespace pcl
