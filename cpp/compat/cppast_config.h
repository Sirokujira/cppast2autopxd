// compat/cppast_config.h
//
// Shim for older cppast layouts. main.cpp does `#include <cppast_config.h>`
// and uses CPPAST_VERSION_STRING / CPPAST_CLANG_VERSION_STRING in the
// `--version` output. Older cppast generated this header (and a matching
// cppast_config.cpp defining cppast::cppast_initialize()); current cppast
// dropped the generated header entirely and exposes the version macros only as
// PRIVATE compile-definitions while building the library itself — so consumers
// no longer receive them.
//
// This header provides safe fallbacks so the tool builds against either layout.
// (The real values are not essential; they only appear in `--version`.)
#pragma once

#ifndef CPPAST_VERSION_STRING
#define CPPAST_VERSION_STRING "unknown (vendored cppast)"
#endif

#ifndef CPPAST_CLANG_VERSION_STRING
#define CPPAST_CLANG_VERSION_STRING "see `llvm-config --version`"
#endif
