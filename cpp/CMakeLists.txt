# Copyright (C) 2020 - <t753github@gmail.com>
# This file is subject to the license terms in the LICENSE file
# found in the top-level directory of this distribution.
#
# Builds the `cppast_autopxd` tool (C/C++ header -> Cython .pxd generator)
# against a locally-cloned cppast. See bootstrap.sh / README_macos.md.

cmake_minimum_required(VERSION 3.16)
project(autopxd VERSION 0.0.2 LANGUAGES CXX)

# --- locate the cppast sources (cloned by bootstrap.sh into .deps/cppast) -----
set(CPPAST_DIR "${CMAKE_CURRENT_SOURCE_DIR}/.deps/cppast"
    CACHE PATH "Path to a cppast source checkout")
if(NOT EXISTS "${CPPAST_DIR}/CMakeLists.txt")
  message(FATAL_ERROR
    "cppast not found at ${CPPAST_DIR}.\n"
    "Run ./bootstrap.sh first (it clones cppast), or pass -DCPPAST_DIR=<path>.")
endif()

# --- point cppast at the right libclang ---------------------------------------
# cppast's external/external.cmake discovers libclang via llvm-config. Homebrew's
# llvm is keg-only (its llvm-config is not on PATH), so hand cppast the explicit
# binary. IMPORTANT: do NOT set LLVM_VERSION_EXPLICIT — that code path in cppast
# skips libclang header/lib discovery and breaks with "clang-c/Index.h not found".
if(NOT DEFINED LLVM_CONFIG_BINARY)
  if(APPLE AND EXISTS "/opt/homebrew/opt/llvm/bin/llvm-config")
    set(LLVM_CONFIG_BINARY "/opt/homebrew/opt/llvm/bin/llvm-config" CACHE FILEPATH "")
  elseif(APPLE AND EXISTS "/usr/local/opt/llvm/bin/llvm-config")
    set(LLVM_CONFIG_BINARY "/usr/local/opt/llvm/bin/llvm-config" CACHE FILEPATH "")
  endif()
endif()

# We don't need cppast's own CLI tool (it pulls in cxxopts); we vendor cxxopts.
set(build_tool OFF CACHE BOOL "" FORCE)

# Bring in cppast as a subproject. Because it is not the top-level project, its
# own tests/examples are skipped automatically; we only build the `cppast` lib.
add_subdirectory("${CPPAST_DIR}" "${CMAKE_BINARY_DIR}/cppast-build" EXCLUDE_FROM_ALL)

# --- optional Doxygen-XML doc-comment support (heavy, Qt-based; OFF) -----------
option(USE_DOXYGEN "enable Doxygen XML doc-comment support (needs doxy_parser)" OFF)

# --- the tool -----------------------------------------------------------------
add_executable(cppast_autopxd main.cpp)
target_compile_features(cppast_autopxd PRIVATE cxx_std_14)

target_include_directories(cppast_autopxd PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/compat"   # vendored cxxopts.hpp + cppast_config.h shim
    "${CMAKE_CURRENT_SOURCE_DIR}/doxy_parser/doxmlparser/include"  # doxmlintf.h (header-only)
    "${CMAKE_CURRENT_SOURCE_DIR}")

# `cppast` propagates its include dirs and libclang (link + headers) transitively.
target_link_libraries(cppast_autopxd PRIVATE cppast)

if(USE_DOXYGEN)
  target_compile_definitions(cppast_autopxd PRIVATE USE_DOXYGEN)
  add_subdirectory(doxy_parser)
  target_link_libraries(cppast_autopxd PRIVATE doxmlparser)
endif()

# Put the binary at the repo root so the docs/run_tests.sh `./cppast_autopxd`
# invocations work regardless of the build directory. (gitignored.)
set_target_properties(cppast_autopxd PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
