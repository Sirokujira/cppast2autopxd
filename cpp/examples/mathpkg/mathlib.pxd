from libc.stdint cimport int8_t
from libc.stdint cimport int16_t
from libc.stdint cimport int32_t
from libc.stdint cimport int64_t
from libc.stdint cimport uint8_t
from libc.stdint cimport uint16_t
from libc.stdint cimport uint32_t
from libc.stdint cimport uint64_t


cdef extern from "mathlib.h" namespace "mathlib":
    int add(int a, int b) nogil
    double hypot2(double x, double y) nogil
    cdef cppclass Accumulator:
        Accumulator()
        Accumulator(double initial)
        void add(double v) nogil
        double total() nogil const
        int64_t count() nogil const
