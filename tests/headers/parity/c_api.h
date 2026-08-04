/* c_api.h - pure C header (no namespaces, C linkage) to test C support. */
#ifndef C_API_H
#define C_API_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct vec3 {
  double x;
  double y;
  double z;
} vec3;

typedef enum status {
  STATUS_OK = 0,
  STATUS_ERROR = 1,
} status;

status vec3_add(const vec3* a, const vec3* b, vec3* out);
double vec3_dot(const vec3* a, const vec3* b);
size_t buffer_size(uint32_t count);

#ifdef __cplusplus
}
#endif

#endif /* C_API_H */
