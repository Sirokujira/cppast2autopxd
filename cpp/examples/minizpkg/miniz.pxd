from libc.stddef cimport size_t
from libc.stddef cimport ptrdiff_t
from libc.stddef cimport wchar_t
from libc.time cimport time_t
from libc.stdint cimport int8_t
from libc.stdint cimport int16_t
from libc.stdint cimport int32_t
from libc.stdint cimport int64_t
from libc.stdint cimport uint8_t
from libc.stdint cimport uint16_t
from libc.stdint cimport uint32_t
from libc.stdint cimport uint64_t
from libc.stdio cimport FILE


cdef extern from "miniz.h":




    ctypedef unsigned long mz_ulong
    void mz_free(void* p) nogil
    mz_ulong mz_adler32(mz_ulong adler, const unsigned char* ptr, size_t buf_len) nogil
    mz_ulong mz_crc32(mz_ulong crc, const unsigned char* ptr, size_t buf_len) nogil
    cdef enum tdefl_status:
        MZ_DEFAULT_STRATEGY = 0
        MZ_FILTERED = 1
        MZ_HUFFMAN_ONLY = 2
        MZ_RLE = 3
        MZ_FIXED = 4
    ctypedef void*(*mz_alloc_func)(void*, size_t, size_t)
    ctypedef void(*mz_free_func)(void*, void*)
    ctypedef void*(*mz_realloc_func)(void*, void*, size_t, size_t)
    cdef enum tdefl_flush:
        MZ_NO_COMPRESSION = 0
        MZ_BEST_SPEED = 1
        MZ_BEST_COMPRESSION = 9
        MZ_UBER_COMPRESSION = 10
        MZ_DEFAULT_LEVEL = 6
        MZ_DEFAULT_COMPRESSION = -1
    cdef enum tinfl_status:
        MZ_NO_FLUSH = 0
        MZ_PARTIAL_FLUSH = 1
        MZ_SYNC_FLUSH = 2
        MZ_FULL_FLUSH = 3
        MZ_FINISH = 4
        MZ_BLOCK = 5
    cdef enum mz_zip_mode:
        MZ_OK = 0
        MZ_STREAM_END = 1
        MZ_NEED_DICT = 2
        MZ_ERRNO = -1
        MZ_STREAM_ERROR = -2
        MZ_DATA_ERROR = -3
        MZ_MEM_ERROR = -4
        MZ_BUF_ERROR = -5
        MZ_VERSION_ERROR = -6
        MZ_PARAM_ERROR = -10000
    cdef struct mz_internal_state:
        pass
    cdef struct mz_stream_s:
        const unsigned char* next_in
        unsigned int avail_in
        mz_ulong total_in
        unsigned char* next_out
        unsigned int avail_out
        mz_ulong total_out
        char* msg
        mz_internal_state* state
        mz_alloc_func zalloc
        mz_free_func zfree
        void* opaque
        int data_type
        mz_ulong adler
        mz_ulong reserved
    ctypedef mz_stream_s mz_stream
    ctypedef mz_stream* mz_streamp
    const char* mz_version() nogil
    int mz_deflateInit(mz_streamp pStream, int level) nogil
    int mz_deflateInit2(mz_streamp pStream, int level, int method, int window_bits, int mem_level, int strategy) nogil
    int mz_deflateReset(mz_streamp pStream) nogil
    int mz_deflate(mz_streamp pStream, int flush) nogil
    int mz_deflateEnd(mz_streamp pStream) nogil
    mz_ulong mz_deflateBound(mz_streamp pStream, mz_ulong source_len) nogil
    int mz_compress(unsigned char* pDest, mz_ulong* pDest_len, const unsigned char* pSource, mz_ulong source_len) nogil
    int mz_compress2(unsigned char* pDest, mz_ulong* pDest_len, const unsigned char* pSource, mz_ulong source_len, int level) nogil
    mz_ulong mz_compressBound(mz_ulong source_len) nogil
    int mz_inflateInit(mz_streamp pStream) nogil
    int mz_inflateInit2(mz_streamp pStream, int window_bits) nogil
    int mz_inflateReset(mz_streamp pStream) nogil
    int mz_inflate(mz_streamp pStream, int flush) nogil
    int mz_inflateEnd(mz_streamp pStream) nogil
    int mz_uncompress(unsigned char* pDest, mz_ulong* pDest_len, const unsigned char* pSource, mz_ulong source_len) nogil
    int mz_uncompress2(unsigned char* pDest, mz_ulong* pDest_len, const unsigned char* pSource, mz_ulong* pSource_len) nogil
    const char* mz_error(int err) nogil
    ctypedef unsigned char Byte
    ctypedef unsigned int uInt
    ctypedef mz_ulong uLong
    ctypedef Byte Bytef
    ctypedef uInt uIntf
    ctypedef char charf
    ctypedef int intf
    ctypedef void* voidpf
    ctypedef uLong uLongf
    ctypedef void* voidp
    ctypedef void* voidpc
    ctypedef unsigned char mz_uint8
    ctypedef short mz_int16
    ctypedef unsigned short mz_uint16
    ctypedef unsigned int mz_uint32
    ctypedef unsigned int mz_uint
    ctypedef int64_t mz_int64
    ctypedef uint64_t mz_uint64
    ctypedef int mz_bool
    extern void* miniz_def_alloc_func(void* opaque, size_t items, size_t size) nogil
    extern void miniz_def_free_func(void* opaque, void* address) nogil
    extern void* miniz_def_realloc_func(void* opaque, void* address, size_t items, size_t size) nogil
    cdef enum mz_zip_flags:
        TDEFL_HUFFMAN_ONLY = 0
        TDEFL_DEFAULT_MAX_PROBES = 128
        TDEFL_MAX_PROBES_MASK = 0xFFF
    cdef enum mz_zip_type:
        TDEFL_WRITE_ZLIB_HEADER = 0x01000
        TDEFL_COMPUTE_ADLER32 = 0x02000
        TDEFL_GREEDY_PARSING_FLAG = 0x04000
        TDEFL_NONDETERMINISTIC_PARSING_FLAG = 0x08000
        TDEFL_RLE_MATCHES = 0x10000
        TDEFL_FILTER_MATCHES = 0x20000
        TDEFL_FORCE_ALL_STATIC_BLOCKS = 0x40000
        TDEFL_FORCE_ALL_RAW_BLOCKS = 0x80000
    void* tdefl_compress_mem_to_heap(const void* pSrc_buf, size_t src_buf_len, size_t* pOut_len, int flags) nogil
    size_t tdefl_compress_mem_to_mem(void* pOut_buf, size_t out_buf_len, const void* pSrc_buf, size_t src_buf_len, int flags) nogil
    void* tdefl_write_image_to_png_file_in_memory_ex(const void* pImage, int w, int h, int num_chans, size_t* pLen_out, mz_uint level, mz_bool flip) nogil
    void* tdefl_write_image_to_png_file_in_memory(const void* pImage, int w, int h, int num_chans, size_t* pLen_out) nogil
    ctypedef mz_bool(*tdefl_put_buf_func_ptr)(const void*, int, void*)
    mz_bool tdefl_compress_mem_to_output(const void* pBuf, size_t buf_len, tdefl_put_buf_func_ptr pPut_buf_func, void* pPut_buf_user, int flags) nogil
    cdef enum mz_zip_error:
        TDEFL_MAX_HUFF_TABLES = 3
        TDEFL_MAX_HUFF_SYMBOLS_0 = 288
        TDEFL_MAX_HUFF_SYMBOLS_1 = 32
        TDEFL_MAX_HUFF_SYMBOLS_2 = 19
        TDEFL_LZ_DICT_SIZE = 32768
        TDEFL_LZ_DICT_SIZE_MASK = -1
        TDEFL_MIN_MATCH_LEN = 3
        TDEFL_MAX_MATCH_LEN = 258
    cdef enum:
        TDEFL_LZ_CODE_BUF_SIZE = 1024
        TDEFL_OUT_BUF_SIZE = 10
        TDEFL_MAX_HUFF_SYMBOLS = 288
        TDEFL_LZ_HASH_BITS = 15
        TDEFL_LEVEL1_HASH_SIZE_MASK = 4095
        TDEFL_LZ_HASH_SHIFT = +3
        TDEFL_LZ_HASH_SIZE = 1
    cdef struct tdefl_compressor:
        tdefl_put_buf_func_ptr m_pPut_buf_func
        void* m_pPut_buf_user
        mz_uint m_flags
        mz_uint m_max_probes[2]
        int m_greedy_parsing
        mz_uint m_adler32
        mz_uint m_lookahead_pos
        mz_uint m_lookahead_size
        mz_uint m_dict_size
        mz_uint8* m_pLZ_code_buf
        mz_uint8* m_pLZ_flags
        mz_uint8* m_pOutput_buf
        mz_uint8* m_pOutput_buf_end
        mz_uint m_num_flags_left
        mz_uint m_total_lz_bytes
        mz_uint m_lz_code_buf_dict_pos
        mz_uint m_bits_in
        mz_uint m_bit_buffer
        mz_uint m_saved_match_dist
        mz_uint m_saved_match_len
        mz_uint m_saved_lit
        mz_uint m_output_flush_ofs
        mz_uint m_output_flush_remaining
        mz_uint m_finished
        mz_uint m_block_index
        mz_uint m_wants_to_finish
        tdefl_status m_prev_return_status
        const void* m_pIn_buf
        void* m_pOut_buf
        size_t* m_pIn_buf_size
        size_t* m_pOut_buf_size
        tdefl_flush m_flush
        const mz_uint8* m_pSrc
        size_t m_src_buf_left
        size_t m_out_buf_ofs
        mz_uint8 m_dict[33025]
        mz_uint16 m_huff_count[3][288]
        mz_uint16 m_huff_codes[3][288]
        mz_uint8 m_huff_code_sizes[3][288]
        mz_uint8 m_lz_code_buf[65536]
        mz_uint16 m_next[32768]
        mz_uint16 m_hash[32768]
        mz_uint8 m_output_buf[85196]
    tdefl_status tdefl_init(tdefl_compressor* d, tdefl_put_buf_func_ptr pPut_buf_func, void* pPut_buf_user, int flags) nogil
    tdefl_status tdefl_compress(tdefl_compressor* d, const void* pIn_buf, size_t* pIn_buf_size, void* pOut_buf, size_t* pOut_buf_size, tdefl_flush flush) nogil
    tdefl_status tdefl_compress_buffer(tdefl_compressor* d, const void* pIn_buf, size_t in_buf_size, tdefl_flush flush) nogil
    tdefl_status tdefl_get_prev_return_status(tdefl_compressor* d) nogil
    mz_uint32 tdefl_get_adler32(tdefl_compressor* d) nogil
    mz_uint tdefl_create_comp_flags_from_zip_params(int level, int window_bits, int strategy) nogil
    tdefl_compressor* tdefl_compressor_alloc() nogil
    void tdefl_compressor_free(tdefl_compressor* pComp) nogil
    cdef enum:
        TINFL_FLAG_PARSE_ZLIB_HEADER = 1
        TINFL_FLAG_HAS_MORE_INPUT = 2
        TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF = 4
        TINFL_FLAG_COMPUTE_ADLER32 = 8
    void* tinfl_decompress_mem_to_heap(const void* pSrc_buf, size_t src_buf_len, size_t* pOut_len, int flags) nogil
    size_t tinfl_decompress_mem_to_mem(void* pOut_buf, size_t out_buf_len, const void* pSrc_buf, size_t src_buf_len, int flags) nogil
    ctypedef int(*tinfl_put_buf_func_ptr)(const void*, int, void*)
    int tinfl_decompress_mem_to_callback(const void* pIn_buf, size_t* pIn_buf_size, tinfl_put_buf_func_ptr pPut_buf_func, void* pPut_buf_user, int flags) nogil
    cdef struct tinfl_decompressor_tag:
        pass
    ctypedef tinfl_decompressor_tag tinfl_decompressor
    tinfl_decompressor* tinfl_decompressor_alloc() nogil
    void tinfl_decompressor_free(tinfl_decompressor* pDecomp) nogil
    tinfl_status tinfl_decompress(tinfl_decompressor* r, const mz_uint8* pIn_buf_next, size_t* pIn_buf_size, mz_uint8* pOut_buf_start, mz_uint8* pOut_buf_next, size_t* pOut_buf_size, mz_uint32 decomp_flags) nogil
    cdef enum:
        TINFL_MAX_HUFF_TABLES = 3
        TINFL_MAX_HUFF_SYMBOLS_0 = 288
        TINFL_MAX_HUFF_SYMBOLS_1 = 32
        TINFL_MAX_HUFF_SYMBOLS_2 = 19
        TINFL_FAST_LOOKUP_BITS = 10
        TINFL_FAST_LOOKUP_SIZE = 1
    ctypedef mz_uint64 tinfl_bit_buf_t
    cdef struct tinfl_decompressor_tag:
        mz_uint32 m_state
        mz_uint32 m_num_bits
        mz_uint32 m_zhdr0
        mz_uint32 m_zhdr1
        mz_uint32 m_z_adler32
        mz_uint32 m_final
        mz_uint32 m_type
        mz_uint32 m_check_adler32
        mz_uint32 m_dist
        mz_uint32 m_counter
        mz_uint32 m_num_extra
        mz_uint32 m_table_sizes[3]
        tinfl_bit_buf_t m_bit_buf
        size_t m_dist_from_out_buf_start
        mz_int16 m_look_up[3][1024]
        mz_int16 m_tree_0[576]
        mz_int16 m_tree_1[64]
        mz_int16 m_tree_2[38]
        mz_uint8 m_code_size_0[288]
        mz_uint8 m_code_size_1[32]
        mz_uint8 m_code_size_2[19]
        mz_uint8 m_raw_header[4]
        mz_uint8 m_len_codes[457]
    cdef enum:
        MZ_ZIP_MAX_IO_BUF_SIZE = 1024
        MZ_ZIP_MAX_ARCHIVE_FILENAME_SIZE = 512
        MZ_ZIP_MAX_ARCHIVE_FILE_COMMENT_SIZE = 512
    cdef struct mz_zip_archive_file_stat:
        mz_uint32 m_file_index
        mz_uint64 m_central_dir_ofs
        mz_uint16 m_version_made_by
        mz_uint16 m_version_needed
        mz_uint16 m_bit_flag
        mz_uint16 m_method
        mz_uint32 m_crc32
        mz_uint64 m_comp_size
        mz_uint64 m_uncomp_size
        mz_uint16 m_internal_attr
        mz_uint32 m_external_attr
        mz_uint64 m_local_header_ofs
        mz_uint32 m_comment_size
        mz_bool m_is_directory
        mz_bool m_is_encrypted
        mz_bool m_is_supported
        char m_filename[512]
        char m_comment[512]
        time_t m_time
    ctypedef size_t(*mz_file_read_func)(void*, mz_uint64, void*, size_t)
    ctypedef size_t(*mz_file_write_func)(void*, mz_uint64, const void*, size_t)
    ctypedef mz_bool(*mz_file_needs_keepalive)(void*)
    cdef struct mz_zip_internal_state_tag:
        pass
    ctypedef mz_zip_internal_state_tag mz_zip_internal_state
    cdef struct mz_zip_archive:
        mz_uint64 m_archive_size
        mz_uint64 m_central_directory_file_ofs
        mz_uint32 m_total_files
        mz_zip_mode m_zip_mode
        mz_zip_type m_zip_type
        mz_zip_error m_last_error
        mz_uint64 m_file_offset_alignment
        mz_alloc_func m_pAlloc
        mz_free_func m_pFree
        mz_realloc_func m_pRealloc
        void* m_pAlloc_opaque
        mz_file_read_func m_pRead
        mz_file_write_func m_pWrite
        mz_file_needs_keepalive m_pNeeds_keepalive
        void* m_pIO_opaque
        mz_zip_internal_state* m_pState
    cdef struct mz_zip_reader_extract_iter_state:
        mz_zip_archive* pZip
        mz_uint flags
        int status
        mz_uint64 read_buf_size
        mz_uint64 read_buf_ofs
        mz_uint64 read_buf_avail
        mz_uint64 comp_remaining
        mz_uint64 out_buf_ofs
        mz_uint64 cur_file_ofs
        mz_zip_archive_file_stat file_stat
        void* pRead_buf
        void* pWrite_buf
        size_t out_blk_remain
        tinfl_decompressor inflator
        mz_uint file_crc32
    mz_bool mz_zip_reader_init(mz_zip_archive* pZip, mz_uint64 size, mz_uint flags) nogil
    mz_bool mz_zip_reader_init_mem(mz_zip_archive* pZip, const void* pMem, size_t size, mz_uint flags) nogil
    mz_bool mz_zip_reader_init_file(mz_zip_archive* pZip, const char* pFilename, mz_uint32 flags) nogil
    mz_bool mz_zip_reader_init_file_v2(mz_zip_archive* pZip, const char* pFilename, mz_uint flags, mz_uint64 file_start_ofs, mz_uint64 archive_size) nogil
    mz_bool mz_zip_reader_init_cfile(mz_zip_archive* pZip, FILE* pFile, mz_uint64 archive_size, mz_uint flags) nogil
    mz_bool mz_zip_reader_end(mz_zip_archive* pZip) nogil
    void mz_zip_zero_struct(mz_zip_archive* pZip) nogil
    mz_zip_mode mz_zip_get_mode(mz_zip_archive* pZip) nogil
    mz_zip_type mz_zip_get_type(mz_zip_archive* pZip) nogil
    mz_uint mz_zip_reader_get_num_files(mz_zip_archive* pZip) nogil
    mz_uint64 mz_zip_get_archive_size(mz_zip_archive* pZip) nogil
    mz_uint64 mz_zip_get_archive_file_start_offset(mz_zip_archive* pZip) nogil
    FILE* mz_zip_get_cfile(mz_zip_archive* pZip) nogil
    size_t mz_zip_read_archive_data(mz_zip_archive* pZip, mz_uint64 file_ofs, void* pBuf, size_t n) nogil
    mz_zip_error mz_zip_set_last_error(mz_zip_archive* pZip, mz_zip_error err_num) nogil
    mz_zip_error mz_zip_peek_last_error(mz_zip_archive* pZip) nogil
    mz_zip_error mz_zip_clear_last_error(mz_zip_archive* pZip) nogil
    mz_zip_error mz_zip_get_last_error(mz_zip_archive* pZip) nogil
    const char* mz_zip_get_error_string(mz_zip_error mz_err) nogil
    mz_bool mz_zip_reader_is_file_a_directory(mz_zip_archive* pZip, mz_uint file_index) nogil
    mz_bool mz_zip_reader_is_file_encrypted(mz_zip_archive* pZip, mz_uint file_index) nogil
    mz_bool mz_zip_reader_is_file_supported(mz_zip_archive* pZip, mz_uint file_index) nogil
    mz_uint mz_zip_reader_get_filename(mz_zip_archive* pZip, mz_uint file_index, char* pFilename, mz_uint filename_buf_size) nogil
    int mz_zip_reader_locate_file(mz_zip_archive* pZip, const char* pName, const char* pComment, mz_uint flags) nogil
    mz_bool mz_zip_reader_locate_file_v2(mz_zip_archive* pZip, const char* pName, const char* pComment, mz_uint flags, mz_uint32* file_index) nogil
    mz_bool mz_zip_reader_file_stat(mz_zip_archive* pZip, mz_uint file_index, mz_zip_archive_file_stat* pStat) nogil
    mz_bool mz_zip_is_zip64(mz_zip_archive* pZip) nogil
    size_t mz_zip_get_central_dir_size(mz_zip_archive* pZip) nogil
    mz_bool mz_zip_reader_extract_to_mem_no_alloc(mz_zip_archive* pZip, mz_uint file_index, void* pBuf, size_t buf_size, mz_uint flags, void* pUser_read_buf, size_t user_read_buf_size) nogil
    mz_bool mz_zip_reader_extract_file_to_mem_no_alloc(mz_zip_archive* pZip, const char* pFilename, void* pBuf, size_t buf_size, mz_uint flags, void* pUser_read_buf, size_t user_read_buf_size) nogil
    mz_bool mz_zip_reader_extract_to_mem(mz_zip_archive* pZip, mz_uint file_index, void* pBuf, size_t buf_size, mz_uint flags) nogil
    mz_bool mz_zip_reader_extract_file_to_mem(mz_zip_archive* pZip, const char* pFilename, void* pBuf, size_t buf_size, mz_uint flags) nogil
    void* mz_zip_reader_extract_to_heap(mz_zip_archive* pZip, mz_uint file_index, size_t* pSize, mz_uint flags) nogil
    void* mz_zip_reader_extract_file_to_heap(mz_zip_archive* pZip, const char* pFilename, size_t* pSize, mz_uint flags) nogil
    mz_bool mz_zip_reader_extract_to_callback(mz_zip_archive* pZip, mz_uint file_index, mz_file_write_func pCallback, void* pOpaque, mz_uint flags) nogil
    mz_bool mz_zip_reader_extract_file_to_callback(mz_zip_archive* pZip, const char* pFilename, mz_file_write_func pCallback, void* pOpaque, mz_uint flags) nogil
    mz_zip_reader_extract_iter_state* mz_zip_reader_extract_iter_new(mz_zip_archive* pZip, mz_uint file_index, mz_uint flags) nogil
    mz_zip_reader_extract_iter_state* mz_zip_reader_extract_file_iter_new(mz_zip_archive* pZip, const char* pFilename, mz_uint flags) nogil
    size_t mz_zip_reader_extract_iter_read(mz_zip_reader_extract_iter_state* pState, void* pvBuf, size_t buf_size) nogil
    mz_bool mz_zip_reader_extract_iter_free(mz_zip_reader_extract_iter_state* pState) nogil
    mz_bool mz_zip_reader_extract_to_file(mz_zip_archive* pZip, mz_uint file_index, const char* pDst_filename, mz_uint flags) nogil
    mz_bool mz_zip_reader_extract_file_to_file(mz_zip_archive* pZip, const char* pArchive_filename, const char* pDst_filename, mz_uint flags) nogil
    mz_bool mz_zip_reader_extract_to_cfile(mz_zip_archive* pZip, mz_uint file_index, FILE* File, mz_uint flags) nogil
    mz_bool mz_zip_reader_extract_file_to_cfile(mz_zip_archive* pZip, const char* pArchive_filename, FILE* pFile, mz_uint flags) nogil
    mz_bool mz_zip_validate_file(mz_zip_archive* pZip, mz_uint file_index, mz_uint flags) nogil
    mz_bool mz_zip_validate_archive(mz_zip_archive* pZip, mz_uint flags) nogil
    mz_bool mz_zip_validate_mem_archive(const void* pMem, size_t size, mz_uint flags, mz_zip_error* pErr) nogil
    mz_bool mz_zip_validate_file_archive(const char* pFilename, mz_uint flags, mz_zip_error* pErr) nogil
    mz_bool mz_zip_end(mz_zip_archive* pZip) nogil
    mz_bool mz_zip_writer_init(mz_zip_archive* pZip, mz_uint64 existing_size) nogil
    mz_bool mz_zip_writer_init_v2(mz_zip_archive* pZip, mz_uint64 existing_size, mz_uint flags) nogil
    mz_bool mz_zip_writer_init_heap(mz_zip_archive* pZip, size_t size_to_reserve_at_beginning, size_t initial_allocation_size) nogil
    mz_bool mz_zip_writer_init_heap_v2(mz_zip_archive* pZip, size_t size_to_reserve_at_beginning, size_t initial_allocation_size, mz_uint flags) nogil
    mz_bool mz_zip_writer_init_file(mz_zip_archive* pZip, const char* pFilename, mz_uint64 size_to_reserve_at_beginning) nogil
    mz_bool mz_zip_writer_init_file_v2(mz_zip_archive* pZip, const char* pFilename, mz_uint64 size_to_reserve_at_beginning, mz_uint flags) nogil
    mz_bool mz_zip_writer_init_cfile(mz_zip_archive* pZip, FILE* pFile, mz_uint flags) nogil
    mz_bool mz_zip_writer_init_from_reader(mz_zip_archive* pZip, const char* pFilename) nogil
    mz_bool mz_zip_writer_init_from_reader_v2(mz_zip_archive* pZip, const char* pFilename, mz_uint flags) nogil
    mz_bool mz_zip_writer_add_mem(mz_zip_archive* pZip, const char* pArchive_name, const void* pBuf, size_t buf_size, mz_uint level_and_flags) nogil
    mz_bool mz_zip_writer_add_mem_ex(mz_zip_archive* pZip, const char* pArchive_name, const void* pBuf, size_t buf_size, const void* pComment, mz_uint16 comment_size, mz_uint level_and_flags, mz_uint64 uncomp_size, mz_uint32 uncomp_crc32) nogil
    mz_bool mz_zip_writer_add_mem_ex_v2(mz_zip_archive* pZip, const char* pArchive_name, const void* pBuf, size_t buf_size, const void* pComment, mz_uint16 comment_size, mz_uint level_and_flags, mz_uint64 uncomp_size, mz_uint32 uncomp_crc32, time_t* last_modified, const char* user_extra_data_local, mz_uint user_extra_data_local_len, const char* user_extra_data_central, mz_uint user_extra_data_central_len) nogil
    mz_bool mz_zip_writer_add_read_buf_callback(mz_zip_archive* pZip, const char* pArchive_name, mz_file_read_func read_callback, void* callback_opaque, mz_uint64 max_size, const time_t* pFile_time, const void* pComment, mz_uint16 comment_size, mz_uint level_and_flags, const char* user_extra_data_local, mz_uint user_extra_data_local_len, const char* user_extra_data_central, mz_uint user_extra_data_central_len) nogil
    mz_bool mz_zip_writer_add_file(mz_zip_archive* pZip, const char* pArchive_name, const char* pSrc_filename, const void* pComment, mz_uint16 comment_size, mz_uint level_and_flags) nogil
    mz_bool mz_zip_writer_add_cfile(mz_zip_archive* pZip, const char* pArchive_name, FILE* pSrc_file, mz_uint64 max_size, const time_t* pFile_time, const void* pComment, mz_uint16 comment_size, mz_uint level_and_flags, const char* user_extra_data_local, mz_uint user_extra_data_local_len, const char* user_extra_data_central, mz_uint user_extra_data_central_len) nogil
    mz_bool mz_zip_writer_add_from_zip_reader(mz_zip_archive* pZip, mz_zip_archive* pSource_zip, mz_uint src_file_index) nogil
    mz_bool mz_zip_writer_finalize_archive(mz_zip_archive* pZip) nogil
    mz_bool mz_zip_writer_finalize_heap_archive(mz_zip_archive* pZip, void** ppBuf, size_t* pSize) nogil
    mz_bool mz_zip_writer_end(mz_zip_archive* pZip) nogil
    mz_bool mz_zip_add_mem_to_archive_file_in_place(const char* pZip_filename, const char* pArchive_name, const void* pBuf, size_t buf_size, const void* pComment, mz_uint16 comment_size, mz_uint level_and_flags) nogil
    mz_bool mz_zip_add_mem_to_archive_file_in_place_v2(const char* pZip_filename, const char* pArchive_name, const void* pBuf, size_t buf_size, const void* pComment, mz_uint16 comment_size, mz_uint level_and_flags, mz_zip_error* pErr) nogil
    void* mz_zip_extract_archive_file_to_heap(const char* pZip_filename, const char* pArchive_name, size_t* pSize, mz_uint flags) nogil
    void* mz_zip_extract_archive_file_to_heap_v2(const char* pZip_filename, const char* pArchive_name, const char* pComment, size_t* pSize, mz_uint flags, mz_zip_error* pErr) nogil
