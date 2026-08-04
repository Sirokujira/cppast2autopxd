// A C++ shim in ITS OWN namespace whose signatures name the wrapped
// library's types. This is the shape used to bridge a Python callable to
// a callback-taking C++ API: the library type names arrive fully
// qualified (`pcl::PointCloud`) while the extern block being generated is
// `namespace "shim"`, so they resolve only through the extra cimports.
#pragma once

#include <memory>

#include <pcl/point_cloud.h>
#include <pcl/point_types.h>

namespace shim {

typedef void (*CloudCallbackFn)(
    std::shared_ptr<pcl::PointCloud<pcl::PointXYZ>> cloud, void* user_data);

class CloudCallback {
public:
    CloudCallback();

    void connect(CloudCallbackFn fn, void* user_data);
    void feed(const pcl::PointXYZ& point);
    void disconnect();
    bool connected() const;
};

}  // namespace shim
