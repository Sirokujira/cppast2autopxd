// Copyright (C) 2018 Tooru Oonuma <t753github@gmail.com>
// This file is subject to the license terms in the LICENSE file
// found in the top-level directory of this distribution.

#include <fstream>
#include <iostream>
#include <cstdlib>
#include <cstdio>
#include <string>

#include <cppast_config.h>

// cxxopts splits a std::vector<> option's value on commas. Nothing this tool
// takes is ever a comma-separated LIST — every repeatable option is passed
// once per value — and the split silently mangled the values that do contain
// commas: `--extra_cimport "from m cimport A, B"` arrived as two entries and
// the second reached the pxd as a stray indented line (invalid Cython, exit
// 0), which is the multi-symbol form python-pcl_skbuild's config uses in five
// places. A --typemap TO like `vector[pair[int, int]]` broke the same way.
// Take each value verbatim instead.
#define CXXOPTS_VECTOR_DELIMITER '\0'
#include <cxxopts.hpp>

#include <cppast/code_generator.hpp>         // for generate_code()
#include <cppast/cpp_entity_kind.hpp>        // for the cpp_entity_kind definition
#include <cppast/cpp_forward_declarable.hpp> // for is_definition()
#include <cppast/cpp_namespace.hpp>          //s for cpp_namespace
#include <cppast/libclang_parser.hpp> // for libclang_parser, libclang_compile_config, cpp_entity,...
#include <cppast/visitor.hpp>         // for visit()

// pxd ファイル書き出し
// #include "autopxd.h"
// ロジック実装込のヘッダとして読み込む?
#include "autopxd.hpp"

AutoPxd* autopxd;

// print help options
void
print_help(const cxxopts::Options& options)
// void print_help(cxxopts::ParseResult& options)
{
  std::cout << options.help({"", "compilation"}) << '\n';
}

// print error message
void
print_error(const std::string& msg) {
  std::cerr << msg << '\n';
}

// prints the AST entry of a cpp_entity (base class for all entities),
// will only print a single line
void
autopxd_entity(std::ofstream& out, const cppast::cpp_entity& e) {
  // print name and the kind of the entity
  if (!e.name().empty())
    // 対象項目
    out << e.name();
  else
    // 変数がよくわからないとき(using とかもここに入る)
    out << "<anonymous>";

  // 種類
  // include directive ->
  // macro definition ->
  // namespace
  // class
  // class template
  // function
  // member variable
  // member function
  // access specifier
  out << " (" << cppast::to_string(e.kind()) << ")";

  // print whether or not it is a definition
  if (cppast::is_definition(e)) {
    // define ?
    // 内部は?
    // out << " [definition]";
    // pxd の記述として書き出す
    // e.kind() == "variant" + is_definition() == true
  }

  if (e.kind() == cppast::cpp_entity_kind::language_linkage_t) {
    // no need to print additional information for language linkages
    out << '\n';
  } else if (e.kind() == cppast::cpp_entity_kind::namespace_t) {
    // cast to cpp_namespace
    auto& ns = static_cast<const cppast::cpp_namespace&>(e);
    // print whether or not it is inline
    if (ns.is_inline())
      // inline 関数?
      out << " [inline]";
    out << '\n';
  } else {
    // print the declaration of the entity
    // it will only use a single line
    // derive from code_generator and implement various callbacks for printing
    // it will print into a std::string
    class code_generator : public cppast::code_generator {
      std::string str_;          // the result
      bool was_newline_ = false; // whether or not the last token was a newline
                                 // needed for lazily printing them

    public:
      code_generator(const cppast::cpp_entity& e) {
        // kickoff code generation here
        cppast::generate_code(*this, e);
      }

      // return the result
      const std::string&
      str() const noexcept {
        return str_;
      }

    private:
      // called to retrieve the generation options of an entity
      generation_options
      do_get_options(const cppast::cpp_entity&, cppast::cpp_access_specifier_kind) override {
        // generate declaration only
        return code_generator::declaration;
      }

      // no need to handle indentation, as only a single line is used
      void
      do_indent() override {}
      void
      do_unindent() override {}

      // called when a generic token sequence should be generated
      // there are specialized callbacks for various token kinds,
      // to e.g. implement syntax highlighting
      void
      do_write_token_seq(cppast::string_view tokens) override {
        if (was_newline_) {
          // lazily append newline as space
          str_ += ' ';
          was_newline_ = false;
        }
        // append tokens
        str_ += tokens.c_str();
      }

      // called when a newline should be generated
      // we're lazy as it will always generate a trailing newline,
      // we don't want
      void
      do_write_newline() override {
        was_newline_ = true;
      }

    } generator(e);

    // print generated code
    // pxd の記述として書き出す
    // case1. e.name 関数名, e.kind == function, generator 関数の定義
    out << ": `" << generator.str() << '`' << '\n';
  }
}

// prints the AST of a file
void
autopxd_ast(std::ofstream& out, const cppast::cpp_file& file) {
  // print file name
  // out << "AST for '" << file.name() << "':\n";
  std::string prefix; // the current prefix string

  // recursively visit file and all children
  cppast::visit(file, [&](const cppast::cpp_entity& e, cppast::visitor_info info) {

    if (e.kind() == cppast::cpp_entity_kind::file_t || cppast::is_templated(e) || cppast::is_friended(e))
      // no need to do anything for a file,
      // templated and friended entities are just proxies, so skip those as
      // well
      // return true to continue visit for children
      return true;
    else if (info.event == cppast::visitor_info::container_entity_exit) {
      // we have visited all children of a container,
      // remove prefix
      // 接頭文字 - 2文字削除
      prefix.pop_back();
      prefix.pop_back();
    } else {
      // 階層情報の検索
      out << prefix; // print prefix for previous entities
      // calculate next prefix
      if (info.last_child) {
        if (info.event == cppast::visitor_info::container_entity_enter)
          prefix += "  ";

        // 開始端?(階層+1)
        // out << "+-";
      } else {
        if (info.event == cppast::visitor_info::container_entity_enter)
          prefix += "| ";

        // 階層継続?
        // out << "|-";
      }

      // print_entity(out, e);
      autopxd_entity(out, e);
    }

    return true;
  });
}

// parse a file
std::unique_ptr<cppast::cpp_file>
parse_file(const cppast::libclang_compile_config& config, const cppast::diagnostic_logger& logger, const std::string& filename, bool fatal_error) {
  // the entity index is used to resolve cross references in the AST
  // we don't need that, so it will not be needed afterwards
  cppast::cpp_entity_index idx;
  // the parser is used to parse the entity
  // there can be multiple parser implementations
  cppast::libclang_parser parser(type_safe::ref(logger));
  // parse the file
  auto file = parser.parse(idx, filename, config);
  if (fatal_error && parser.error())
    return nullptr;
  return file;
}

// Read repeatable options from a config file so a caller with a fixed set of
// cross-header rules (PCL's message headers need the same cimports and the
// same uindex_t substitution on every invocation) states them once. Minimal
// on purpose: the keys ARE the CLI option names and values are taken verbatim
// after the first '=', so there is nothing to learn beyond the flags, and no
// new dependency. Returns false (with a message) on an unopenable file, a
// line without '=', or an unknown key — never silently ignores a line.
static bool
load_config_file(const std::string& path, std::vector<std::string>& extra_cimports,
                 std::vector<std::string>& typemap_substitutions,
                 std::string& extern_from) {
  std::ifstream in(path);
  if (!in) {
    print_error("cannot open config file '" + path + "'");
    return false;
  }
  std::string line;
  int lineno = 0;
  while (std::getline(in, line)) {
    lineno++;
    // tolerate a CRLF config on any platform
    if (!line.empty() && line.back() == '\r') line.pop_back();
    auto begin = line.find_first_not_of(" \t");
    if (begin == std::string::npos) continue;                 // blank
    if (line[begin] == '#') continue;                         // comment
    auto eq = line.find('=', begin);
    if (eq == std::string::npos) {
      print_error("config " + path + ":" + std::to_string(lineno) +
                  ": expected `key = value`");
      return false;
    }
    auto key_end = line.find_last_not_of(" \t", eq - 1);
    std::string key = line.substr(begin, key_end - begin + 1);
    auto val_begin = line.find_first_not_of(" \t", eq + 1);
    std::string value =
        val_begin == std::string::npos ? std::string() : line.substr(val_begin);
    while (!value.empty() && (value.back() == ' ' || value.back() == '\t'))
      value.pop_back();

    // '#' starts a comment at line start, so a caller will reasonably expect
    // a TRAILING comment to work too — but the value is taken verbatim, so it
    // would be swallowed into the rule (an extra_cimport comment even reached
    // the generated pxd, and cython accepted it). Reject rather than guess.
    if (value.find('#') != std::string::npos) {
      print_error("config " + path + ":" + std::to_string(lineno) +
                  ": '#' in a value (comments must be on their own line)");
      return false;
    }

    if (key == "extra_cimport")
      extra_cimports.push_back(value);
    else if (key == "typemap")
      typemap_substitutions.push_back(value);
    else if (key == "extern_from") {
      // Unlike the repeatable keys this one is a single value, so a second
      // entry would silently win: say which line collides instead.
      if (!extern_from.empty()) {
        print_error("config " + path + ":" + std::to_string(lineno) +
                    ": extern_from given more than once (it is a single value)");
        return false;
      }
      if (value.empty()) {
        print_error("config " + path + ":" + std::to_string(lineno) +
                    ": extern_from needs a path");
        return false;
      }
      extern_from = value;
    } else {
      // include paths and the standard belong on the command line: they feed
      // the parse config, which is already built by the time this runs.
      print_error("config " + path + ":" + std::to_string(lineno) +
                  ": unknown key '" + key +
                  "' (expected extra_cimport, typemap or extern_from)");
      return false;
    }
  }
  // Opening a DIRECTORY succeeds on libstdc++ and the first getline simply
  // fails, which used to look like an empty config: every rule silently
  // dropped, exit 0. badbit distinguishes it from a genuinely empty file.
  if (in.bad()) {
    print_error("cannot read config file '" + path + "' (is it a directory?)");
    return false;
  }
  return true;
}

int
main(int argc, char* argv[]) try {
#ifdef __APPLE__
  // Homebrew's libclang ships with no default macOS SDK sysroot, so headers
  // like <stdint.h> are not found during cppast's preprocessing step and the
  // parsed AST silently comes back empty (a 0-byte .pxd, no error). Export
  // SDKROOT (honoured by both the clang preprocessor invocation and libclang)
  // when it is not already set.
  if (!std::getenv("SDKROOT")) {
    if (FILE* sdk_pipe = popen("xcrun --show-sdk-path 2>/dev/null", "r")) {
      char buf[1024];
      if (std::fgets(buf, sizeof(buf), sdk_pipe)) {
        std::string sdk(buf);
        while (!sdk.empty() && (sdk.back() == '\n' || sdk.back() == '\r' || sdk.back() == ' '))
          sdk.pop_back();
        if (!sdk.empty())
          setenv("SDKROOT", sdk.c_str(), 1);
      }
      pclose(sdk_pipe);
    }
  }
#endif

  cxxopts::Options option_list("cppast", "cppast - The commandline interface to the cppast library.\n");
  // clang-format off
    option_list.add_options()
        ("h,help", "display this help and exit")
        ("version", "display version information and exit")
        ("v,verbose", "be verbose when parsing")
        ("fatal_errors", "abort program when a parser error occurs, instead of doing error correction")
        ("file", "the file that is being parsed (last positional argument)", cxxopts::value<std::string>());
    option_list.add_options("compilation")
        ("output_dir", "set the directory where a pxd file",
        cxxopts::value<std::string>())
        ("xml_dir", "set the directory doxygen xml files.",
        cxxopts::value<std::string>())
        ("database_dir", "set the directory where a 'compile_commands.json' file is located containing build information",
        cxxopts::value<std::string>())
        ("database_file", "set the file name whose configuration will be used regardless of the current file name",
        cxxopts::value<std::string>())
        ("std", "set the C++ standard (c++98, c++03, c++11, c++14, c++1z (experimental))",
         cxxopts::value<std::string>()->default_value(cppast::to_string(cppast::cpp_standard::cpp_latest)))
        ("I,include_directory", "add directory to include search path",
         cxxopts::value<std::vector<std::string>>())
        ("D,macro_definition", "define a macro on the command line",
         cxxopts::value<std::vector<std::string>>())
        ("U,macro_undefinition", "undefine a macro on the command line",
         cxxopts::value<std::vector<std::string>>())
        ("gnu_extensions", "enable GNU extensions (equivalent to -std=gnu++XX)")
        ("msvc_extensions", "enable MSVC extensions (equivalent to -fms-extensions)")
        ("msvc_compatibility", "enable MSVC compatibility (equivalent to -fms-compatibility)")
        ("fast_preprocessing", "enable fast preprocessing, be careful, this breaks if you e.g. redefine macros in the same file!")
        ("remove_comments_in_macro", "whether or not comments generated by macro are kept, enable if you run into errors")
        ("extra_cimport", "add a cimport line verbatim to the generated pxd (repeatable), e.g. \"from PCLHeader cimport PCLHeader\" — the counterpart of the Python implementation's extra_cimports for names declared in sibling headers",
         cxxopts::value<std::vector<std::string>>())
        ("typemap", "substitute a type name in the generated pxd, FROM=TO with word-boundary matching (repeatable), e.g. \"uindex_t=uint32_t\" — the counterpart of the Python implementation's typemap substitutions",
         cxxopts::value<std::vector<std::string>>())
        ("config", "read repeatable options from a file: lines of `key = value` where key is extra_cimport, typemap or extern_from (blank lines and whole-line #-comments ignored; a '#' inside a value is an error, since it is the comment marker). Repeatable; entries APPEND to any given on the command line",
         cxxopts::value<std::vector<std::string>>())
        ("extern_from", "write PATH into the generated `cdef extern from \"...\"` line instead of the parsed file's name, for pxd generated from a self-contained mirror header whose real counterpart the C++ compiler must include (e.g. \"pcl/point_cloud.h\") — the counterpart of the Python implementation's extern_from. Also settable as an `extern_from = ` config key; unlike the repeatable keys (which append) that one is single-valued and LOSES to this flag",
         cxxopts::value<std::string>())
        ("except_plus", "append `except +` to functions, methods and constructors so a C++ exception propagates as a Python one instead of terminating; mutable-reference returns are exempt (Cython would hand out a reference to a temporary). The counterpart of the Python implementation's except_plus")
        ("no_nogil", "do not append `nogil` to functions and methods (the counterpart of the Python implementation's nogil = false); `nogil` is emitted by default");
  // clang-format on
  option_list.parse_positional("file");

  auto options = option_list.parse(argc, argv);
  if (options.count("help")) {
    // print_help(options);
  } else if (options.count("version")) {
    // std::cout << "autopxd version " << AUTOPXD_VERSION_STRING << "\n";
    std::cout << "Using cppast version " << CPPAST_VERSION_STRING << "\n";
    std::cout << "Copyright (C) Jonathan Müller 2017-2018 "
                 "<jonathanmueller.dev@gmail.com>\n";
    std::cout << '\n';
    std::cout << "Using libclang version " << CPPAST_CLANG_VERSION_STRING << '\n';
  } else if (!options.count("file") || options["file"].as<std::string>().empty()) {
    print_error("missing file argument");
    return 1;
  } else {
    // the compile config stores compilation flags
    cppast::libclang_compile_config config;
    if (options.count("database_dir")) {
      cppast::libclang_compilation_database database(options["database_dir"].as<std::string>());
      if (options.count("database_file"))
        config = cppast::libclang_compile_config(database, options["database_file"].as<std::string>());
      else
        config = cppast::libclang_compile_config(database, options["file"].as<std::string>());
    }

    if (options.count("verbose"))
      config.write_preprocessed(true);

    if (options.count("fast_preprocessing"))
      config.fast_preprocessing(true);

    if (options.count("remove_comments_in_macro"))
      config.remove_comments_in_macro(true);

    if (options.count("include_directory"))
      for (auto& include : options["include_directory"].as<std::vector<std::string>>())
        config.add_include_dir(include);
    if (options.count("macro_definition"))
      for (auto& macro : options["macro_definition"].as<std::vector<std::string>>()) {
        auto equal = macro.find('=');
        auto name = macro.substr(0, equal);
        if (equal == std::string::npos)
          config.define_macro(std::move(name), "");
        else {
          auto def = macro.substr(equal + 1u);
          config.define_macro(std::move(name), std::move(def));
        }
      }
    if (options.count("macro_undefinition"))
      for (auto& name : options["macro_undefinition"].as<std::vector<std::string>>())
        config.undefine_macro(name);

    // the compile_flags are generic flags
    cppast::compile_flags flags;
    if (options.count("gnu_extensions"))
      flags |= cppast::compile_flag::gnu_extensions;
    if (options.count("msvc_extensions"))
      flags |= cppast::compile_flag::ms_extensions;
    if (options.count("msvc_compatibility"))
      flags |= cppast::compile_flag::ms_compatibility;

    if (options["std"].as<std::string>() == "c++98")
      config.set_flags(cppast::cpp_standard::cpp_98, flags);
    else if (options["std"].as<std::string>() == "c++03")
      config.set_flags(cppast::cpp_standard::cpp_03, flags);
    else if (options["std"].as<std::string>() == "c++11")
      config.set_flags(cppast::cpp_standard::cpp_11, flags);
    else if (options["std"].as<std::string>() == "c++14")
      config.set_flags(cppast::cpp_standard::cpp_14, flags);
    else if (options["std"].as<std::string>() == "c++1z")
      config.set_flags(cppast::cpp_standard::cpp_1z, flags);
    else {
      print_error("invalid value '" + options["std"].as<std::string>() + "' for std flag");
      return 1;
    }

    // the logger is used to print diagnostics
    cppast::stderr_diagnostic_logger logger;
    if (options.count("verbose"))
      logger.set_verbose(true);

    auto output_dir = options["output_dir"].as<std::string>();
    std::cout << output_dir << '\n';
  	
  	auto xml_dir = options["xml_dir"].as<std::string>();
    std::cout << xml_dir << '\n';

    auto file = parse_file(config, logger, options["file"].as<std::string>(), options.count("fatal_errors") == 1);

    if (!file)
      return 2;

    // std::string autopxd_file;
    // autopxd_file = file->name() + ".pxd";
    std::cout << file->name() << '\n';

    std::vector<std::string> extra_cimports;
    if (options.count("extra_cimport"))
      extra_cimports = options["extra_cimport"].as<std::vector<std::string>>();
    std::vector<std::string> typemap_substitutions;
    if (options.count("typemap"))
      typemap_substitutions = options["typemap"].as<std::vector<std::string>>();
    // config-file entries APPEND to command-line ones (never replace them)
    std::string config_extern_from;
    if (options.count("config"))
      for (auto& conf : options["config"].as<std::vector<std::string>>())
        if (!load_config_file(conf, extra_cimports, typemap_substitutions,
                              config_extern_from))
          return 1;

    std::string extern_from;
    if (options.count("extern_from")) {
      // Presence, not emptiness: `--extern_from ""` used to fall through to
      // the config key, so the flag documented as winning quietly lost. An
      // empty value is rejected here exactly as it is in a config file.
      extern_from = options["extern_from"].as<std::string>();
      if (extern_from.empty()) {
        print_error("--extern_from needs a path");
        return 1;
      }
    } else {
      extern_from = config_extern_from;
    }
    // The value is written between double quotes in `cdef extern from "..."`,
    // so a `"` inside it closes the string early and produces silently broken
    // Cython with exit 0 — the same class of trap as a '#' in a config value.
    if (extern_from.find('"') != std::string::npos) {
      print_error("extern_from must not contain '\"' (it is written inside a "
                  "quoted Cython string): " + extern_from);
      return 1;
    }

    // autopxd = new AutoPxd(file->name());
    autopxd = new AutoPxd(file->name(), output_dir, xml_dir,
                          extra_cimports, typemap_substitutions,
                          extern_from, options.count("no_nogil") == 0,
                          options.count("except_plus") == 1);

    autopxd->autopxd_ast(*file);

    delete autopxd;
  }
} catch (const cppast::libclang_error& ex) {
  print_error(std::string("[fatal parsing error] ") + ex.what());
  return 2;
}

