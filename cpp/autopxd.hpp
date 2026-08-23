#pragma once
#include <iostream>
#include <fstream>
#include <stack>
#include <sstream>
#include <string>
#include <vector>
#include <algorithm>

#include <cctype>

#include <cppast/libclang_parser.hpp>        // for libclang_parser, libclang_compile_config, cpp_entity,...
#include <cppast/visitor.hpp>                // for visit()
#include <cppast/code_generator.hpp>         // for generate_code()
// override parameter
//#include <type_safe/flag_set.hpp>            // ref
//#include <type_safe/index.hpp>
#include <cppast/cpp_entity.hpp>
#include <cppast/cpp_entity_ref.hpp>

#include <cppast/cpp_entity_kind.hpp>        // for the cpp_entity_kind definition
#include <cppast/cpp_forward_declarable.hpp> // for is_definition()
#include <cppast/cpp_namespace.hpp>          // for cpp_namespace
#include <cppast/cpp_function_template.hpp>  // for cpp_function_template (free fn templates)
#include <cppast/cpp_template_parameter.hpp> // for template parameter names

// Class 
#include "nodes.h"
#include "code_gen.hpp"

// Doxygen XML doc-comment interface. doxmlintf.h declares only abstract
// (pure-virtual) interfaces, so including it is header-only and costs nothing
// at link time. The actual (Qt-based) doxmlparser *library* is only required
// when USE_DOXYGEN is defined, which gates the single factory call
// (createObjectModel) and the runtime doc lookups below.
// doxmlintf.h uses the non-standard integer type `uint`, which is not provided
// by default on macOS; <sys/types.h> defines it (and is harmless elsewhere).
#include <sys/types.h>
#include "doxmlintf.h"

using namespace std;

/*! @brief  Pxd ファイル生成の大本クラス
    @remark cppast 側で対処可能な項目との切り分けを見ておくこと
            code_generator の定義はこちらに書くべき?
*/
class AutoPxd
{
private:
    // hファイル(root ファイル)
    // namespace(階層になるケースがあるため複数?)
    // class定義(階層になるケースがあるため複数?)
    // template付 class定義
    // template 定義
    // struct 定義
    // → 上記パラメータを同一で扱えるように基底クラスを用意する?

    // pxd ファイル書き出し用
    std::string autopxd_file;
    std::ofstream fout_pxd;
    std::string base_filename;
    // Just the header's basename (e.g. "simple.h"); used in the
    // `cdef extern from "<header>"` line. Cython resolves it via the include
    // search path, so an absolute path is both unnecessary and non-portable.
    std::string header_name;

    // 記述ルール取り込み?
    // std::vector<std::stack<PxdNode*>> declStack;
    std::vector<std::vector<PxdNode*>> declStack;

    // doxygen parser. The member is always declared (so the doc-lookup helper
    // methods that reference it still compile), but it is only constructed via
    // the doxmlparser factory when USE_DOXYGEN is enabled; otherwise it stays
    // null and those helpers are unreferenced (dropped by -dead_strip).
#ifdef USE_DOXYGEN
    IDoxygen* doxygen = createObjectModel();
#else
    IDoxygen* doxygen = nullptr;
#endif

    // std::vector<std::string> pxd_lines;
    // std::string namespace_str;
    // std::string class_str;
    std::stack<std::string> namespaceStack;
    std::stack<std::string> classNameStack;

    // Names of the namespaces currently open, in declaration order
    // (outermost first). Unlike namespaceStack (which is destructively consumed
    // when the `cdef extern from ... namespace` header is emitted), this is kept
    // for the lifetime of the block so emitted declarations can strip the
    // `Namespace::` qualifier — inside a Cython namespace block types must be
    // referred to unqualified (e.g. `Point`, not `demo::Point`).
    std::vector<std::string> currentNamespaceNames;

    // --extra_cimport lines (verbatim `from X cimport Y`), seeded into the
    // hoisted import list; --typemap FROM=TO word-boundary substitutions,
    // applied to the final body before the symbol-driven import passes so a
    // substitution target like uint32_t picks up its own import. Both mirror
    // the Python implementation's extra_cimports / typemap.substitutions.
    std::vector<std::string> extraCimports;
    std::vector<std::string> typemapSubstitutions;

    // Template type-parameter names of the function template currently being
    // entered. cppast represents a free function template as a
    // function_template_t proxy wrapping the real function_t; the proxy carries
    // the parameters. We capture them here so the inner function_t can emit the
    // Cython form `RetType name[T, ...](params)`.
    std::vector<std::string> pendingFunctionTemplateParams;

    // Names of the classes whose body we are currently emitting. Used to strip
    // the redundant `ClassName::` scope from members (e.g. a method returning
    // `Status::Code` inside `cdef cppclass Status` must say just `Code`).
    std::vector<std::string> currentClassNames;

    // Typedef names for `typedef enum/struct { ... } Name;` where the entity is
    // anonymous: cppast emits the body as an anonymous `cdef enum:` and a
    // separate self-typedef `Name = Name`. We record Name here (in emission
    // order) and, in post-processing, attach it to the matching anonymous block
    // so `Name` becomes a usable type.
    std::vector<std::string> pendingAnonTypedefNames;

    // class に定義している template の型情報のリスト
    std::vector<std::string> classTemplateNames;

    std::string class_access_str;
    std::string const_str;
    bool isClass;
    bool isClassAccessPublic;
    bool isEnumClassInFlag;
    bool isAnonymous;
    int indentCount;
    bool isFileEnd;

    // class 内の Template について格納
    // (Template 付関数呼び出し時の引数をチェックするために使用する。)
    // class に複数の Template が設定されている可能性があるため、以下の形にしている。
    std::vector<std::string> classTemplates;
    
    // ヘッダ解析時の処理として
    std::string workingFolder;

public:
    // AutoPxd(const std::string& filename, const std::string& output_folder = ".")
    AutoPxd(const std::string& filename, const std::string& output_folder = ".", const std::string& xml_folder = "",
            const std::vector<std::string>& extra_cimports = {},
            const std::vector<std::string>& typemap_substitutions = {})
        : extraCimports(extra_cimports), typemapSubstitutions(typemap_substitutions)
    {
        // そのまま設定すると、絶対パスになるため
        // 相対パスとして設定すること。
        base_filename = filename;

        // 拡張子取り除き
        // win
        // int path_i = base_filename.find_last_of("\\") + 1;
        int path_i = base_filename.find_last_of("/") + 1;
        int ext_i = base_filename.find_last_of(".");
        std::string filename_without_ext = base_filename.substr(path_i, ext_i - path_i);
        std::string extname = base_filename.substr(ext_i, base_filename.size() - ext_i);
        // header basename for the `cdef extern from` line
        header_name = base_filename.substr(path_i);

        // autopxd_file = base_filename + ".pxd";
        // autopxd_file = filename_without_ext + ".pxd";
        autopxd_file = output_folder + "/" + filename_without_ext + ".pxd";
        // class_str = "";
        std::cout << autopxd_file << "\n";

#ifdef USE_DOXYGEN
        if(!xml_folder.empty())
        {
            // xml ファイルの解析処理を実行する
            if (doxygen->readXMLDir(xml_folder.c_str()))
            {
                // Debug
                printDoxygen(doxygen);

                // 同一ファイル名(絶対パスも?)である場合、ドキュメントの対象関数、変数を即検索できるように index を用意する?
                // キー名として関数名を設定する?(override しているケースはどうする?)
            }
            else
            {
                cout << "Could not read files." << endl << flush;
            }
        }
#else
        (void)xml_folder;
#endif

        class_access_str = "";
        isClass = false;
        isClassAccessPublic = false;
        isEnumClassInFlag = false;
        indentCount = 0;
        isFileEnd = false;

        // open target write pxd file
        fout_pxd.open(autopxd_file, std::ios::out);
    }

    // 
    virtual ~AutoPxd()
    {
#ifdef USE_DOXYGEN
        if (doxygen != nullptr)
        {
            doxygen->release();
            doxygen = nullptr;
        }
#endif

        // close target write pxd file
        fout_pxd.close();
    }

    // prints the AST of a file
    void autopxd_ast(const cppast::cpp_file& file)
    {
        // print file name
        // fout_pxd << "AST for '" << file.name() << "':\n";
        std::vector<std::string> refLines = {};
        std::vector<PxdNode*> refNodes = {};
        PxdNode* tmpPxdNode = nullptr;
        bool node_continue = true;
        bool container_start = true;
        bool isIndentCountUp = false;

        // Emit the `cdef extern from "file" namespace "ns::...":` header once,
        // before the first top-level entity inside a namespace. This must run
        // whether that entity is the last child or not (a namespace containing a
        // single class takes the last_child path), so it is shared by both
        // container_entity_enter branches below.
        auto emitNamespaceHeader = [&]() {
            // Build from currentNamespaceNames (outermost first, kept in sync
            // by the namespace enter/exit events below). The old code drained
            // namespaceStack, which reversed nested namespaces into
            // "traits::pcl" AND emptied the stack, so siblings after a nested
            // namespace lost their qualification entirely.
            if(!currentNamespaceNames.empty() && container_start)
            {
                std::string headerRef = "\n";
                headerRef += "cdef extern from \"" + header_name + "\" namespace \"";
                for(size_t i = 0; i < currentNamespaceNames.size(); ++i)
                {
                    if(i) headerRef += "::";
                    headerRef += currentNamespaceNames[i];
                }
                headerRef += "\":\n";
                refLines.push_back(headerRef);
                container_start = false;
            }
        };

        // recursively visit file and all children
        cppast::visit(file, [&](const cppast::cpp_entity& e, cppast::visitor_info info) {
            std::cout << "\n";
            std::cout << "is_new_entity : ";
            std::cout << info.is_new_entity();
            std::cout << "\n";

            // if(indentCount

            if (e.kind() == cppast::cpp_entity_kind::file_t)
            {
                // ファイル先頭/終端で通知される?
                std::cout << "file_t";
                std::cout << "\n";

                if(isFileEnd)
                {
                    // ファイル終端処理
                    // enum 定義
                    // NodeType の判断を行う。
                    // container_entity_enter のタイミングで実行?
                    PxdNode* enumNode = new EnumPxdNode("", refLines);
                    refNodes.push_back(enumNode);
                    refLines = {};
                    node_continue = true;
                }
                else
                {
                    // ファイル先頭処理
                    // Note: クラス/Enum の先頭解析時に追加する。-> 存在しないケースの対応 -> 他のケース対処でNG
                    // ここに置くこともNG : namespace_t の対応があるため。
                    std::string headerRef = "\n";
                    headerRef += "cdef extern from \"" + header_name + "\":" + "\n";
                    refLines.push_back(headerRef);
                    indentCount++;
                    isFileEnd = true;
                }

                // no need to do anything for a file,
                // templated and friended entities are just proxies, so skip those as well
                // return true to continue visit for children
                return true;
            }
            else if (e.kind() == cppast::cpp_entity_kind::class_t && cppast::is_templated(e))
            {
                // A templated class/struct appears twice in the AST: the
                // class_template_t proxy (which carries the template
                // parameters) and this inner class_t definition
                // (is_templated()==true) that holds the members. Emit the class
                // line only via the proxy; skip this duplicate entirely — no
                // line and no indent change — but keep visiting its children so
                // the members are emitted one level under the proxy.
                std::cout << "skip templated inner class_t\n";
                return true;
            }
            else if (e.kind() == cppast::cpp_entity_kind::function_template_t)
            {
                // A free function template is a transparent proxy whose child
                // is the real function_t (is_templated()==true), which the
                // normal path emits. Unlike a class template, there is no outer
                // line to emit here, so do NOT add/remove an indent level for
                // the proxy (it would push the inner function one level too
                // deep). Capture the template parameter names so the inner
                // function_t can emit the Cython form `Ret name[T, ...](...)`.
                std::cout << "transparent function_template_t proxy\n";
                if(info.event == cppast::visitor_info::container_entity_enter)
                {
                    pendingFunctionTemplateParams.clear();
                    auto& tmpl = static_cast<const cppast::cpp_function_template&>(e);
                    for(auto& p : tmpl.parameters())
                    {
                        if(!p.name().empty())
                            pendingFunctionTemplateParams.push_back(p.name());
                    }
                }
                return true;
            }
            else if (e.kind() == cppast::cpp_entity_kind::language_linkage_t)
            {
                // `extern "C" { ... }` is a transparent container. Its members
                // belong to the enclosing `cdef extern from` block, so do NOT
                // change the indent level for it (otherwise its children get an
                // extra, header-less indent). Both enter and exit are ignored;
                // children are still visited.
                std::cout << "transparent language_linkage_t\n";
                return true;
            }
            else if (e.kind() == cppast::cpp_entity_kind::namespace_t &&
                     info.event == cppast::visitor_info::container_entity_enter)
            {
                // ENTER only: the visitor also fires this callback on the
                // container's EXIT event, and pushing there doubled every
                // namespace ("pcl::traits::traits") once the exit-pop below
                // stopped the old drain from absorbing the duplicates.
                std::cout << "namespace_t";
                std::cout << "\n";

                // cast to cpp_namespace
                auto& ns = static_cast<const cppast::cpp_namespace&>(e);
                // print whether or not it is inline
                if (ns.is_inline())
                {
                    // inline 関数?
                    // fout_pxd << " [inline]";
                }

                namespaceStack.push(e.name());
                // 非破壊の記録（宣言から修飾子を除去するため）。
                currentNamespaceNames.push_back(e.name());
                // Entities inside this namespace need their own extern-from
                // header (nested namespace, or a namespace re-opened after
                // one closed).
                container_start = true;
                // fout_pxd << '\n';
            }
            else if (info.event == cppast::visitor_info::container_entity_exit)
            {
                std::cout << "container_entity_exit";
                std::cout << "\n";

                // Leaving a namespace: retract it from both records so
                // following siblings are qualified by the OUTER scope only,
                // and re-arm the header emission — the next entity opens a
                // fresh `cdef extern from` block for that outer scope.
                if(e.kind() == cppast::cpp_entity_kind::namespace_t)
                {
                    if(!currentNamespaceNames.empty() &&
                       currentNamespaceNames.back() == e.name())
                        currentNamespaceNames.pop_back();
                    if(!namespaceStack.empty() && namespaceStack.top() == e.name())
                        namespaceStack.pop();
                    container_start = true;
                }
                else
                {
                    // namespace 内に複数のクラス/構造体が定義されている場合を考慮
                    // クラス/構造体を１つずつ管理する？
                    // A namespace exit must NOT decrement: namespaces never
                    // incremented indent (the extern-from block header is the
                    // indent provider). Before the enter-only guard above,
                    // namespace exits re-entered the namespace_t branch and
                    // never reached this decrement — keep that behavior.
                    indentCount--;
                }
                std::cout << "indentCount: ";
                std::cout << indentCount;
                std::cout << "\n";

                // カウントダウン?
                node_continue = false;
            }
            else
            {
                // 階層情報の検索
                if (info.last_child)
                {
                    // 1階層目?
                    if (info.event == cppast::visitor_info::container_entity_enter)
                    {
                        // 階層変化あり(class 内の class/struct/union 定義で発生?)
                        std::cout << "(last_child)container_entity_enter";
                        std::cout << "\n";

                        // indentCount++;
                        isIndentCountUp = true;
                        std::cout << "indentCount: ";
                        std::cout << indentCount;
                        std::cout << "\n";

                        // カウントアップ?
                        node_continue = true;
                    }
                    else if(info.event == cppast::visitor_info::leaf_entity)
                    {
                        // 階層変化なし(enum 等の終端?)
                        // fout_pxd << "leaf_entity";
                        std::cout << "(last_child)leaf_entity";
                        std::cout << "\n";
                        node_continue = false;
                    }

                    // 開始端?(階層+1)
                    // out << "+-";
                }
                else
                {
                    if (info.event == cppast::visitor_info::container_entity_enter)
                    {
                        // 階層変化あり(class 定義とかがメイン?)
                        std::cout << "main? container_entity_enter";
                        std::cout << "\n";

                        // indentCount++;
                        isIndentCountUp = true;
                        std::cout << "indentCount: ";
                        std::cout << indentCount;
                        std::cout << "\n";

                        // カウントアップ?
                        node_continue = true;
                    }
                    else if(info.event == cppast::visitor_info::leaf_entity)
                    {
                        // 階層変化なし(enum/class 内検索途中経過? 1行～数行単位の処理、関数/変数/マクロ定義が対象?)
                        // クラス内関数/変数も同様?
                        std::cout << "main? leaf_entity";
                        std::cout << "\n";
                        // node_continue = true;
                    }
                    else
                    {
                        std::cout << "container other?";
                        std::cout << "\n";
                    }

                    // 階層継続?
                    // out << "|-";
                }

                // Emit the namespace header before the FIRST namespaced entity,
                // whether it is a container (class/enum) or a leaf (a free
                // function/variable). Doing it here (idempotent: guarded by
                // container_start) covers all four enter/leaf x last/non-last
                // branches above — otherwise a namespace whose first child is a
                // free function would place that function in the file-level
                // (non-namespaced) extern block and link against ::fn.
                emitNamespaceHeader();

                // print_entity(out, e);
                // autopxd_entity(out, e);
                // AutoPxd に専用の関数を用意する。(そっちの方が対処が楽なため)
                autopxd_entity2(e, refLines, tmpPxdNode);
            }

            if(node_continue == false)
            {
                // enum/class 定義の終端に到達したのでいったん書き出す。
                // TODO: NodeType の判断を行うタイミングは?
                // container_entity_enter のタイミングで実行?
                PxdNode* enumNode = new EnumPxdNode("", refLines);
                refNodes.push_back(enumNode);
                refLines = {};
                node_continue = true;
            }

            if(isIndentCountUp)
            {
                indentCount++;
                isIndentCountUp = false;
            }

            return true;
        });
        declStack.push_back(refNodes);

        std::cout << "write pxd";
        std::cout << "\n";

        // Collect everything into one buffer first so we can post-process it.
        std::string body;
        for(std::vector<PxdNode*>& stacksIt : declStack)
        {
            for (PxdNode* stackIt : stacksIt)
            {
                for(auto lines: stackIt->lines2())
                {
                    body += lines;
                }
            }
        }

        // Cython requires `from ... cimport ...` / `cimport ...` at module
        // top-level, BEFORE any `cdef extern from` block. The per-entity emitter
        // interleaves them with the extern header, so hoist them: split the
        // buffer into lines, pull out the (de-duplicated, left-trimmed) import
        // lines, and emit them first followed by the remaining body.
        std::vector<std::string> importLines;
        std::vector<std::string> importedSymbols;
        // --extra_cimport lines go in FIRST: the caller's statement of what a
        // sibling-header name means (`from PCLHeader cimport PCLHeader`) wins
        // the by-symbol dedup against anything the emitter derived.
        for(const auto& imp : extraCimports)
        {
            std::string symbol = imp.substr(imp.find_last_of(' ') + 1);
            if(std::find(importedSymbols.begin(), importedSymbols.end(), symbol)
                   == importedSymbols.end())
            {
                importedSymbols.push_back(symbol);
                importLines.push_back(imp);
            }
        }
        std::string rest;
        {
            std::string line;
            std::istringstream iss(body);
            while(std::getline(iss, line))
            {
                // left-trim for the import test (a stray leading space can occur)
                std::string trimmed = line;
                while(!trimmed.empty() && (trimmed.front() == ' ' || trimmed.front() == '\t'))
                    trimmed.erase(trimmed.begin());

                bool isImport = (trimmed.rfind("from ", 0) == 0 &&
                                 trimmed.find(" cimport ") != std::string::npos)
                                || trimmed.rfind("cimport ", 0) == 0;
                if(isImport)
                {
                    std::string symbol = trimmed.substr(trimmed.find_last_of(' ') + 1);

                    // Drop bogus "import the module name itself" lines such as
                    // `from libc.string cimport string` / `from libc.time cimport
                    // time`: for C headers we don't have a curated symbol list
                    // for, the emitter falls back to importing the module
                    // basename, which is not an importable symbol. Detect symbol
                    // == leaf of a `libc.` module. NOTE: only `libc.` — for the
                    // C++ STL `from libcpp.string cimport string` is a *valid*
                    // import (string is a real symbol there), so it must stay.
                    bool bogus = false;
                    if(trimmed.rfind("from libc.", 0) == 0)
                    {
                        std::string mod = trimmed.substr(5);
                        mod = mod.substr(0, mod.find(' '));            // libc.string
                        std::string modLeaf = mod.substr(mod.find_last_of('.') + 1);
                        if(modLeaf == symbol) bogus = true;
                    }
                    else if(trimmed.rfind("from libcpp.", 0) == 0)
                    {
                        // Most libcpp modules DO export a self-named symbol
                        // (string, vector, map, pair...), so leaf == symbol is
                        // bogus only for the modules verified with the real
                        // cython compiler to export none — `<algorithm>` in
                        // pcl/PolygonMesh.h produced `from libcpp.algorithm
                        // cimport algorithm`, an unresolvable import.
                        static const char* noSelfSymbol[] = {
                            "algorithm", "cast", "functional", "limits",
                            "memory", "typeindex", "typeinfo", "utility"};
                        std::string mod = trimmed.substr(5);
                        mod = mod.substr(0, mod.find(' '));
                        std::string modLeaf = mod.substr(mod.find_last_of('.') + 1);
                        if(modLeaf == symbol)
                            for(const char* m : noSelfSymbol)
                                if(modLeaf == m) { bogus = true; break; }
                    }

                    // De-duplicate by the imported symbol (the last token): the
                    // same name (e.g. size_t) can be offered by two modules and
                    // importing it twice is a redefinition error in Cython.
                    if(!bogus &&
                       std::find(importedSymbols.begin(), importedSymbols.end(), symbol) == importedSymbols.end())
                    {
                        importedSymbols.push_back(symbol);
                        importLines.push_back(trimmed);
                    }
                }
                else
                {
                    rest += line;
                    rest += "\n";
                }
            }
        }

        // Drop empty `cdef extern from ...:` blocks. A header is empty when the
        // next non-blank line is not indented (i.e. another top-level statement
        // or another extern header). This happens for the file-level block when
        // every declaration actually lives in a `namespace` block.
        {
            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);

            std::string filtered;
            for(size_t i = 0; i < lines.size(); ++i)
            {
                bool isExternHeader =
                    lines[i].rfind("cdef extern from", 0) == 0 &&
                    !lines[i].empty() && lines[i].back() == ':';
                if(isExternHeader)
                {
                    // find next non-blank line
                    size_t j = i + 1;
                    while(j < lines.size() && lines[j].find_first_not_of(" \t") == std::string::npos)
                        j++;
                    bool hasBody = (j < lines.size()) &&
                                   (lines[j][0] == ' ' || lines[j][0] == '\t');
                    if(!hasBody)
                    {
                        // skip this header (and the blank lines after it)
                        i = j - 1;
                        continue;
                    }
                }
                filtered += lines[i];
                filtered += "\n";
            }
            rest = filtered;
        }

        // Attach recorded typedef names to anonymous enum/struct blocks:
        // `typedef enum { ... } Name;` emits an anonymous `cdef enum:` plus a
        // (suppressed) self-typedef whose name we queued in
        // pendingAnonTypedefNames. Rewrite `cdef enum:` -> `cdef enum Name:`
        // (and the struct form) in order, so `Name` is a usable type.
        if(!pendingAnonTypedefNames.empty())
        {
            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);

            // Names that already appear as a named block (`cdef enum/struct/
            // cppclass NAME:`) come from a *named* self-typedef
            // (`typedef struct vec3 {} vec3`) and must NOT be reused to label an
            // anonymous block — skip them so the queue stays aligned.
            auto isDefinedBlock = [&](const std::string& nm) -> bool {
                for(const auto& l : lines)
                {
                    std::string s = l; size_t q = 0;
                    while(q < s.size() && s[q] == ' ') q++;
                    s = s.substr(q);
                    if(s == "cdef enum " + nm + ":" || s == "enum " + nm + ":" ||
                       s == "cdef struct " + nm + ":" || s == "struct " + nm + ":" ||
                       s == "cdef cppclass " + nm + ":")
                        return true;
                }
                return false;
            };
            std::vector<std::string> anonNames;
            for(const auto& nm : pendingAnonTypedefNames)
                if(!isDefinedBlock(nm)) anonNames.push_back(nm);

            size_t nameIdx = 0;
            std::string filtered;
            for(size_t i = 0; i < lines.size(); ++i)
            {
                std::string t = lines[i];
                std::string lead;
                size_t p = 0; while(p < t.size() && t[p] == ' ') { lead += ' '; p++; }
                std::string rest_t = t.substr(p);
                if(nameIdx < anonNames.size() &&
                   (rest_t == "cdef enum:" || rest_t == "cdef struct:" ||
                    rest_t == "enum:" || rest_t == "struct:"))
                {
                    std::string kind = rest_t.substr(0, rest_t.size() - 1); // drop ':'
                    lines[i] = lead + kind + " " + anonNames[nameIdx] + ":";
                    nameIdx++;
                }
                filtered += lines[i];
                filtered += "\n";
            }
            rest = filtered;
        }

        // Drop redundant self-typedefs `ctypedef X X`. They arise from the C
        // idiom `typedef struct {...} X;` / `typedef enum {...} X;` after the
        // anonymous block has been named X above; `X` is already defined, so
        // re-typedef'ing it to itself is a redeclaration (Cython warns/errors).
        {
            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);
            std::string filtered;
            for(const auto& l : lines)
            {
                std::string s = l; size_t q = 0;
                while(q < s.size() && s[q] == ' ') q++;
                s = s.substr(q);
                // match "ctypedef <tok> <tok>" with both tokens identical
                bool drop = false;
                if(s.rfind("ctypedef ", 0) == 0)
                {
                    std::string a = s.substr(9);
                    // collapse internal spaces to compare the two words
                    std::istringstream ws(a);
                    std::string w1, w2, w3;
                    ws >> w1 >> w2;
                    if(!(ws >> w3) && !w1.empty() && w1 == w2)
                        drop = true;  // exactly two identical words
                }
                if(!drop)
                {
                    filtered += l;
                    filtered += "\n";
                }
            }
            rest = filtered;
        }

        // Flatten anonymous unions/structs into their enclosing record.
        // PCL's point types are unions of anonymous structs (SSE padding);
        // Cython cannot declare an unnamed nested record, but for extern
        // declarations only the member names/types matter — the real layout
        // always comes from the C++ header. So `cdef union :` / `cdef
        // struct :` headers are removed and their bodies dedented one level,
        // repeatedly, until no anonymous nested record remains.
        {
            auto indentOf = [](const std::string& s) -> int {
                int n = 0; while(n < (int)s.size() && s[n] == ' ') n++; return n;
            };
            bool changed = true;
            while(changed)
            {
                changed = false;
                std::vector<std::string> lines;
                std::string line;
                std::istringstream iss(rest);
                while(std::getline(iss, line)) lines.push_back(line);

                std::string filtered;
                for(size_t i = 0; i < lines.size(); ++i)
                {
                    std::string t = lines[i];
                    size_t p = 0; while(p < t.size() && t[p] == ' ') p++;
                    std::string body_t = t.substr(p);
                    // trailing-space tolerant match of an anonymous header
                    while(!body_t.empty() && body_t.back() == ' ') body_t.pop_back();
                    bool anonHeader =
                        body_t == "cdef union :" || body_t == "cdef union:" ||
                        body_t == "cdef struct :" || body_t == "cdef struct:" ||
                        body_t == "union :" || body_t == "union:" ||
                        body_t == "struct :" || body_t == "struct:";
                    // an anonymous header INSIDE a record (indent > 4): drop
                    // it and dedent its body one level. (Top-level anonymous
                    // typedef blocks are named by the pass above.)
                    if(anonHeader && (int)p >= 4)
                    {
                        int hdrIndent = (int)p;
                        size_t j = i + 1;
                        // find the body indent (first non-blank line)
                        while(j < lines.size() && lines[j].find_first_not_of(" \t") == std::string::npos)
                            j++;
                        int bodyIndent = (j < lines.size()) ? indentOf(lines[j]) : hdrIndent;
                        int shift = bodyIndent - hdrIndent;
                        if(shift <= 0) shift = 4;
                        for(j = i + 1; j < lines.size(); ++j)
                        {
                            if(lines[j].find_first_not_of(" \t") == std::string::npos)
                                continue;   // keep blank lines
                            if(indentOf(lines[j]) <= hdrIndent)
                                break;      // end of the anonymous body
                            lines[j] = lines[j].substr(shift);
                        }
                        changed = true;
                        continue;           // drop the header line itself
                    }
                    filtered += lines[i];
                    filtered += "\n";
                }
                rest = filtered;
            }
        }

        // Convert remaining template angle brackets to Cython's square
        // brackets EVERYWHERE (nested arguments and field declarations were
        // missed by the earlier per-site conversions): `vector<PointT>` ->
        // `vector[PointT]`, `shared_ptr[PointCloud<PointT>]` ->
        // `shared_ptr[PointCloud[PointT]]`. A '<' counts as a template
        // opener when directly preceded by an identifier character and not
        // part of an `operator<`/`operator<<` name; the matching '>' is
        // found by depth counting.
        {
            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);

            std::string filtered;
            for(auto& l : lines)
            {
                std::string t = l;
                size_t p0 = t.find_first_not_of(" \t");
                if(p0 == std::string::npos || t[p0] == '#')
                {
                    filtered += l + "\n";
                    continue;
                }
                std::vector<size_t> stack;
                for(size_t i = 0; i < t.size(); ++i)
                {
                    if(t[i] == '<')
                    {
                        bool identBefore = i > 0 &&
                            (std::isalnum((unsigned char)t[i-1]) || t[i-1] == '_');
                        bool isOperator = i >= 8 &&
                            t.compare(i - 8, 8, "operator") == 0;
                        if(identBefore && !isOperator)
                            stack.push_back(i);
                    }
                    else if(t[i] == '>' && !stack.empty())
                    {
                        t[stack.back()] = '[';
                        t[i] = ']';
                        stack.pop_back();
                    }
                }
                filtered += t + "\n";
            }
            rest = filtered;
        }

        // Skip declarations Cython cannot express, keeping the rest of the
        // file valid (the previous behavior emitted them verbatim and the
        // whole .pxd failed to compile — draco's status.h operator<<):
        //   - std iostream types: Cython ships no libcpp.ostream/istream, so
        //     any signature touching them is un-declarable (curate via manual
        //     edit or a substitution when really needed)
        //   - rvalue references (T&&): move ctors/assignment are not callable
        //     from Cython and only produce parser warnings/noise
        // Each dropped line is kept as a comment for auditability.
        {
            auto hasIdentFrom = [](const std::string& s,
                                   const char* const* deny, size_t n) -> bool {
                size_t i = 0;
                while(i < s.size())
                {
                    if(std::isalpha((unsigned char)s[i]) || s[i] == '_')
                    {
                        size_t b = i;
                        while(i < s.size() &&
                              (std::isalnum((unsigned char)s[i]) || s[i] == '_'))
                            i++;
                        std::string tok = s.substr(b, i - b);
                        for(size_t d = 0; d < n; ++d)
                            if(tok == deny[d]) return true;
                    }
                    else i++;
                }
                return false;
            };
            static const char* denyIostream[] = {
                "ostream", "istream", "iostream", "wostream", "wistream",
                "basic_ostream", "basic_istream", "streambuf",
                "ofstream", "ifstream", "fstream", "stringstream",
                "ostringstream", "istringstream"};
            // std types Cython ships no libcpp module for (pcl/point_types.h
            // carries a std::bitset member).
            static const char* denyNoModule[] = { "bitset" };
            auto hasDeniedIdent = [&](const std::string& s) -> bool {
                return hasIdentFrom(s, denyIostream,
                                    sizeof(denyIostream) / sizeof(*denyIostream));
            };
            // Operator overloads Cython cannot express: the compound
            // assignments and `->` (pcl/PolygonMesh.h concatenates with
            // `operator+=`; plain `operator+` stays supported).
            auto hasDeniedOperator = [](const std::string& s) -> bool {
                static const char* denyOps[] = {
                    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
                    "<<=", ">>=", "->"};
                size_t pos = s.find("operator");
                while(pos != std::string::npos)
                {
                    size_t k = pos + 8;
                    while(k < s.size() && s[k] == ' ') k++;
                    // longest match first so `<<=` is not read as `<<`
                    for(const char* op : denyOps)
                    {
                        size_t len = std::char_traits<char>::length(op);
                        if(s.compare(k, len, op) == 0)
                        {
                            // `->` must not match a lone `-`; compound ops end
                            // in `=`, so require the NEXT char not extend the
                            // token into a supported operator (`-` vs `->`).
                            if(op[len - 1] == '=' || s.compare(k, 2, "->") == 0)
                                return true;
                        }
                    }
                    pos = s.find("operator", pos + 8);
                }
                return false;
            };

            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);

            std::string filtered;
            for(const auto& l : lines)
            {
                std::string t = l;
                size_t p = 0; while(p < t.size() && t[p] == ' ') p++;
                std::string lead = t.substr(0, p);
                std::string body_t = t.substr(p);
                bool isBlockHeader = !body_t.empty() && body_t.back() == ':';
                const char* why = nullptr;
                if(!isBlockHeader && !body_t.empty())
                {
                    if(body_t.rfind("#", 0) != 0 && hasDeniedIdent(body_t))
                        why = "std iostreams have no Cython libcpp module";
                    else if(body_t.rfind("#", 0) != 0 &&
                            hasIdentFrom(body_t, denyNoModule,
                                         sizeof(denyNoModule) / sizeof(*denyNoModule)))
                        why = "no Cython libcpp module for this std type";
                    else if(body_t.rfind("#", 0) != 0 && hasDeniedOperator(body_t))
                        why = "operator overload not supported in Cython";
                    else if(body_t.find("&&") != std::string::npos)
                        why = "rvalue references not supported in Cython";
                }
                if(why)
                {
                    filtered += lead + "# skipped: " + body_t + "  (" + why + ")\n";
                    continue;
                }
                filtered += l;
                filtered += "\n";
            }
            rest = filtered;
        }

        // Insert `pass` into otherwise-empty blocks. An opaque/forward-declared
        // struct (`struct mz_internal_state;`) yields a `cdef struct X:` header
        // with no members; Cython requires a body. If a line ends with ':' and
        // the next non-blank line is not more deeply indented, append an
        // indented `pass`. (extern-from headers were already dropped above, so
        // this targets struct/cppclass/enum bodies.)
        {
            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);

            auto indentOf = [](const std::string& s) -> int {
                int n = 0; while(n < (int)s.size() && s[n] == ' ') n++; return n;
            };

            std::string filtered;
            for(size_t i = 0; i < lines.size(); ++i)
            {
                filtered += lines[i];
                filtered += "\n";

                std::string t = lines[i];
                while(!t.empty() && (t.back() == ' ' || t.back() == '\t')) t.pop_back();
                if(!t.empty() && t.back() == ':')
                {
                    int hdrIndent = indentOf(lines[i]);
                    size_t j = i + 1;
                    while(j < lines.size() && lines[j].find_first_not_of(" \t") == std::string::npos)
                        j++;
                    bool hasBody = (j < lines.size()) && indentOf(lines[j]) > hdrIndent;
                    if(!hasBody)
                    {
                        filtered += std::string(hdrIndent + 4, ' ') + "pass\n";
                    }
                }
            }
            rest = filtered;
        }

        // Promote a `cdef struct` whose body contains member typedefs to
        // `cdef cppclass`: Cython rejects `ctypedef` inside a struct body but
        // accepts it inside a cppclass, and a struct carrying member typedefs
        // is necessarily C++ (the construct does not exist in C), so the
        // promotion is safe. This is what pcl/PCLHeader.h looks like
        // (`typedef std::shared_ptr<PCLHeader> Ptr;` inside a struct) and it
        // mirrors what the Python implementation emits for that header.
        {
            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);

            auto indentOf = [](const std::string& s) -> int {
                int n = 0; while(n < (int)s.size() && s[n] == ' ') n++; return n;
            };

            static const std::string structKw = "cdef struct ";
            for(size_t i = 0; i < lines.size(); ++i)
            {
                int p = indentOf(lines[i]);
                std::string body_t = lines[i].substr(p);
                while(!body_t.empty() && (body_t.back() == ' ' || body_t.back() == '\t'))
                    body_t.pop_back();
                if(body_t.rfind(structKw, 0) != 0 || body_t.empty() || body_t.back() != ':')
                    continue;

                // A TEMPLATE struct header (`cdef struct Box[T]:` — the #33
                // angle->square pass has already run) is C++-only too, and
                // Cython rejects template parameters on `cdef struct`; promote
                // it regardless of what the body holds.
                bool isTemplateHeader =
                    body_t.find('[') != std::string::npos;

                bool hasMemberTypedef = false;
                bool hasMethod = false;
                for(size_t j = i + 1; j < lines.size(); ++j)
                {
                    if(lines[j].find_first_not_of(" \t") == std::string::npos)
                        continue;                       // blank line: still in body
                    if(indentOf(lines[j]) <= p)
                        break;                          // dedent: body ended
                    std::string t = lines[j].substr(indentOf(lines[j]));
                    if(t.rfind("ctypedef ", 0) == 0) { hasMemberTypedef = true; break; }
                    // A METHOD makes the struct C++-only too, and Cython
                    // rejects a `const`-qualified method inside `cdef struct`
                    // (`Ops operator+(...) nogil const`, silently broken
                    // before). A function-pointer FIELD also carries parens —
                    // `int (*cb)(int)` — so require the paren NOT be `(*`.
                    // Comments, nested block headers and enum members don't
                    // carry parens at all.
                    while(!t.empty() && (t.back() == ' ' || t.back() == '\t'))
                        t.pop_back();
                    if(t.rfind("#", 0) != 0 && (t.empty() || t.back() != ':'))
                    {
                        size_t paren = t.find('(');
                        if(paren != std::string::npos &&
                           t.compare(paren, 2, "(*") != 0)
                            hasMethod = true;
                    }
                }
                if(hasMemberTypedef || isTemplateHeader || hasMethod)
                {
                    lines[i] = std::string(p, ' ') + "cdef cppclass " +
                               body_t.substr(structKw.size());
                    // Nested declarations inside a cppclass drop the `cdef`
                    // keyword (a nested `cdef enum X:` is a syntax error —
                    // pcl/PCLPointField.h's PointFieldTypes). Strip it from
                    // any deeper block header in the promoted body.
                    for(size_t j = i + 1; j < lines.size(); ++j)
                    {
                        if(lines[j].find_first_not_of(" \t") == std::string::npos)
                            continue;
                        int ind = indentOf(lines[j]);
                        if(ind <= p) break;
                        std::string bt = lines[j].substr(ind);
                        std::string btTrim = bt;
                        while(!btTrim.empty() &&
                              (btTrim.back() == ' ' || btTrim.back() == '\t'))
                            btTrim.pop_back();
                        if(!btTrim.empty() && btTrim.back() == ':' &&
                           bt.rfind("cdef ", 0) == 0)
                            lines[j] = std::string(ind, ' ') + bt.substr(5);
                    }
                }
            }

            rest.clear();
            for(const auto& l : lines) { rest += l; rest += "\n"; }
        }

        // Drop default member initializers on record fields: PCL's structs use
        // C++11 in-class initializers (`std::uint32_t seq = 0`) and the field
        // emitter carries them through as `uint32_t seq=0`, which Cython
        // rejects inside a `cdef struct` / `cdef cppclass`. Truncate at the
        // first top-level `=`. Only lines inside a record body are touched —
        // enum members (`RED = 0`) keep their values, and method declarations
        // (any line containing a parenthesis) are left alone.
        {
            std::vector<std::string> lines;
            std::string line;
            std::istringstream iss(rest);
            while(std::getline(iss, line)) lines.push_back(line);

            auto indentOf = [](const std::string& s) -> int {
                int n = 0; while(n < (int)s.size() && s[n] == ' ') n++; return n;
            };

            // innermost open blocks: (indent, isRecord)
            std::vector<std::pair<int, bool>> blockStack;
            for(auto& l : lines)
            {
                if(l.find_first_not_of(" \t") == std::string::npos)
                    continue;                           // blank line keeps context
                int ind = indentOf(l);
                while(!blockStack.empty() && blockStack.back().first >= ind)
                    blockStack.pop_back();

                std::string t = l.substr(ind);
                while(!t.empty() && (t.back() == ' ' || t.back() == '\t')) t.pop_back();

                if(!t.empty() && t.back() == ':' && t.rfind("cdef extern from", 0) != 0)
                {
                    bool isRecord = t.rfind("cdef struct ", 0) == 0 ||
                                    t.rfind("cdef cppclass ", 0) == 0 ||
                                    t.rfind("ctypedef struct ", 0) == 0 ||
                                    t.rfind("cdef union ", 0) == 0;
                    // enums (`cdef enum X:` / class-nested `enum X:`) push a
                    // non-record block so their members keep `= value`.
                    blockStack.push_back({ind, isRecord});
                    continue;
                }

                bool inRecord = !blockStack.empty() && blockStack.back().second;
                if(!inRecord || t.rfind("#", 0) == 0 || t.rfind("ctypedef ", 0) == 0)
                    continue;

                // truncate at the first `=` outside [] (template args carry none
                // today, but stay safe) and re-trim the field text. A `(`
                // BEFORE that `=` means the line is a signature (method or
                // function pointer) whose `=` is a default argument — leave it
                // alone; a `(` AFTER it is just part of the initializer
                // expression (`int z = int(3)`), which still truncates.
                int depth = 0;
                for(size_t k = 0; k < t.size(); ++k)
                {
                    if(t[k] == '[') depth++;
                    else if(t[k] == ']') depth--;
                    else if(t[k] == '(') break;
                    else if(t[k] == '=' && depth == 0)
                    {
                        // Only a LONE `=` is an initializer. The `=` inside an
                        // operator NAME reaches this scan before any `(`
                        // (`bool operator>=(...)`), and truncating there once
                        // emitted a silently-broken `bool operator>`. Compound
                        // tokens (`==`, `<=`, `>=`, `!=`, second char of `==`)
                        // and a preceding `operator` word (copy assignment,
                        // `Cmp& operator=(...)`) mark a signature: leave the
                        // whole line alone.
                        if(k + 1 < t.size() && t[k + 1] == '=') break;
                        if(k > 0 && std::string("<>!+-*/%&|^=").find(t[k - 1]) != std::string::npos) break;
                        static const std::string opWord = "operator";
                        if(k >= opWord.size() &&
                           t.compare(k - opWord.size(), opWord.size(), opWord) == 0) break;
                        t = t.substr(0, k);
                        while(!t.empty() && (t.back() == ' ' || t.back() == '\t'))
                            t.pop_back();
                        l = std::string(ind, ' ') + t;
                        break;
                    }
                }
            }

            rest.clear();
            for(const auto& l : lines) { rest += l; rest += "\n"; }
        }

        // --typemap FROM=TO substitutions: word-boundary textual replacement
        // over the final body, the C++ counterpart of the Python typemap's
        // substitutions (pcl_headers.toml). Runs BEFORE the symbol-driven
        // import passes so a target like `uint32_t` gains its stdint import
        // automatically; a target needing a different module (e.g.
        // `vector[int]`) is paired with --extra_cimport by the caller.
        for(const auto& sub : typemapSubstitutions)
        {
            size_t eq = sub.find('=');
            if(eq == std::string::npos || eq == 0)
            {
                // never silent: a typo'd flag should be attributable.
                std::cerr << "warning: ignoring malformed --typemap '" << sub
                          << "' (expected FROM=TO)\n";
                continue;
            }
            // Trim around FROM/TO: a caller (or a config line) writing
            // `A = B` instead of `A=B` otherwise got a FROM with a trailing
            // space, which can never match a word-boundary token — the
            // substitution silently did nothing.
            auto trim = [](std::string v) {
                size_t b = v.find_first_not_of(" \t");
                if(b == std::string::npos) return std::string();
                size_t e = v.find_last_not_of(" \t");
                return v.substr(b, e - b + 1);
            };
            const std::string from = trim(sub.substr(0, eq));
            const std::string to = trim(sub.substr(eq + 1));
            if(from.empty())
            {
                std::cerr << "warning: ignoring --typemap '" << sub
                          << "' (empty FROM)\n";
                continue;
            }
            std::string outBuf;
            outBuf.reserve(rest.size());
            size_t pos = 0;
            while(pos < rest.size())
            {
                size_t hit = rest.find(from, pos);
                if(hit == std::string::npos) { outBuf += rest.substr(pos); break; }
                bool leftOk = hit == 0 ||
                    (!std::isalnum((unsigned char)rest[hit - 1]) && rest[hit - 1] != '_');
                size_t after = hit + from.size();
                bool rightOk = after >= rest.size() ||
                    (!std::isalnum((unsigned char)rest[after]) && rest[after] != '_');
                outBuf += rest.substr(pos, hit - pos);
                outBuf += (leftOk && rightOk) ? to : from;
                pos = after;
            }
            rest = outBuf;
        }

        // Symbol-driven stdint imports: the include-directive mapping misses
        // the C++ spellings (<cstdint>) and transitive includes, so scan the
        // final body for stdint type tokens and import each one actually
        // used. (De-duplicated against imports already collected.)
        {
            static const char* stdintSyms[] = {
                "int8_t", "int16_t", "int32_t", "int64_t",
                "uint8_t", "uint16_t", "uint32_t", "uint64_t",
                "int_least8_t", "int_least16_t", "int_least32_t", "int_least64_t",
                "uint_least8_t", "uint_least16_t", "uint_least32_t", "uint_least64_t",
                "int_fast8_t", "int_fast16_t", "int_fast32_t", "int_fast64_t",
                "uint_fast8_t", "uint_fast16_t", "uint_fast32_t", "uint_fast64_t",
                "intptr_t", "uintptr_t", "intmax_t", "uintmax_t"};
            for(const char* sym : stdintSyms)
            {
                const std::string symStr = sym;
                bool used = false;
                size_t pos = 0;
                while(!used && (pos = rest.find(symStr, pos)) != std::string::npos)
                {
                    bool leftOk = pos == 0 ||
                        (!std::isalnum((unsigned char)rest[pos - 1]) && rest[pos - 1] != '_');
                    size_t after = pos + symStr.size();
                    bool rightOk = after >= rest.size() ||
                        (!std::isalnum((unsigned char)rest[after]) && rest[after] != '_');
                    if(leftOk && rightOk) used = true;
                    pos += symStr.size();
                }
                if(used &&
                   std::find(importedSymbols.begin(), importedSymbols.end(), symStr)
                       == importedSymbols.end())
                {
                    importedSymbols.push_back(symStr);
                    importLines.push_back("from libc.stdint cimport " + symStr);
                }
            }
        }

        // C++ `bool` needs `from libcpp cimport bool` — without it Cython
        // silently resolves `bool` to the Python type, which breaks the C++
        // compile of any code calling the method. Detect a word-boundary
        // `bool` in the body and add the import once.
        {
            bool usesBool = false;
            size_t pos = 0;
            while(!usesBool && (pos = rest.find("bool", pos)) != std::string::npos)
            {
                bool leftOk = pos == 0 ||
                    (!std::isalnum((unsigned char)rest[pos - 1]) && rest[pos - 1] != '_');
                size_t after = pos + 4;
                bool rightOk = after >= rest.size() ||
                    (!std::isalnum((unsigned char)rest[after]) && rest[after] != '_');
                if(leftOk && rightOk) usesBool = true;
                pos += 4;
            }
            if(usesBool &&
               std::find(importedSymbols.begin(), importedSymbols.end(), "bool")
                   == importedSymbols.end())
            {
                importedSymbols.push_back("bool");
                importLines.push_back("from libcpp cimport bool");
            }
        }

        // Symbol-driven libcpp.memory imports (same shape as the stdint pass):
        // the include mapping imported all three smart-pointer names whenever
        // `<memory>` was seen — leaving unused `unique_ptr`/`weak_ptr` noise —
        // and none at all when `shared_ptr` only arrives transitively (e.g.
        // referenced by a member typedef in a header that never includes
        // `<memory>` directly). Re-derive from actual use in the final body:
        // add the missing, drop the unused.
        {
            static const char* memSyms[] = { "unique_ptr", "shared_ptr", "weak_ptr" };
            for(const char* sym : memSyms)
            {
                const std::string symStr = sym;
                bool used = false;
                size_t pos = 0;
                while(!used && (pos = rest.find(symStr, pos)) != std::string::npos)
                {
                    bool leftOk = pos == 0 ||
                        (!std::isalnum((unsigned char)rest[pos - 1]) && rest[pos - 1] != '_');
                    size_t after = pos + symStr.size();
                    bool rightOk = after >= rest.size() ||
                        (!std::isalnum((unsigned char)rest[after]) && rest[after] != '_');
                    if(leftOk && rightOk) used = true;
                    pos += symStr.size();
                }

                auto symIt = std::find(importedSymbols.begin(), importedSymbols.end(), symStr);
                if(used && symIt == importedSymbols.end())
                {
                    importedSymbols.push_back(symStr);
                    importLines.push_back("from libcpp.memory cimport " + symStr);
                }
                else if(!used && symIt != importedSymbols.end())
                {
                    importedSymbols.erase(symIt);
                    importLines.erase(
                        std::remove(importLines.begin(), importLines.end(),
                                    "from libcpp.memory cimport " + symStr),
                        importLines.end());
                }
            }
        }

        std::string out;
        for(const auto& imp : importLines)
        {
            out += imp;
            out += "\n";
        }
        if(!importLines.empty())
            out += "\n";
        out += rest;

        std::cout << out;
        fout_pxd << out;
    }

private:
    void autopxd_entity2(const cppast::cpp_entity& e, std::vector<std::string>& refLines, PxdNode* pxd_node)
    {
        bool isDefine;
        isDefine = cppast::is_definition(e);

        // print name and the kind of the entity
        if (!e.name().empty())
        {
            // 対象項目
            // fout_pxd << e.name();
        }
        else
        {
            // 変数がよくわからないとき(enum/struct の定義で "}" 後に定義するケース/using とかもここに入る)
            // fout_pxd << "<anonymous>";
            isAnonymous = true;
        }

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
        // fout_pxd << " (" << cppast::to_string(e.kind()) << ")" << "\n";
        // std::string pxd_line = "";
        /*
        switch(e.kind())
        {
            // cpp_entity_kind.hpp を参照
            case cppast::cpp_entity_kind::namespace_t:
                // cast to cpp_namespace
                auto& ns = static_cast<const cppast::cpp_namespace&>(e);
                // print whether or not it is inline
                if (ns.is_inline())
                {
                    // inline 関数?
                    // fout_pxd << " [inline]";
                }
                // fout_pxd << '\n';

                if(!namespace_str.empty())
                {
                    namespace_str += "::";
                }
                namespace_str += e.name();
                break;

            case cppast::cpp_entity_kind::macro_parameter_t:
            case cppast::cpp_entity_kind::macro_definition_t:
            case cppast::cpp_entity_kind::include_directive_t:
                break;

            case cppast::cpp_entity_kind::language_linkage_t:
                // fout_pxd << '\n';
                break;

            case cppast::cpp_entity_kind::namespace_alias_t:
            case cppast::cpp_entity_kind::using_directive_t:
            case cppast::cpp_entity_kind::using_declaration_t:
            case cppast::cpp_entity_kind::type_alias_t:
            case cppast::cpp_entity_kind::enum_t:
            case cppast::cpp_entity_kind::enum_value_t:
            case cppast::cpp_entity_kind::class_t:
            case cppast::cpp_entity_kind::access_specifier_t:
            case cppast::cpp_entity_kind::base_class_t:
            case cppast::cpp_entity_kind::variable_t:
            case cppast::cpp_entity_kind::member_variable_t:
            case cppast::cpp_entity_kind::bitfield_t:
            case cppast::cpp_entity_kind::function_parameter_t:
            case cppast::cpp_entity_kind::function_t:
            case cppast::cpp_entity_kind::member_function_t:
            case cppast::cpp_entity_kind::conversion_op_t:
            case cppast::cpp_entity_kind::constructor_t:
            case cppast::cpp_entity_kind::destructor_t:
            case cppast::cpp_entity_kind::friend_t:
            case cppast::cpp_entity_kind::template_type_parameter_t:
            case cppast::cpp_entity_kind::non_type_template_parameter_t:
            case cppast::cpp_entity_kind::template_template_parameter_t:
            case cppast::cpp_entity_kind::alias_template_t:
            case cppast::cpp_entity_kind::variable_template_t:
            case cppast::cpp_entity_kind::function_template_t:
            case cppast::cpp_entity_kind::function_template_specialization_t:
            case cppast::cpp_entity_kind::class_template_t:
            case cppast::cpp_entity_kind::class_template_specialization_t:
            case cppast::cpp_entity_kind::static_assert_t:
            case cppast::cpp_entity_kind::unexposed_t:
                break;

            // case cppast::cpp_entity_kind::count:
        }
        */

        // print whether or not it is a definition
        // if (cppast::is_definition(e))
        if (isDefine)
        {
            std::cout << "is_definition";
            std::cout << "\n";

            // define ?
            // 内部は?
            // fout_pxd << " [definition]";
            // pxd の記述として書き出す
            // e.kind() == "variant" + is_definition() == true
        }

        if (e.kind() == cppast::cpp_entity_kind::language_linkage_t)
        {
            std::cout << "language_linkage_t";
            std::cout << "\n";
            // pragma?

            // no need to print additional information for language linkages
        }
        else
        {
            pxd_generator generator(e);

            // fout_pxd << ": `" << generator.str() << '`' << '\n';
            // fout_pxd << '`' << generator.str() << '`' << '\n';
            // std::unique_ptr<pxd_generator> tmp_generator = new pxd_generator(e);

            // libclang で対処できない項目の対応
            auto parseGeneratorLists = ParseGenerator(generator.generatorLists());

            // stack か何かに突っ込んでおいて、このタイミングで解析する?
            // 行単位の解析
            // namespace_str, 
            // std::cout << "call autopxd_generator2 start.";
            // std::cout << "\n";
            // refLines.push_back(autopxd_generator2(e, generator.generatorLists(), indentCount, pxd_node));
            refLines.push_back(autopxd_generator2(e, parseGeneratorLists, indentCount, pxd_node));
            // TODO: Node 種類は内部で決める?
            // 行単位での解析のため、区切りが不明
            // declStack.push_back(autopxd_generator3(namespace_str, e, generator.generatorLists()));
            // autopxd_generator3(namespace_str, e, generator.generatorLists(), refNodes);
            // std::cout << "call autopxd_generator2 end.";
            // std::cout << "\n";

            // Node クラス側に分解処理を持たせる?
            // pxd_node.writeline(generator.generatorLists());
        }
    }

    // clang でのパラメータ分解で対処できなかった項目を対応する。
    // ex. Value で "}" などが入っているケース
    std::vector<IGenerator*> ParseGenerator(const std::vector<IGenerator*>& orgGeneratorLists)
    {
        // copy
        std::vector<IGenerator*> retGeneratorLists;
        std::vector<IGenerator*> tmpGeneratorLists(orgGeneratorLists.size()); // ちゃんと確保しておくこと
        std::copy(orgGeneratorLists.begin(), orgGeneratorLists.end(), tmpGeneratorLists.begin());
        // lineGeneratorStack Iterator
        for(auto itr = tmpGeneratorLists.begin(); itr != tmpGeneratorLists.end(); ++itr)
        {
            // Debug
            std::cout << (*itr)->GetType();
            std::cout << " \"";
            std::cout << (*itr)->GetString();
            std::cout << "\"\n";

            // libclangTool で分解しきれなかった項目の対応
            // "{", "}", ",", ""
            std::string parseStr = (*itr)->GetString();
            std::string delimiter = "}";
            size_t pos = 0;
            std::string token;
            // while ((pos = parseStr.find(delimiter)) != std::string::npos) 
            if ((pos = parseStr.find(delimiter)) != std::string::npos) 
            {
                while((pos = parseStr.find(delimiter)) != std::string::npos) 
                {
                    token = parseStr.substr(0, pos);
                    std::cout << "token: " << token << std::endl;
                    if(token != parseStr)
                    {
                        // 文字の不一致
                        IGenerator* parseGenerator = *itr;
                        parseGenerator->SetString(token.c_str());
                        retGeneratorLists.push_back(parseGenerator);

                        IGenerator* parseGenerator2 = new PunctuationGenerator();
                        parseGenerator2->SetString(delimiter.c_str());
                        retGeneratorLists.push_back(parseGenerator2);

                        // 
                        parseStr.erase(0, pos + delimiter.length());
                    }
                }
            }
            else
            {
                retGeneratorLists.push_back(*itr);
            }
            // std::cout << s << std::endl;
        }
        return retGeneratorLists;
    }

    // 特殊対応
    // header
    // standard c header list
    std::vector<std::string> c_header_lists { "<errno.h>", "<float.h>", "<limits.h>", "<locale.h>", "<math.h>", "<setjmp.h>", "<signal.h>", "<stddef.h>", "<stdint.h>", "<stdio.h>", "<stdlib.h>", "<string.h>", "<time.h>" };
    // standard c++ header list
    std::vector<std::string> cpp_header_lists { "<algorithm>", "<cast>", "<complex>", "<deque>", "<forward_list>", "<functional>", "<iterator>", "<limits>", "<list>", "<map>", "<memory>", "<pair>", "<queue>", "<set>", "<stack>", "<string>", "<typeindex>", "<typeinfo>", "<unordered_map>", "<unordered_set>", "<utility>", "<vector>" };
    // posix header list
    std::vector<std::string> posix_header_lists { "<dlfcn.h>", "<fcntl.h>", "<sys/ioctl.h>", "<sys/mman.h>", "<sys/resource.h>", "<sys/select.h>", "<signal.h>", "<sys/stat.h>", "<stdio.h>", "<stdlib.h>", "<strings.h>", "<sys/time.h>", "<sys/types.h>", "<unistd.h>", "<sys/wait.h>" };
    // reject header list
    // std::vector<std::string> reject_header_lists { "<windows.h>" };
    // cimport <cinttypes>
    // cimport <cstddef>
    // cimport <cstring>
    // cimport <ostream>

    // c header 読み出し+
    // c - stdint 読み込み時に展開する定義
    // cython が使用する標準で定義されている型情報リスト
    // uint32_t 等が使用されている時の対応はどうするか
    // from libc.stdint cimport int8_t
    // from libc.stdint cimport uint32_t
    // :
    // Symbols exported by Cython's `libc.stdint`. NOTE: size_t is NOT one of
    // them (it lives in libc.stddef), so it must not be listed here.
    std::vector<std::string> cstd_type_lists { "int8_t", "int16_t", "int32_t", "int64_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t" };

    // cpp header 読み出し+
    // memory 呼び出し時の
    // cpp ファイルの定義として使用する型定義を追加
    std::vector<std::string> cpp_type_lists { "bool", "nullptr_t", "nullptr" };
    std::vector<std::string> cpp_memory_import_lists { "unique_ptr", "shared_ptr", "weak_ptr" };

    // class 内の Enum 値を使用する場合は?(定義が後になるケース?[あるかどうかも調査]の対応)
    // operator function の対応についてどうするか。

    // 文字列置き換え
    void myReplace(std::string& str,
               const std::string& oldStr,
               const std::string& newStr)
    {
        std::string::size_type pos = 0u;
        while((pos = str.find(oldStr, pos)) != std::string::npos)
        {
            str.replace(pos, oldStr.length(), newStr);
            pos += newStr.length();
        }
    }

    // The per-token emitters glue keywords/punctuation together without regard
    // for spacing, producing artefacts like `voidconst*` or `area()const`.
    // normalizeDeclSpacing applies a few conservative, idempotent fixes so the
    // generated declaration reads as valid Cython. It only inserts spaces; it
    // never removes type information.
    // Normalize spacing while preserving the leading indentation (and any
    // leading decorator lines that end in a newline).
    std::string normalizeDeclIndented(const std::string& s)
    {
        std::string::size_type body = s.find_last_of('\n');
        std::string::size_type start = (body == std::string::npos) ? 0 : body + 1;
        std::string::size_type firstNonSpace = s.find_first_not_of(" \t", start);
        if(firstNonSpace == std::string::npos) return s;
        std::string decl = normalizeDeclSpacing(s.substr(firstNonSpace));
        // 名前空間ブロック内では型は非修飾で参照する。
        decl = stripNamespaceQualifiers(decl);
        return s.substr(0, firstNonSpace) + decl;
    }

    std::string normalizeDeclSpacing(std::string s)
    {
        // `<letter>const`  -> `<letter> const`   (e.g. voidconst, Pointconst)
        // `const<letter>`  -> `const <letter>`   (e.g. constvoid)
        for(std::string::size_type i = s.find("const"); i != std::string::npos; i = s.find("const", i + 1))
        {
            if(i > 0 && (std::isalnum((unsigned char)s[i-1]) || s[i-1] == '_'))
            {
                s.insert(i, " ");
                i++; // skip the inserted space
            }
            std::string::size_type after = i + 5; // length of "const"
            if(after < s.size() && (std::isalnum((unsigned char)s[after]) || s[after] == '_'))
            {
                s.insert(after, " ");
            }
        }
        // `)const` -> `) const`
        myReplace(s, ")const", ") const");
        // `,` between params -> `, ` for readability
        myReplace(s, ",", ", ");
        // collapse any accidental double spaces produced above
        myReplace(s, "  ", " ");
        // a removed leading keyword (explicit/virtual) can leave a leading space
        while(!s.empty() && (s.front() == ' ' || s.front() == '\t'))
            s.erase(s.begin());

        // East-const -> west-const. cppast/libclang prints `T const&` / `T const*`
        // but Cython only accepts `const T&` / `const T*`. Rewrite a parameter
        // type `<TYPE> const<&|*>` to `const <TYPE><&|*>`. (A trailing method
        // `... ) const` has no following &/* so is left untouched.)
        s = eastConstToWest(s);

        // Drop a top-level `const` on a by-value parameter: libclang prints
        // `T const name` for `const T name`; the const is meaningless on a value
        // parameter and Cython rejects the `T const name` form. Detected as
        // " const " immediately followed by an identifier char and NOT by &/*
        // (those were handled above). Turn `<word> const <word>` into
        // `<word> <word>`.
        s = dropValueParamConst(s);

        // Cython requires the modifier order `nogil const` for a const method,
        // not `const nogil`. Our emitters append ` nogil` after the (trailing)
        // method `const`, producing the invalid `... const nogil`; swap it.
        myReplace(s, " const nogil", " nogil const");

        // `= default` / `= delete` are not valid in a .pxd; drop them (in both
        // the spaced and glued forms the emitters can produce).
        myReplace(s, " = default", "");
        myReplace(s, " = delete", "");
        myReplace(s, "=default", "");
        myReplace(s, "=delete", "");

        // `std::` is not used in Cython; the matching type is cimported plain
        // (e.g. `from libcpp.string cimport string`). Strip the qualifier.
        myReplace(s, "std::", "");
        return s;
    }

    // Move a `const` that qualifies a pointer/reference parameter type to the
    // front: `Foo const&` -> `const Foo&`, `Foo[T] const*` -> `const Foo[T]*`.
    std::string eastConstToWest(std::string s)
    {
        const std::string needle = " const";
        std::string::size_type pos = 0;
        while((pos = s.find(needle, pos)) != std::string::npos)
        {
            std::string::size_type after = pos + needle.size();
            // only convert when const qualifies a pointer/reference here
            if(after >= s.size() || (s[after] != '&' && s[after] != '*'))
            {
                pos = after;
                continue;
            }
            // find the start of the type token preceding " const"
            // (letters, digits, _, ::, and bracket-balanced template args,
            // spaces). Template args can still be in their C++ `<...>`
            // spelling at this point — the #33 angle->square pass runs later
            // — so both bracket alphabets balance here.
            std::string::size_type start = pos;
            int bracket = 0;
            while(start > 0)
            {
                char c = s[start - 1];
                if(c == ']' || c == '>') { bracket++; start--; continue; }
                if(c == '[' || c == '<') { if(bracket==0) break; bracket--; start--; continue; }
                if(bracket > 0) { start--; continue; }
                if(std::isalnum((unsigned char)c) || c == '_' || c == ':' || c == ' ')
                {
                    start--; continue;
                }
                break;
            }
            // trim leading spaces of the captured type
            while(start < pos && s[start] == ' ') start++;
            std::string type = s.substr(start, pos - start);
            // rebuild: <prefix> + "const " + <type> + <suffix(&/*...)>
            s = s.substr(0, start) + "const " + type + s.substr(after);
            pos = start + std::string("const ").size() + type.size();
        }
        return s;
    }

    // Drop a meaningless top-level `const` on a by-value parameter:
    // `mz_uint32 const decomp_flags` -> `mz_uint32 decomp_flags`. Only removes
    // ` const ` when both neighbours are identifier characters (i.e. it sits
    // between a type and a parameter name), so pointer/reference consts (already
    // moved west) and trailing method `const` are untouched.
    std::string dropValueParamConst(std::string s)
    {
        const std::string needle = " const ";
        std::string::size_type pos = 0;
        while((pos = s.find(needle, pos)) != std::string::npos)
        {
            bool prevIdent = pos > 0 &&
                (std::isalnum((unsigned char)s[pos-1]) || s[pos-1] == '_');
            std::string::size_type after = pos + needle.size();
            bool nextIdent = after < s.size() &&
                (std::isalnum((unsigned char)s[after]) || s[after] == '_');
            // skip if 'const' is actually 'west' already (prev is '(' or ',' or
            // space) — handled by requiring prevIdent (a type token precedes).
            if(prevIdent && nextIdent)
            {
                s.erase(pos, std::string(" const").size()); // leave one space
            }
            else
            {
                pos = after;
            }
        }
        return s;
    }

    // Inside a `cdef extern from ... namespace "demo"` block, types must be
    // referred to unqualified. Strip the leading `demo::` (and any nested
    // namespace) qualifier from a declaration. Removes the longest open
    // namespace prefix first (e.g. `a::b::` before `a::`) so nested namespaces
    // collapse fully. Does not touch the class scope qualifiers we intentionally
    // keep elsewhere.
    std::string stripNamespaceQualifiers(std::string s)
    {
        if(!currentNamespaceNames.empty())
        {
            // build "a::b::" from outermost..innermost, then progressively shorter.
            std::string full;
            for(const auto& n : currentNamespaceNames) full += n + "::";
            // try full prefix, then drop the outermost segment and retry.
            std::vector<std::string> prefixes;
            prefixes.push_back(full);
            for(size_t i = 0; i < currentNamespaceNames.size(); ++i)
            {
                std::string p;
                for(size_t j = i; j < currentNamespaceNames.size(); ++j)
                    p += currentNamespaceNames[j] + "::";
                if(!p.empty()) prefixes.push_back(p);
            }
            for(const auto& p : prefixes)
            {
                // PCL spells self-references with a global qualifier
                // (`shared_ptr< ::pcl::PCLPointField>`); try the `::`-prefixed
                // form FIRST or plain removal would strand a dangling `::`.
                myReplace(s, "::" + p, "");
                myReplace(s, p, "");
            }
        }
        // Convert a class scope to Cython's dot spelling (`PCLHeader::Ptr` ->
        // `PCLHeader.Ptr`). currentClassNames is a classes-seen-so-far list,
        // not a scope stack, so plain deletion here broke references OUTSIDE
        // the class (`using HeaderPtr = PCLHeader::Ptr;` at namespace scope
        // became the undefined bare `Ptr`). The dot form is verified valid in
        // BOTH positions — at namespace scope and inside the class's own body
        // (`Status.Code get()` within `cdef cppclass Status`) — so no
        // context tracking is needed.
        for(const auto& c : currentClassNames)
        {
            myReplace(s, c + "::", c + ".");
        }
        return s;
    }

    // IGenerator 継承
    std::string autopxd_generator2(const cppast::cpp_entity& e, const std::vector<IGenerator*>& generatorLists, int indentCount, PxdNode* node)
    {
        std::string retStr = "";
        std::string indentSpace = "";
        const std::string indentBaseSpace = "    ";
        for(int i = 0; i < indentCount;i++)
        {
            indentSpace += indentBaseSpace;
        }

        if(e.kind() == cppast::cpp_entity_kind::include_directive_t)
        {
            std::cout << "include_directive_t";
            std::cout << "\n";

            // TODO : Cython が標準で対応できないヘッダファイルに関しては、再帰的にヘッダを解析していく仕組みを実装する?
            // 現時点での対応は面倒なため、対応しないことにする
            std::string importDef = "";
            std::string line_generator = "";

            // lineGeneratorStack Iterator
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                // line_generator += (*itr)->GetType();
                line_generator += (*itr)->GetString();
            }

            importDef = line_generator;
            bool isStandard = false;

            // standard header list
            // start
            // 標準 C/C++ ヘッダファイルかどうかチェックする。
            for(auto itr = c_header_lists.begin(); itr != c_header_lists.end(); ++itr)
            {
                // '標準C header check'
                if(std::string::npos != importDef.find(*itr))
                {
                    std::string repace_c_import_header = *itr;
                    myReplace(repace_c_import_header, "<", "");
                    myReplace(repace_c_import_header, ">", "");

                    // cimport の対応
                    std::string repace_c_import = "";
                    // TODO : 取り出したい内容が ファイル名と一致していないケースもあるので注意して実装する。
                    // libc.<module> cimport の対象シンボル一覧。ヘッダ名そのもの
                    // (例: stddef) は import 可能なシンボルではないため、提供する
                    // 型名へ展開する必要がある。
                    const std::vector<std::string>* import_symbols = nullptr;
                    std::vector<std::string> stddef_type_lists { "size_t", "ptrdiff_t", "wchar_t" };
                    std::vector<std::string> time_type_lists { "time_t" };
                    std::vector<std::string> stdio_type_lists { "FILE" };
                    if (repace_c_import_header == "stdint.h")
                    {
                        import_symbols = &cstd_type_lists;
                    }
                    else if (repace_c_import_header == "stddef.h")
                    {
                        import_symbols = &stddef_type_lists;
                    }
                    else if (repace_c_import_header == "time.h")
                    {
                        import_symbols = &time_type_lists;
                    }
                    else if (repace_c_import_header == "stdio.h")
                    {
                        import_symbols = &stdio_type_lists;
                    }

                    if (import_symbols != nullptr)
                    {
                        // module 名は basename から ".h" を除いたもの。
                        std::string module = repace_c_import_header;
                        myReplace(module, ".h", "");
                        for(auto itr2 = import_symbols->begin(); itr2 != import_symbols->end(); ++itr2)
                        {
                            repace_c_import += "from libc.";
                            repace_c_import += module;
                            repace_c_import += " ";
                            repace_c_import += "cimport ";
                            repace_c_import += *itr2;
                            repace_c_import += "\n";
                        }
                    }
                    else
                    {
                        repace_c_import = "from libc." + repace_c_import_header + " " + "cimport " + repace_c_import_header;
                    }

                    myReplace(importDef, *itr, repace_c_import);
                    isStandard = true;
                    break;
                }
            }

            for(auto itr = cpp_header_lists.begin(); itr != cpp_header_lists.end(); ++itr)
            {
                // '標準 C++ header check'
                if(std::string::npos != importDef.find(*itr))
                {
                    std::string repace_cpp_import_header = *itr;
                    myReplace(repace_cpp_import_header, "<", "");
                    myReplace(repace_cpp_import_header, ">", "");

                    // cimport の対応
                    std::string repace_cpp_import = "";
                    if(repace_cpp_import_header == "memory")
                    {
                        // memory なら unique_ptr とか?
                        for(auto itr2 = cpp_memory_import_lists.begin(); itr2 != cpp_memory_import_lists.end(); ++itr2)
                        {
                            repace_cpp_import += "from libcpp.";
                            repace_cpp_import += repace_cpp_import_header;
                            repace_cpp_import += " ";
                            repace_cpp_import += "cimport ";
                            repace_cpp_import += *itr2;
                            repace_cpp_import += "\n";
                        }
                    }
                    else
                    {
                        // TODO : 取り出したい内容が ファイル名と一致していないケースもあるので注意して実装する。
                        repace_cpp_import = "from libcpp." + repace_cpp_import_header + " " + "cimport " + repace_cpp_import_header;
                    }

                    myReplace(importDef, *itr, repace_cpp_import);
                    isStandard = true;
                    break;
                }
            }

            for(auto itr = posix_header_lists.begin(); itr != posix_header_lists.end(); ++itr)
            {
                // 'posix header check'
                if(std::string::npos != importDef.find(*itr))
                {
                    std::string repace_posix_import_header = *itr;
                    myReplace(repace_posix_import_header, "<", "");
                    myReplace(repace_posix_import_header, ">", "");

                    std::string repace_posix_import = "from posix." + repace_posix_import_header + " " + "cimport " + repace_posix_import_header;
                    myReplace(importDef, *itr, repace_posix_import);
                    isStandard = true;
                    break;
                }
            }
            // end

            // custom header list?

            if(isStandard)
            {
                // ".h" remove
                myReplace(importDef, ".h", "");
                myReplace(importDef, "#include", "");
                // "/" to "."
                std::replace(importDef.begin(), importDef.end(), '/', '.');
                // "\"" remove
                myReplace(importDef, "\"", "");
                importDef += "\n";
                retStr = importDef;
            }
            else
            {
                // 非標準ヘッダ (`#include <ostream>` や `#include "foo/bar.h"`)。
                // Cython は任意の C/C++ ヘッダを cimport できず、`cimport
                // <ostream>` のような出力は構文エラーになる。これらは宣言が
                // `cdef extern from` ブロックで直接賄われるため、import 行は
                // 出力しない(スキップ)。
                retStr = "";
            }
        }
        else if(e.kind() == cppast::cpp_entity_kind::type_alias_t)
        {
            // typedef
            std::cout << "type_alias_t";
            std::cout << "\n";

            std::string typeAliasDef   = "";
            std::string typeAliasName  = "";
            std::string typeAliasValue = "";
            std::string typeIdentifierName = "";
            std::string typeVariantName = "";
            std::string typeCallbackDefineName = "";
            // 非callback の右辺型を順序通りに連結する蓄積先。
            // テンプレート (`Foo<A, B>`) は Cython の `Foo[A, B]` へ変換する。
            std::string typeRhs = "";

            typeAliasDef += indentSpace;

            // callback 定義の場合の対応はどうする?
            //
            bool isDefineStart = false;
            bool isCallbackDefine = false;
            bool isPunctuation = false;
            bool rhsSawPointer = false;  // 右辺で '*' を見たか(ポインタconst判定用)
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";
                KeywordGenerator *sa = dynamic_cast<KeywordGenerator*>(*itr);
                if(sa != nullptr)
                {
                    std::string tmpKeyword = sa->GetString();
                    // 接頭字
                    if(tmpKeyword == "static")
                    {
                        typeAliasName += "@staticmethod";
                        typeAliasName += "\n";
                        typeAliasName += indentSpace;
                        continue;
                    }

                    if(isDefineStart == true)
                    {
                        // 変数の戻り値定義
                        if(isPunctuation == false)
                        {
                            /*
                            if(tmpKeyword == "int")
                            {
                                typeAliasName += "@cython.returns(cython.int)";
                                typeAliasName += "\n";
                            }
                            else if(tmpKeyword == "float")
                            {
                                typeAliasName += "@cython.returns(cython.float)";
                                typeAliasName += "\n";
                            }
                            else if(tmpKeyword == "double")
                            {
                                typeAliasName += "@cython.returns(cython.double)";
                                typeAliasName += "\n";
                            }
                            else if(tmpKeyword == "void")
                            {
                                typeAliasName += "@cython.returns(cython.double)";
                                typeAliasName += "\n";
                            }
                            else
                            {
                                // 定義しない。(不明なため)
                            }
                            */
                            // int

                            typeAliasName += tmpKeyword;
                            typeCallbackDefineName += tmpKeyword;
                            // 非callback の右辺型キーワード(void/const/unsigned…)を
                            // 順序通り typeRhs に積む。ただし `*` の後に来る const
                            // (ポインタ自体の const: `void *const`)は Cython に
                            // 表現がないため捨てる。
                            if(!isCallbackDefine)
                            {
                                if(tmpKeyword == "const" && rhsSawPointer)
                                {
                                    // pointer-const: drop
                                }
                                else
                                {
                                    if(!typeRhs.empty() && typeRhs.back() != '*' &&
                                       typeRhs.back() != '[' && typeRhs.back() != ' ')
                                        typeRhs += " ";
                                    typeRhs += tmpKeyword;
                                }
                            }
                        }
                        else
                        {
                            // TODO: ここに入る時点でコールバック関数の定義として扱えないか?
                            // 関数の呼び出し変数の型情報
                            if(tmpKeyword == "int")
                            {
                            }
                            else if(tmpKeyword == "float")
                            {
                            }
                            else if(tmpKeyword == "double")
                            {
                            }
                            typeAliasName += tmpKeyword;
                            typeCallbackDefineName += tmpKeyword;
                        }
                    }
                    continue;
                }

                PunctuationGenerator *sb = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string tmpPunctuation = sb->GetString();
                    if(tmpPunctuation == "(")
                    {
                        isPunctuation = true;
                        typeCallbackDefineName += tmpPunctuation;
                    }
                    // using 名称 =
                    else if(tmpPunctuation == ")")
                    {
                        isPunctuation = false;
                        if(!isCallbackDefine)
                        {
                            typeCallbackDefineName += typeIdentifierName;
                            isCallbackDefine = true;
                        }
                        typeCallbackDefineName += tmpPunctuation;
                    }
                    else if(tmpPunctuation == "=")
                    {
                        isDefineStart = true;
                    }
                    else if(tmpPunctuation == ";")
                    {
                    }
                    else if(tmpPunctuation == "*")
                    {
                        typeCallbackDefineName += tmpPunctuation;
                        // ポインタ型 typedef の `*` を右辺に取り込む
                        // (`typedef void* voidp` -> `ctypedef void* voidp`)。
                        if(isDefineStart && !isCallbackDefine)
                        {
                            typeRhs += "*";
                            rhsSawPointer = true;
                        }
                    }
                    else if(tmpPunctuation == "<")
                    {
                        // テンプレート開始: Foo<...> -> Foo[...]
                        typeRhs += "[";
                    }
                    else if(tmpPunctuation == ">")
                    {
                        // テンプレート終了
                        typeRhs += "]";
                    }
                    else
                    {
                        typeAliasName += tmpPunctuation;
                        typeCallbackDefineName += tmpPunctuation;
                    }
                    continue;
                }

                IdentifierGenerator *sc = dynamic_cast<IdentifierGenerator*>(*itr);
                if(sc != nullptr)
                {
                    typeIdentifierName = sc->GetString();
                    continue;
                }

                TokenGenerator *sd = dynamic_cast<TokenGenerator*>(*itr);
                if(sd != nullptr)
                {
                    std::string tmpToken = sd->GetString();
                    if(tmpToken == " ")
                    {
                        continue;
                    }
                    // 右辺(= の後)の型トークンは順序通りに連結する。複数トークン
                    // (`VectorD` と `ScalarT, dimension_t`)が上書きされないよう
                    // typeVariantName ではなく typeRhs に積む。直前が識別子文字
                    // なら空白を挟む(`unsigned long` 等)。`[`/`*` の直後は挟まない。
                    if(isDefineStart)
                    {
                        if(!typeRhs.empty())
                        {
                            char b = typeRhs.back();
                            if(b != '[' && b != '*' && b != ' ')
                                typeRhs += " ";
                        }
                        typeRhs += tmpToken;
                    }
                    typeVariantName = tmpToken;
                    typeCallbackDefineName += tmpToken;
                    continue;
                }

                typeAliasName += (*itr)->GetString();
                typeCallbackDefineName += (*itr)->GetString();
            }
            // ****

            typeAliasDef += "ctypedef ";
            // typeAliasDef += "my_union_u";
            // typeAliasDef += "hogehoge ";
            if(isCallbackDefine)
            {
                // callback の対応
                typeAliasDef += typeCallbackDefineName;
            }
            else
            {
                // C の `typedef struct vec3 {...} vec3;` は cppast 上 `using vec3
                // = vec3` として現れる。Cython では `cdef struct vec3` が既に名前
                // vec3 を定義済みなので、自己 typedef (右辺==別名) は再定義エラーに
                // なる。出力しない。
                std::string rhsForSelfCheck = !typeRhs.empty() ? typeRhs : typeVariantName;
                if(typeAliasValue.empty() && typeAliasName.empty() &&
                   rhsForSelfCheck == typeIdentifierName && !typeIdentifierName.empty())
                {
                    // Self-typedef. For `typedef struct X {...} X;` the name X is
                    // already defined by `cdef struct X`, so emitting nothing is
                    // correct. But for an ANONYMOUS `typedef enum {...} X;` /
                    // `typedef struct {...} X;`, the body block is unnamed and X
                    // would be undefined — record X to be attached to that block
                    // in post-processing.
                    pendingAnonTypedefNames.push_back(typeIdentifierName);
                    return "";
                }

                // 通常の対応: `ctypedef <右辺型> <別名>`
                // typeRhs は `=` の後を順序通り(ポインタ/テンプレート/複数
                // キーワード対応)に連結したもの。これがあれば唯一の権威として
                // 使う(typeAliasName にも同じキーワードが入るため二重出力を避け
                // る)。無い場合のみ従来の typeAliasName/typeVariantName へ
                // フォールバックする。
                if(!typeRhs.empty())
                {
                    typeAliasDef += typeRhs;
                    typeAliasDef += " ";
                }
                else
                {
                    if(!typeAliasValue.empty())
                    {
                        typeAliasDef += typeAliasValue;
                        typeAliasDef += " ";
                    }
                    if(!typeAliasName.empty())
                    {
                        typeAliasDef += typeAliasName;
                        typeAliasDef += " ";
                    }
                    if(!typeVariantName.empty())
                    {
                        typeAliasDef += typeVariantName;
                        typeAliasDef += " ";
                    }
                }
                typeAliasDef += typeIdentifierName;
            }
            // インデントを保護しつつ宣言本体の空白を整形する
            // (callback typedef の `voidconst*` 等を修正)。
            typeAliasDef = normalizeDeclIndented(typeAliasDef);
            typeAliasDef += "\n";
            retStr = typeAliasDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::macro_definition_t)
        {
            std::cout << "macro_definition_t";
            std::cout << "\n";

            // 不要?
            /*
            std::string macroDefineDef   = "";
            std::string macroDefineName  = "";
            std::string macroDefineValue = "";

            macroDefineDef += indentSpace;

            // lineGeneratorStack Iterator
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\n";

                IdentifierGenerator *sa = dynamic_cast<IdentifierGenerator*>(*itr);
                if(sa != nullptr)
                {
                    macroDefineName = sa->GetString();
                }
                //IdentifierGenerator *sa = dynamic_cast<IdentifierGenerator*>(*itr);
                //if(sa != nullptr)
                //{
            }

            macroDefineDef += "DEF ";
            macroDefineDef += macroDefineName;
            macroDefineDef += macroDefineValue;
            macroDefineDef += "\n";
            retStr = macroDefineDef;
            */
        }
        else if(e.kind() == cppast::cpp_entity_kind::class_t)
        {
            std::cout << "class_t";
            std::cout << "\n";

            std::string classDef = "";
            std::string classKeyworkName = "";
            std::string className = "";

            classDef += indentSpace;

            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                KeywordGenerator *sa = dynamic_cast<KeywordGenerator*>(*itr);
                if(sa != nullptr)
                {
                    classKeyworkName = sa->GetString();
                }

                IdentifierGenerator *sb = dynamic_cast<IdentifierGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string tmpClassName= sb->GetString();
                    if(!tmpClassName.empty())
                    {
                        className = tmpClassName;
                        // class_str = className;
                        classNameStack.push(className);
                        // メンバから ClassName:: を除去するために記録する。
                        if(std::find(currentClassNames.begin(), currentClassNames.end(), tmpClassName) == currentClassNames.end())
                            currentClassNames.push_back(tmpClassName);
                    }
                }

                PunctuationGenerator *sc = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sc != nullptr)
                {
                    std::string tmpPunctuation = sc->GetString();
                    if(tmpPunctuation == ";")
                    {
                        // 空定義として扱う
                        // className = tmpClassName;
                    }
                }
            }

            // second line
            // classDef += "cdef cppclass ";
            // classDef += "className";
            classDef += "cdef ";
            if(classKeyworkName == "class")
            {
                classDef += "cppclass";
                isClass = true;
            }
            else
            {
                classDef += classKeyworkName;
                isClass = false;
            }
            classDef += " ";
            classDef += className;
            classDef += ":";

            // ベースクラス継承する場合
            // (
            // Action
            // )

            classDef += "\n";

            // ファイル情報の付随
            // std::string headerRef = "\n";
            // headerRef += "cdef extern from \"" + base_filename + "\":" + "\n";
            // retStr += headerRef;

            retStr += classDef;
            isClassAccessPublic = false;
        }
        else if (e.kind() == cppast::cpp_entity_kind::class_template_t)
        {
            std::cout << "class_template_t";
            std::cout << "\n";
            
            classTemplateNames.clear();

            std::string classTemplateDef = "";
            std::string classTemplateKeyworkName = "";
            std::string classTemplateName = "";
            std::string classTemplateDefineName = "";

            classTemplateDef += indentSpace;

            bool isTemplate = false;
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                KeywordGenerator *sa = dynamic_cast<KeywordGenerator*>(*itr);
                if(sa != nullptr)
                {
                    classTemplateKeyworkName = sa->GetString();
                    // template
                    if(classTemplateKeyworkName == "template")
                    {
                        isTemplate = true;
                    }
                    // class
                }
                IdentifierGenerator *sb = dynamic_cast<IdentifierGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string tmpClassName= sb->GetString();
                    if(isTemplate)
                    {
                        // Template 部分の対応
                        // TODO:複数定義しているケースの対応は?
                        classTemplateDefineName += tmpClassName;
                        classTemplateNames.push_back(tmpClassName);
                    }
                    else
                    {
                        if(!tmpClassName.empty())
                        {
                            classTemplateName = tmpClassName;
                            // メンバから ClassName:: を除去するために記録する。
                            if(std::find(currentClassNames.begin(), currentClassNames.end(), tmpClassName) == currentClassNames.end())
                                currentClassNames.push_back(tmpClassName);
                        }
                    }
                }
                PunctuationGenerator *sc = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sc != nullptr)
                {
                    std::string tmpPunctuation = sc->GetString();
                    if(tmpPunctuation == ";")
                    {
                        // 空定義として扱う
                        // classTemplateName = tmpClassName;
                        continue;
                    }

                    if(isTemplate)
                    {
                        // template parameter list: <T, N> -> [T, N]
                        if(tmpPunctuation == "<")
                        {
                            // start
                            classTemplateDefineName += "[";
                            continue;
                        }
                        if(tmpPunctuation == ",")
                        {
                            // 複数テンプレート引数の区切り
                            classTemplateDefineName += ", ";
                            continue;
                        }
                        if(tmpPunctuation == ">")
                        {
                            // end
                            classTemplateDefineName += "]";
                            isTemplate = false;
                            continue;
                        }
                    }
                }
            }

            // first line
            // second line
            classTemplateDef += "cdef ";
            if(classTemplateKeyworkName == "class")
            {
                classTemplateDef += "cppclass";
                isClass = true;
            }
            else
            {
                classTemplateDef += classTemplateKeyworkName;
                isClass = false;
            }
            classTemplateDef += " ";
            classTemplateDef += classTemplateName;
            // template 引数: Name[T, N]
            classTemplateDef += classTemplateDefineName;
            // Cython のブロック開始
            classTemplateDef += ":";

            // ベースクラス継承する場合
            // (
            // Action
            // )
            classTemplateDef += "\n";
            
            // ファイル情報の付随
            // std::string headerRef = "\n";
            // headerRef += "cdef extern from \"" + base_filename + "\":" + "\n";
            // retStr += headerRef;

            retStr += classTemplateDef;
            isClassAccessPublic = false;
        }
        else if (e.kind() == cppast::cpp_entity_kind::access_specifier_t)
        {
            std::cout << "access_specifier_t";
            std::cout << "\n";

            std::string accessParam = "";
            // lineGeneratorStack Iterator
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                KeywordGenerator *sa = dynamic_cast<KeywordGenerator*>(*itr);
                if(sa != nullptr)
                {
                    accessParam = sa->GetString();
                    continue;
                }
            }

            // 権限が public 以外は、書き出さない。
            // case cppast::cpp_entity_kind::access_specifier_t:
            if(accessParam.compare("public") == 0)
            {
                std::cout << "isClassAccessPublic = true";
                isClassAccessPublic = true;
            }
            else
            {
                std::cout << "isClassAccessPublic = false";
                isClassAccessPublic = false;
            }
        }
        else if(e.kind() == cppast::cpp_entity_kind::constructor_t)
        {
            std::cout << "constructor_t";
            std::cout << "\n";

            // construct
            // Same gate as the member-function path: a STRUCT's members are
            // public by default and isClassAccessPublic only turns true on an
            // explicit access specifier, so the bare `!isClassAccessPublic`
            // silently dropped every struct constructor (and with it the
            // constructor-template skip/clear below, letting the captured
            // template params leak into the next member).
            if(!isClassAccessPublic && isClass)
            {
                // public 以外の項目は pxd に書き出さない。
                std::cout << "not public access constructor.";
                return "";
            }

            std::string constructorName = "";
            std::string constructorTemplateDef = "";
            constructorTemplateDef += indentSpace;

            bool isPunctuation = false;
            bool skipNextSpace = false;
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                // identifier と punctuation[;]を無視する
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                KeywordGenerator *sa = dynamic_cast<KeywordGenerator*>(*itr);
                if(sa != nullptr)
                {
                    std::string tmpKeyword = sa->GetString();
                    // 接頭字
                    if(tmpKeyword == "static")
                    {
                        constructorName += "@staticmethod";
                        constructorName += "\n";
                        constructorName += indentSpace;
                        continue;
                    }
                    // `explicit` は Cython の .pxd では無効なので除去する。
                    // 直後の空白トークンも併せて捨てる。
                    if(tmpKeyword == "explicit")
                    {
                        skipNextSpace = true;
                        continue;
                    }

                    // 変数の戻り値定義
                    if(isPunctuation == false)
                    {
                        constructorName += tmpKeyword;
                    }
                    else
                    {
                        // 関数の呼び出し変数の型情報
                        if(tmpKeyword == "int")
                        {
                        }
                        else if(tmpKeyword == "float")
                        {
                        }
                        else if(tmpKeyword == "double")
                        {
                        }
                        constructorName += tmpKeyword;
                    }
                    continue;
                }

                PunctuationGenerator *sb = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string tmpPunctuation = sb->GetString();
                    if(tmpPunctuation == "(")
                    {
                        isPunctuation = true;
                    }
                    else if(tmpPunctuation == ")")
                    {
                        isPunctuation = false;
                    }
                    else if(tmpPunctuation == ";")
                    {
                        continue;
                    }
                    // `<` / `>` flow through VERBATIM — same reasoning as the
                    // member-function path: the filtered rebuild dropped any
                    // template argument that was not one of the class's own
                    // template parameters (`Widget(std::shared_ptr<Res> r)`
                    // emitted `shared_ptr[]`); the whole-file #33 pass does
                    // the `<...>` -> `[...]` conversion.
                    constructorName += tmpPunctuation;
                    continue;
                }

                TokenGenerator *sd = dynamic_cast<TokenGenerator*>(*itr);
                if(sd != nullptr)
                {
                    std::string tmpToken = sd->GetString();
                    // 直前に除去した explicit に続く空白を捨てる。
                    if(skipNextSpace && tmpToken == " ")
                    {
                        skipNextSpace = false;
                        continue;
                    }
                    skipNextSpace = false;
                    constructorName += tmpToken;
                    continue;
                }
                
                constructorName += (*itr)->GetString();
            }

            // A constructor TEMPLATE is not declarable in Cython
            // (`Wrap[U](const U&)` is a syntax error — compiler-verified), so
            // skip it with a comment. This also consumes the proxy's captured
            // parameter names: leaving them pending made the NEXT plain
            // member emit a phantom template list (`int plain[U](int x)`),
            // and previously leaked into following free functions too.
            if(!pendingFunctionTemplateParams.empty())
            {
                pendingFunctionTemplateParams.clear();
                // normalize the DECL text only — running the spacing passes
                // over the whole comment rewrote the reason ("const ructor").
                constructorTemplateDef += "# skipped: " +
                    normalizeDeclSpacing(constructorName) +
                    "  (constructor template not declarable in Cython)\n";
                retStr = constructorTemplateDef;
                return retStr;
            }

            constructorTemplateDef += constructorName;
            // インデントを保護しつつ宣言本体の空白を整形する。
            constructorTemplateDef = normalizeDeclIndented(constructorTemplateDef);
            constructorTemplateDef += "\n";
            retStr = constructorTemplateDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::destructor_t)
        {
            std::cout << "destructor_t";
            std::cout << "\n";

            // 基本対処しない?
            return "";

            if(!isClassAccessPublic)
            {
                // public 以外の項目は pxd に書き出さない。
                std::cout << "not public access destructor.";
                return "";
            }

            std::string destructorTemplateDef = "";
            destructorTemplateDef += indentSpace;

            // lineGeneratorStack Iterator
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";
                destructorTemplateDef += (*itr)->GetString();
            }

            // public 以外での対応をどうするか?
            // 現状 : 書かない
            destructorTemplateDef += "\n";
            retStr = destructorTemplateDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::member_function_t)
        {
            std::cout << "member_function_t";
            std::cout << "\n";

            // union/struct のケースもある?ため、class であるかチェックする
            // TOOD: struct で function 呼び出しケースがあるか調査
            // if(!isClassAccessPublic)
            if(!isClassAccessPublic && isClass)
            {
                // public 以外の項目は pxd に書き出さない。
                std::cout << "not public access member_function.";
                return "";
            }

            // class 内の Function
            std::string classFunctionDef = "";
            std::string classFunctionName = "";
            std::string nsStr2 = "";

            if(false)
            {
                classFunctionDef += indentSpace;
                classFunctionDef += "@cython.wraparound(False)";
                classFunctionDef += "\n";
                classFunctionDef += indentSpace;
                classFunctionDef += "@cython.boundscheck(False)";
                classFunctionDef += "\n";
            }

            {
                // iterate a COPY: draining the real stack here broke the
                // namespace bookkeeping for every entity after the first.
                std::stack<std::string> nsCopy = namespaceStack;
                while(!nsCopy.empty())
                {
                    if(!nsStr2.empty()) nsStr2 += "::";
                    nsStr2 += nsCopy.top();
                    nsCopy.pop();
                }
            }
            classFunctionDef += indentSpace;

            // remove namespace?
            // myReplace(memberFuncDef, nsStr2, "");

            bool isPunctuation = false;
            bool skipNextSpace = false;
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";
                KeywordGenerator *sa = dynamic_cast<KeywordGenerator*>(*itr);
                if(sa != nullptr)
                {
                    std::string tmpKeyword = sa->GetString();
                    // 接頭字
                    if(tmpKeyword == "static")
                    {
                        classFunctionName += "@staticmethod";
                        classFunctionName += "\n";
                        classFunctionName += indentSpace;
                        skipNextSpace = true;  // drop the space token after `static`
                        continue;
                    }
                    // `virtual` / `explicit` は Cython の cppclass では無効なので除去する。
                    // 直後の空白トークンも併せて捨てる(先頭に空白が残らないように)。
                    if(tmpKeyword == "virtual" || tmpKeyword == "explicit")
                    {
                        skipNextSpace = true;
                        continue;
                    }

                    // 変数の戻り値定義
                    if(isPunctuation == false)
                    {
                        /*
                        if(tmpKeyword == "int")
                        {
                            classFunctionName += "@cython.returns(cython.int)";
                            classFunctionName += "\n";
                        }
                        else if(tmpKeyword == "float")
                        {
                            classFunctionName += "@cython.returns(cython.float)";
                            classFunctionName += "\n";
                        }
                        else if(tmpKeyword == "double")
                        {
                            classFunctionName += "@cython.returns(cython.double)";
                            classFunctionName += "\n";
                        }
                        else if(tmpKeyword == "void")
                        {
                            classFunctionName += "@cython.returns(cython.double)";
                            classFunctionName += "\n";
                        }
                        else
                        {
                            // 定義しない。(不明なため)
                        }
                        */
                        // int

                        classFunctionName += tmpKeyword;
                        // classFunctionName += "cdef";
                    }
                    else
                    {
                        // 関数の呼び出し変数の型情報
                        if(tmpKeyword == "int")
                        {
                        }
                        else if(tmpKeyword == "float")
                        {
                        }
                        else if(tmpKeyword == "double")
                        {
                        }
                        classFunctionName += tmpKeyword;
                    }
                    continue;
                }

                PunctuationGenerator *sb = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string tmpPunctuation = sb->GetString();
                    if(tmpPunctuation == "(")
                    {
                        // A member function TEMPLATE spells `Ret name[T, ...]
                        // (params)` in Cython, same as a free function
                        // template; the function_template_t proxy captured the
                        // parameter names, and this path never consumed them —
                        // PCLPointCloud2's `template<typename T> T& at(...)`
                        // emitted a bare, undefined `T`.
                        if(!isPunctuation && !pendingFunctionTemplateParams.empty())
                        {
                            classFunctionName += "[";
                            for(size_t pi = 0; pi < pendingFunctionTemplateParams.size(); ++pi)
                            {
                                if(pi) classFunctionName += ", ";
                                classFunctionName += pendingFunctionTemplateParams[pi];
                            }
                            classFunctionName += "]";
                        }
                        isPunctuation = true;
                    }
                    else if(tmpPunctuation == ")")
                    {
                        isPunctuation = false;
                    }
                    else if(tmpPunctuation == ";")
                    {
                        continue;
                    }
                    // `<` / `>` flow through VERBATIM. They used to open a
                    // filtered rebuild that kept only the class's own template
                    // parameter names, so a concrete argument vanished:
                    // `std::shared_ptr<Res> build()` emitted `shared_ptr[]`.
                    // The whole-file #33 pass already converts every
                    // identifier-adjacent `<...>` to `[...]` (nested args and
                    // `operator<` handled), so no rebuild is needed here.
                    classFunctionName += tmpPunctuation;
                    continue;
                }

                TokenGenerator *sd = dynamic_cast<TokenGenerator*>(*itr);
                if(sd != nullptr)
                {
                    std::string tmpToken = sd->GetString();
                    // 直前に除去した keyword(virtual/explicit)に続く空白を捨てる。
                    if(skipNextSpace && tmpToken == " ")
                    {
                        skipNextSpace = false;
                        continue;
                    }
                    skipNextSpace = false;
                    classFunctionName += tmpToken;
                    continue;
                }

                classFunctionName += (*itr)->GetString();
            }

            // 消費したテンプレート引数はクリアする（自由関数側と同じ規約）。
            pendingFunctionTemplateParams.clear();

            classFunctionName += " nogil";
            // インデントを保護しつつ宣言本体の空白を整形する。
            classFunctionDef += normalizeDeclIndented(classFunctionName);
            classFunctionDef += "\n";
            retStr = classFunctionDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::enum_t)
        {
            std::cout << "enum_t";
            std::cout << "\n";

            std::string enumTemplateDef = "";
            std::string generatorParam = "";
            std::string enumTypeName = "";

            enumTemplateDef += indentSpace;

            // lineGeneratorStack Iterator
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                IdentifierGenerator *sa = dynamic_cast<IdentifierGenerator*>(*itr);
                if(sa != nullptr)
                {
                    enumTypeName = sa->GetString();
                }
            }

            // `typedef enum { ... } Name;` — the enum entity is anonymous in the
            // token stream, but cppast still exposes the typedef name via
            // e.name(). Use it so the enum is a named, usable type in Cython
            // (otherwise references to `Name` are undefined). The matching
            // self-typedef (`Name = Name`) is dropped by the type_alias handler.
            if(enumTypeName.empty() && !e.name().empty())
            {
                enumTypeName = e.name();
            }

            // first line
            // second line

            if(isClass)
            {
                // class 内 enum 定義。Cython では cppclass 内のネスト enum は
                // `enum Name:` と書く(`cdef` は付けない — 付けると構文エラー)。
                // メンバは素の名前で列挙する。
                enumTemplateDef += "enum";
                if(!enumTypeName.empty())
                {
                    enumTemplateDef += " ";
                    enumTemplateDef += enumTypeName;
                }
                enumTemplateDef += ":";
                // enum の値出力を「素の名前」モードにする。
                isEnumClassInFlag = false;
            }
            else
            {
                // class 外定義
                enumTemplateDef += "cdef enum";
                if(enumTypeName.empty())
                {
                    // None
                }
                else
                {
                    enumTemplateDef += " ";
                    // enumTemplateDef += "EnumTypeName";
                    enumTemplateDef += enumTypeName;
                }
                enumTemplateDef += ":";
                // enum in flag off?
                // Enum の値を設定する際の判断となるフラグを off にする?
                isEnumClassInFlag = false;
            }

            enumTemplateDef += "\n";

            // 先にファイル情報の付随
            // std::string headerRef = "\n";
            // headerRef += "cdef extern from \"" + base_filename + "\":" + "\n";
            // retStr += headerRef;

            retStr += enumTemplateDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::enum_value_t)
        {
            std::cout << "enum_value_t";
            std::cout << "\n";

            std::string enumValueDef = "";
            std::string enumValueName = "";
            std::string enumValue = "";
            std::string enumValueSign = "";
            enumValueDef += indentSpace;

            // lineGeneratorStack Iterator
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                IdentifierGenerator *sa = dynamic_cast<IdentifierGenerator*>(*itr);
                if(sa != nullptr)
                {
                    // FIRST identifier wins: it is the member name. A non-
                    // literal value expression can contain identifiers of its
                    // own (`BOOL = traits::asEnum_v<bool>` — the `bool` inside
                    // the template argument), and last-wins replaced the
                    // member name with them. Qualified pieces arrive as
                    // reference tokens, which is why only some members broke.
                    if(enumValueName.empty())
                        enumValueName = sa->GetString();
                    continue;
                }

                // 負値は `=` の後に `-` が独立した punctuation として現れる。
                // 符号を取り込んで値の前置にする。
                PunctuationGenerator *sp = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sp != nullptr)
                {
                    std::string punct = sp->GetString();
                    if(punct == "-" || punct == "+")
                    {
                        enumValueSign = punct;
                    }
                    continue;
                }

                IntliteralGenerator *sb = dynamic_cast<IntliteralGenerator*>(*itr);
                if(sb != nullptr)
                {
                    // libclang は時折末尾に余分な1文字を付けることがある。数値
                    // 以外の末尾文字のみを取り除く。
                    std::string tmpValue = sb->GetString();
                    while(!tmpValue.empty())
                    {
                        char back = tmpValue.back();
                        if(std::isdigit((unsigned char)back))
                            break;
                        // 16進等を考慮し x/X/a-f/A-F も許容
                        if(std::isxdigit((unsigned char)back) || back == 'x' || back == 'X')
                            break;
                        tmpValue.pop_back();
                    }

                    enumValue = enumValueSign + tmpValue;
                    continue;
                }
            }

            if(isEnumClassInFlag)
            {
                // class 内 enum 定義
                // Enum 定義 + "_" + Enum 値名称
                enumValueDef += "EnumDef";
                enumValueDef += "_";
                // enumValueDef += "EnumValueName";
                enumValueDef += enumValueName;
                enumValueDef += " ";

                // 
                enumValueDef += "\"";
                // enumValueDef += ns_str;
                // enumValueDef += "::";
                {
                    // COPY for the same reason as the member-function path.
                    std::stack<std::string> nsCopy = namespaceStack;
                    bool first = true;
                    while(!nsCopy.empty())
                    {
                        if(!first) enumValueDef += "::";
                        first = false;
                        enumValueDef += nsCopy.top();
                        nsCopy.pop();
                    }
                }
                // enumValueDef += "ClassName";
                if(!classNameStack.empty())
                {
                    enumValueDef += classNameStack.top();
                    classNameStack.pop();
                    while(!classNameStack.empty())
                    {
                        enumValueDef += "::";
                        enumValueDef += classNameStack.top();
                        classNameStack.pop();
                    }
                }
                enumValueDef += "::";
                // enumTemplateValueDef += "EnumValueName";
                if(enumValueName.empty())
                {
                    // None
                    // error?
                }
                else
                {
                    enumValueDef += enumValueName;
                }
            }
            else
            {
                // enum 単体定義
                // Cython enum member: `NAME` or `NAME = VALUE`.
                if(!enumValueName.empty())
                {
                    enumValueDef += enumValueName;
                }

                // generatorLists -> intliteral
                if(!enumValue.empty())
                {
                    // 値が明示されている場合は `= 値` の形にする。
                    enumValueDef += " = ";
                    enumValueDef += enumValue;
                }
            }

            enumValueDef += "\n";
            retStr = enumValueDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::variable_t)
        {
            std::cout << "variable_t";
            std::cout << "\n";

            std::string variableDef = "";
            std::string variableBody = "";  // without indent; cleaned then indented

            // A namespace/global variable inside a `cdef extern from` block is
            // declared as `Type name` (no leading `extern`, no trailing `;` —
            // both are implicit/invalid in Cython). Drop the `extern`/`static`
            // storage keywords and the `;` punctuation; emit everything else.
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                KeywordGenerator* kw = dynamic_cast<KeywordGenerator*>(*itr);
                if(kw != nullptr)
                {
                    std::string k = kw->GetString();
                    if(k == "extern" || k == "static")
                        continue;  // storage class: drop
                    variableBody += k;
                    continue;
                }
                PunctuationGenerator* pn = dynamic_cast<PunctuationGenerator*>(*itr);
                if(pn != nullptr)
                {
                    if(pn->GetString() == ";")
                        continue;  // no trailing semicolons in a .pxd
                    variableBody += pn->GetString();
                    continue;
                }
                variableBody += (*itr)->GetString();
            }

            // east-const / spacing / namespace-qualifier 整形を通す。
            // 先頭にぶら下がった空白トークンは normalizeDeclSpacing が落とす。
            variableDef = indentSpace + stripNamespaceQualifiers(normalizeDeclSpacing(variableBody));
            variableDef += "\n";
            retStr = variableDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::member_variable_t)
        {
            std::cout << "member_variable_t";
            std::cout << "\n";

            // union/struct のケースでも呼び出されるため class 定義であるかチェックする
            // if(!isClassAccessPublic)
            if(!isClassAccessPublic && isClass)
            {
                // public 以外の項目は pxd に書き出さない。
                std::cout << "not public access member_variable.";
                return "";
            }

            std::string memberVariableDef = "";
            std::string memberVariableName = "";
            memberVariableName += indentSpace;
            // memberVariableName += indentBaseSpace;

            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                // IdentifierGenerator *sa = dynamic_cast<IdentifierGenerator*>(*itr);
                // if(sa != nullptr)
                // {
                //     memberVariableName = sa->GetString();
                // }

                PunctuationGenerator *sb = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string tmpPunctuation = sb->GetString();
                    if(tmpPunctuation == ";")
                    {
                    }
                    else
                    {
                        memberVariableName += tmpPunctuation;
                    }
                    continue;
                }

                memberVariableName += (*itr)->GetString();
            }

            // 構造体/クラスメンバも east-const→west-const 等の整形を通す
            // (`unsigned char const* x` → `const unsigned char* x`)。
            memberVariableDef = normalizeDeclIndented(memberVariableName);
            memberVariableDef += "\n";
            retStr = memberVariableDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::bitfield_t)
        {
            std::cout << "bitfield_t";
            std::cout << "\n";

            if(!isClassAccessPublic && isClass)
            {
                std::cout << "not public access bitfield.";
                return "";
            }

            // Cython has no bit-field width syntax; emit the member as a plain
            // field and drop the `: <width>` part (everything from the ':' on).
            std::string bitfieldBody = "";
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                PunctuationGenerator *sb = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string p = sb->GetString();
                    if(p == ":")
                        break;       // width follows — stop here
                    if(p == ";")
                        continue;
                    bitfieldBody += p;
                    continue;
                }
                bitfieldBody += (*itr)->GetString();
            }

            std::string bitfieldDef = indentSpace +
                stripNamespaceQualifiers(normalizeDeclSpacing(bitfieldBody));
            bitfieldDef += "\n";
            retStr = bitfieldDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::function_t)
        {
            std::cout << "function_t";
            std::cout << "\n";

            std::string functionDef = "";
            std::string functionName = "";
            
            // 先頭に定義する。
            if(false)
            {
                functionName += indentSpace;
                functionName += "@cython.wraparound(False)";
                functionName += "\n";
                functionName += indentSpace;
                functionName += "@cython.boundscheck(False)";
                functionName += "\n";
            }

            functionName += indentSpace;
            // functionName += indentBaseSpace;
            bool isPunctuation = false;
            bool fnSkipNextSpace = false;

            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";

                // 直前に挿入した @staticmethod 改行+インデントの後に来る空白
                // トークンを捨てる(行頭に余分な空白が残らないように)。
                {
                    TokenGenerator* _sp = dynamic_cast<TokenGenerator*>(*itr);
                    if(fnSkipNextSpace && _sp != nullptr && _sp->GetString() == " ")
                    {
                        fnSkipNextSpace = false;
                        continue;
                    }
                    fnSkipNextSpace = false;
                }

                KeywordGenerator *sa = dynamic_cast<KeywordGenerator*>(*itr);
                if(sa != nullptr)
                {
                    std::string tmpKeyword = sa->GetString();
                    // 接頭字
                    if(tmpKeyword == "static")
                    {
                        // functionName += "@decorate";
                        functionName += "@staticmethod";
                        functionName += "\n";
                        functionName += indentSpace;
                        fnSkipNextSpace = true;  // drop the space token after `static`
                        continue;
                    }

                    // Inside a `cdef extern from` block a function is declared
                    // verbatim as `ReturnType name(params)` — there is no
                    // `cdef` prefix (that would be invalid Cython). Emit the
                    // keyword as-is, whether it is the return type (before '(')
                    // or a parameter type keyword (after '(').
                    functionName += tmpKeyword;
                    continue;
                }

                PunctuationGenerator *sb = dynamic_cast<PunctuationGenerator*>(*itr);
                if(sb != nullptr)
                {
                    std::string tmpPunctuation = sb->GetString();
                    if(tmpPunctuation == "(")
                    {
                        // 自由関数テンプレートは Cython では
                        // `Ret name[T, ...](params)` と書く。最初の '(' の直前で
                        // テンプレート引数リストを挿入する。
                        if(!isPunctuation && !pendingFunctionTemplateParams.empty())
                        {
                            functionName += "[";
                            for(size_t pi = 0; pi < pendingFunctionTemplateParams.size(); ++pi)
                            {
                                if(pi) functionName += ", ";
                                functionName += pendingFunctionTemplateParams[pi];
                            }
                            functionName += "]";
                        }
                        isPunctuation = true;
                    }
                    else if(tmpPunctuation == ")")
                    {
                        isPunctuation = false;
                    }
                    else if(tmpPunctuation == ";")
                    {
                        continue;
                    }
                    functionName += tmpPunctuation;
                    continue;
                }
                functionName += (*itr)->GetString();

                // IdentifierGenerator *sb = dynamic_cast<IdentifierGenerator*>(*itr);
                // if(sa != nullptr)
                // {
                //     functionName = sa->GetString();
                // }
            }
            // 消費したテンプレート引数はクリアする。
            pendingFunctionTemplateParams.clear();

            // 末尾に nogil をつける。
            functionName += " nogil";
            // インデントを保護しつつ宣言本体の空白を整形する。
            functionDef = normalizeDeclIndented(functionName);
            functionDef += "\n";
            retStr = functionDef;
        }
        else if(e.kind() == cppast::cpp_entity_kind::template_type_parameter_t)
        {
            std::cout << "template_type_parameter_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::non_type_template_parameter_t)
        {
            std::cout << "non_type_template_parameter_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::template_template_parameter_t)
        {
            std::cout << "template_template_parameter_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::alias_template_t)
        {
            std::cout << "alias_template_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::variable_template_t)
        {
            std::cout << "variable_template_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::function_template_t)
        {
            std::cout << "function_template_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::function_template_specialization_t)
        {
            std::cout << "function_template_specialization_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::static_assert_t)
        {
            std::cout << "static_assert_t";
            std::cout << "\n";
        }
        else if(e.kind() == cppast::cpp_entity_kind::unexposed_t)
        {
            std::cout << "unexposed_t";
            std::cout << "\n";
        }
        else
        {
            // cpp_entity_kind.hpp
            std::cout << "Unknown Param";
            std::cout << "\n";
            std::cout << (int)e.kind();
            std::cout << "\n";

            std::string otherDef = "";

            // class 外定義
            // generatorLists -> Identifier
            // lineGeneratorStack Iterator
            for(auto itr = generatorLists.begin(); itr != generatorLists.end(); ++itr)
            {
                std::cout << (*itr)->GetType();
                std::cout << " \"";
                std::cout << (*itr)->GetString();
                std::cout << "\"\n";
            }
            otherDef += "\n";

            retStr = otherDef;
        }

        return retStr;
    }

    // doxygen のコメント記述に関しての有無をチェックする.
    // TODO: コメント内容の取得はどうやって行うか?
    bool isDocumented(IDocRoot *brief, IDocRoot *detailed, IDocRoot *inbody = nullptr)
    {
        bool found = false;

        // brief
        if (brief)
        {
            IDocIterator *docIt = brief->contents();
            if (docIt == nullptr)
            {
                return false;
            }

            // IDocInternal *docIntern = brief->internal();
            // if (docIntern == nullptr)
            // {
            //  return false;
            // }
            // printf("docIntern->paragraphs enter.\n");
            // IDocIterator *docIterPara = docIntern->paragraphs();
            // printf("docIntern->paragraphs exit.\n");
            // if (docIterPara == nullptr)
            // {
            //  return false;
            // }

            // printf("docIntern->subSections enter.\n");
            // IDocIterator *docIterSubSections = docIntern->subSections();
            // printf("docIntern->subSections exit.\n");
            // if (docIterSubSections == nullptr)
            // {
            //  return false;
            // }
            IDoc* docCur = nullptr;
            // docCur = docIterPara->current();
            // docCur = docIterSubSections->current();
            // if(docCur == nullptr)
            // {
            //  printf("docCur is null.\n");
            //  return false;
            // }

            IDocPara* docPara = nullptr;
            IDocIterator *docIter2 = nullptr;
            IDocIterator *docIter3 = nullptr;
            IDoc* docParaCur = nullptr;

            for (docIt->toFirst(); (docCur = docIt->current()); docIt->toNext())
            // for (docIterPara->toFirst(); (docCur = docIterPara->current()); docIterPara->toNext())
            // for (docIterSubSections->toFirst(); (docCur = docIterSubSections->current()); docIterSubSections->toNext())
            {
                if (docCur) // method has brief description
                {
                    printf("doc(brief) : kind = %d.\n", docCur->kind());
                    switch (docCur->kind())
                    {
                        case IDoc::Para:
                            printf("docPara convert enter.\n");
                            docPara = static_cast<IDocPara*>(docCur);
                            if(docPara == nullptr) 
                            {
                                printf("docPara is null.\n");
                                continue;
                            }
                            printf("docPara->kind() = %d.\n", docPara->kind());
                    	    // printf("docPara->text() = %d.\n", docPara->text()->isEmpty());
                            // printf("docPara->text() = %s.\n", docPara->text().data());
                            printf("docPara convert exit.\n");

                            // // TODO: 変換NG(contents が存在しないため)
                            printf("docIter2 contents enter.\n");
                    	    // ParagraphHandle の情報?
                            docIter2 = docPara->contents();
                            if(docIter2 == nullptr) 
                            {
                                printf("docIter2 is null.\n");
                                continue;
                            }
                            printf("docIter2 contents exit.\n");
                            // 
                            // printf("docIter3 contents enter.\n");
                            // docParaCur = docIter2->current();
                    	    // // docIter3 = docParaCur->contents();
                            // // if(docIter3 == nullptr) 
                            // // {
                            // //     continue;
                            // //     printf("docIter3 is null.\n");
                            // // }
                            // // printf("docIter3 contents exit.\n");
                            // // 
                            // // for (docIter3->toFirst(); (docParaCur = docIter3->current()); docIter3->toNext())
                            // // {
                            // //     printf("enter.\n");
                            // //     if(docParaCur != nullptr)
                            // //     {
                            // //         printf("Doc(Para): kind = %d.\n", docParaCur->kind());
                            // //     }
                            // //     printf("exit.\n");
                            // // }
                            break;

                        case IDoc::Text:
                        case IDoc::MarkupModifier:     //  3 -> IDocMarkupModifier
                        case IDoc::ItemizedList:       //  4 -> IDocItemizedList
                        case IDoc::OrderedList:        //  5 -> IDocOrderedList
                        case IDoc::ListItem:           //  6 -> IDocListItem
                        case IDoc::ParameterList:      //  7 -> IDocParameterList
                        case IDoc::Parameter:          //  8 -> IDocParameter
                        case IDoc::SimpleSect:         //  9 -> IDocSimpleSect
                        case IDoc::Title:              // 10 -> IDocTitle
                        case IDoc::Ref:                // 11 -> IDocRef
                        case IDoc::VariableList:       // 12 -> IDocVariableList
                        case IDoc::VariableListEntry:  // 13 -> IDocVariableListEntry
                        case IDoc::HRuler:             // 14 -> IDocHRuler
                        case IDoc::LineBreak:          // 15 -> IDocLineBreak
                        case IDoc::ULink:              // 16 -> IDocULink
                        case IDoc::EMail:              // 17 -> IDocEMail
                        case IDoc::Link:               // 18 -> IDocLink
                        case IDoc::ProgramListing:     // 19 -> IDocProgramListing
                        case IDoc::CodeLine:           // 20 -> IDocCodeLine
                        case IDoc::Highlight:          // 21 -> IDocHighlight
                        case IDoc::Formula:            // 22 -> IDocFormula
                        case IDoc::Image:              // 23 -> IDocImage
                        case IDoc::DotFile:            // 24 -> IDocDotFile
                        case IDoc::IndexEntry:         // 25 -> IDocIndexEntry
                        case IDoc::Table:              // 26 -> IDocTable
                        case IDoc::Row:                // 27 -> IDocRow
                        case IDoc::Entry:              // 28 -> IDocEntry
                        case IDoc::Section:            // 29 -> IDocSection
                        case IDoc::Verbatim:           // 30 -> IDocVerbatim
                        case IDoc::Copy:               // 31 -> IDocCopy
                        case IDoc::TocList:            // 32 -> IDocTocList
                        case IDoc::TocItem:            // 33 -> IDocTocItem
                        case IDoc::Anchor:             // 34 -> IDocAnchor
                        case IDoc::Symbol:             // 35 -> IDocSymbol
                        case IDoc::Internal:           // 36 -> IDocInternal
                        case IDoc::Root:               // 37 -> IDocRoot
                        case IDoc::ParameterItem:      // 38 -> IDocParameterItem
                            break;

                        default: break;
                    }

                	found=true;
                }
            }
            docIt->release();
        }

        // detail
        if (detailed)
        {
            IDocIterator *docIt = detailed->contents();
            IDoc* docCur = nullptr;
            IDocPara* docPara = nullptr;
            IDocIterator *docIter2 = nullptr;
            IDocIterator *docIter3 = nullptr;
            IDoc* docParaCur = nullptr;

            for (docIt->toFirst(); (docCur = docIt->current()); docIt->toNext())
            {
                if (docCur) // method has brief description
                {
                	printf("doc(detailed) : kind = %d.\n", docCur->kind());
                	// detailed の場合は、contents が存在するケースがある?
            		switch (docCur->kind())
                    {
                        case IDoc::Para:
                            printf("docPara convert enter.\n");
                            docPara = static_cast<IDocPara*>(docCur);
                            if(docPara == nullptr) 
                            {
                                printf("docPara is null.\n");
                                continue;
                            }
                            printf("docPara->kind() = %d.\n", docPara->kind());
                    	    // if(docPara->text() == nullptr) 
                    		// { 
                    		// 	printf("docPara->text() is null.\n");
                    		// 	continue; 
                    		// }
                    	    // printf("docPara->text() = %d.\n", docPara->text()->isEmpty());
                            // printf("docPara->text() = %s.\n", docPara->text()->latin1());
                            printf("docPara convert exit.\n");

                            //// TODO: 変換NG(contents が存在しないため)
                            //printf("docIter2 contents enter.\n");
                            //docIter2 = docPara->contents();
                            //if(docIter2 == nullptr) 
                            //{
                            //    printf("docIter2 is null.\n");
                            //    continue;
                            //}
                            //printf("docIter2 contents exit.\n");
                            //
                            //printf("docIter3 contents enter.\n");
                            //docParaCur = docIter2->current();
                            //docIter3 = docParaCur->contents();
                            //if(docIter3 == nullptr) 
                            //{
                            //    continue;
                            //    printf("docIter3 is null.\n");
                            //}
                            //printf("docIter3 contents exit.\n");
                            //
                            //for (docIter3->toFirst(); (docParaCur = docIter3->current()); docIter3->toNext())
                            //{
                            //    printf("enter.\n");
                            //    if(docParaCur != nullptr)
                            //    {
                            //        printf("Doc(Para): kind = %d.\n", docParaCur->kind());
                            //    }
                            //    printf("exit.\n");
                            //}
                            break;

                        case IDoc::Text:
                        case IDoc::MarkupModifier:     //  3 -> IDocMarkupModifier
                        case IDoc::ItemizedList:       //  4 -> IDocItemizedList
                        case IDoc::OrderedList:        //  5 -> IDocOrderedList
                        case IDoc::ListItem:           //  6 -> IDocListItem
                        case IDoc::ParameterList:      //  7 -> IDocParameterList
                        case IDoc::Parameter:          //  8 -> IDocParameter
                        case IDoc::SimpleSect:         //  9 -> IDocSimpleSect
                        case IDoc::Title:              // 10 -> IDocTitle
                        case IDoc::Ref:                // 11 -> IDocRef
                        case IDoc::VariableList:       // 12 -> IDocVariableList
                        case IDoc::VariableListEntry:  // 13 -> IDocVariableListEntry
                        case IDoc::HRuler:             // 14 -> IDocHRuler
                        case IDoc::LineBreak:          // 15 -> IDocLineBreak
                        case IDoc::ULink:              // 16 -> IDocULink
                        case IDoc::EMail:              // 17 -> IDocEMail
                        case IDoc::Link:               // 18 -> IDocLink
                        case IDoc::ProgramListing:     // 19 -> IDocProgramListing
                        case IDoc::CodeLine:           // 20 -> IDocCodeLine
                        case IDoc::Highlight:          // 21 -> IDocHighlight
                        case IDoc::Formula:            // 22 -> IDocFormula
                        case IDoc::Image:              // 23 -> IDocImage
                        case IDoc::DotFile:            // 24 -> IDocDotFile
                        case IDoc::IndexEntry:         // 25 -> IDocIndexEntry
                        case IDoc::Table:              // 26 -> IDocTable
                        case IDoc::Row:                // 27 -> IDocRow
                        case IDoc::Entry:              // 28 -> IDocEntry
                        case IDoc::Section:            // 29 -> IDocSection
                        case IDoc::Verbatim:           // 30 -> IDocVerbatim
                        case IDoc::Copy:               // 31 -> IDocCopy
                        case IDoc::TocList:            // 32 -> IDocTocList
                        case IDoc::TocItem:            // 33 -> IDocTocItem
                        case IDoc::Anchor:             // 34 -> IDocAnchor
                        case IDoc::Symbol:             // 35 -> IDocSymbol
                        case IDoc::Internal:           // 36 -> IDocInternal
                        case IDoc::Root:               // 37 -> IDocRoot
                        case IDoc::ParameterItem:      // 38 -> IDocParameterItem
                            break;

                        default: break;
                    }

                	found = true;
                }
            }
            docIt->release();
        }
        return found;
    }

    /*
    Compound compoundById(std::string id)
    {
        return Compound::Create (doxygen->compoundById(id));
    }

    Compound compoundByName(std::string name)
    {
        return Compound::Create (doxygen->compoundById(name));
    }

    Compound memberById(std::string id)
    {
        return Compound::Create (doxygen->compoundById(id));
    }

    Compound memberByName(std::string name)
    {
        return Compound::Create (doxygen->compoundById(name));
    }
    */
    void printDoxygen(IDoxygen* doxygen)
    {
        int numClasses=0;
        int numDocClasses=0;
        int numStructs=0;
        int numUnions=0;
        int numInterfaces=0;
        int numExceptions=0;
        int numNamespaces=0;
        int numFiles=0;
        int numGroups=0;
        int numPages=0;
        int numPackages=0;
        int numPubMethods=0;
        int numProMethods=0;
        int numPriMethods=0;
        int numDocPubMethods=0;
        int numDocProMethods=0;
        int numDocPriMethods=0;
        int numFunctions=0;
        int numAttributes=0;
        int numVariables=0;
        int numDocFunctions=0;
        int numDocAttributes=0;
        int numDocVariables=0;
        int numParams=0;

        // index.xml の解析
        // compound の取得
        ICompoundIterator *cli = doxygen->compounds();
        ICompound *comp;
        for (cli->toFirst(); (comp = cli->current()); cli->toNext())
        {
            // パターンが複数ある?
            // compound タグ/name
            // memberdef タグ/name?
            printf("Processing %s\n", comp->name()->latin1());
            printf("ID %s\n" , comp->id()->latin1());
            // CompoundKind
            // printf("CompoundKind %d\n" , comp->kind());
            printf("CompoundKind %s\n" , comp->kindString()->latin1());
            bool hasDocs = isDocumented(comp->briefDescription(), comp->detailedDescription());
            switch (comp->kind())
            {
                case ICompound::Class:
                    numClasses++;
                    if (hasDocs)
                    {
                        numDocClasses++;
                    }
                    break;
                case ICompound::Struct:     numStructs++;    break;
                case ICompound::Union:      numUnions++;     break;
                case ICompound::Interface:  numInterfaces++; break;
                case ICompound::Exception:  numExceptions++; break;
                case ICompound::Namespace:  numNamespaces++; break;
                case ICompound::File:       numFiles++;      break;
                case ICompound::Group:      numGroups++;     break;
                case ICompound::Page:       numPages++;      break;
                default: break;
            }

            // compound の下層タグの取得
            ISectionIterator *sli = comp->sections();
            ISection *sec;
            for (sli->toFirst(); (sec = sli->current()); sli->toNext())
            {
                // member タグの取得
                IMemberIterator *mli = sec->members();
                IMember *mem;
                for (mli->toFirst(); (mem=mli->current()); mli->toNext())
                {
                    // MemberKind
                    printf("    (Member)%s\n", mem->name()->latin1());
                    printf("    (Member)ID %s\n" , mem->id()->latin1());
                    // printf("MemberKind %d\n" , mem->kind());
                    printf("    (Member)Kind %s\n" , mem->kindString()->latin1());
                    printf("    (Member)Protection %s\n" , mem->protection()->latin1());

                    IParamIterator *pli = mem->parameters();
                    IParam *par;
                    if (comp->kind()==ICompound::Class || 
                        comp->kind()==ICompound::Struct || 
                        comp->kind()==ICompound::Interface)
                    {
                        if (mem->kind()==IMember::Function ||
                            mem->kind()==IMember::Prototype ||
                            mem->kind()==IMember::Signal ||
                            mem->kind()==IMember::Slot ||
                            mem->kind()==IMember::DCOP) // is a "method"
                        {
                            // pxd で対処する項目は public のみ
                            if (mem->section()->isPublic())
                            {
                                numPubMethods++;
                                if (isDocumented(mem->briefDescription(), mem->detailedDescription(), mem->inbodyDescription()))
                                {
                                    numDocPubMethods++;
                                }
                            }
                            else if (mem->section()->isProtected())
                            {
                                numProMethods++;
                                if (isDocumented(mem->briefDescription(), mem->detailedDescription()))
                                {
                                    numDocProMethods++;
                                }
                            }
                            else if (mem->section()->isPrivate())
                            {
                                numPriMethods++;
                                if (isDocumented(mem->briefDescription(), mem->detailedDescription()))
                                {
                                    numDocPriMethods++;
                                }
                            }
                        }
                        else if (mem->kind()==IMember::Variable || 
                                 mem->kind()==IMember::Property) // is an "attribute"
                        {
                            numAttributes++;
                            if (isDocumented(mem->briefDescription(), mem->detailedDescription()))
                            {
                                numDocAttributes++;
                            }
                        }
                    }
                    else if (comp->kind()==ICompound::File ||
                             comp->kind()==ICompound::Namespace
                            )
                    {
                        if (mem->kind()==IMember::Function ||
                            mem->kind()==IMember::Prototype ||
                            mem->kind()==IMember::Signal ||
                            mem->kind()==IMember::Slot ||
                            mem->kind()==IMember::DCOP
                            ) // is a "method"
                        {
                            numFunctions++;
                            if (isDocumented(mem->briefDescription(), mem->detailedDescription()))
                            {
                                numDocFunctions++;
                            }
                        }
                        else if (mem->kind()==IMember::Variable || 
                                 mem->kind()==IMember::Property
                                ) // is an "attribute"
                        {
                            numVariables++;
                            if (isDocumented(mem->briefDescription(),mem->detailedDescription()))
                            {
                                numDocVariables++;
                            }
                        }
                    }
               
                    for (pli->toFirst();(par=pli->current());pli->toNext())
                    {
                        numParams++;
                    }
                    const char *type = mem->typeString()->latin1();
                    if (type && strcmp(type, "void"))
                    {
                        numParams++; // count non-void return types as well
                    }
                    pli->release();
                }
                mli->release();
            }
            sli->release();

            comp->release();
        }
        cli->release();

        int numMethods    = numPubMethods+numProMethods+numPriMethods;
        int numDocMethods = numDocPubMethods+numDocProMethods+numDocPriMethods;

        printf("Metrics:\n");
        printf("-----------------------------------\n");
        if (numClasses>0)    printf("Classes:     %10d (%d documented)\n",numClasses, numDocClasses);
        if (numStructs>0)    printf("Structs:     %10d\n",numStructs);
        if (numUnions>0)     printf("Unions:      %10d\n",numUnions);
        if (numInterfaces>0) printf("Interfaces:  %10d\n",numInterfaces);
        if (numExceptions>0) printf("Exceptions:  %10d\n",numExceptions);
        if (numNamespaces>0) printf("Namespaces:  %10d\n",numNamespaces);
        if (numFiles>0)      printf("Files:       %10d\n",numFiles);
        if (numGroups>0)     printf("Groups:      %10d\n",numGroups);
        if (numPages>0)      printf("Pages:       %10d\n",numPages);
        if (numPackages>0)   printf("Packages:    %10d\n",numPackages);
        if (numMethods>0)    printf("Methods:     %10d (%d documented)\n",numMethods,numDocMethods);
        if (numPubMethods>0) printf("  Public:    %10d (%d documented)\n",numPubMethods,numDocPubMethods);
        if (numProMethods>0) printf("  Protected: %10d (%d documented)\n",numProMethods,numDocProMethods);
        if (numPriMethods>0) printf("  Private:   %10d (%d documented)\n",numPriMethods,numDocPriMethods);
        if (numFunctions>0)  printf("Functions:   %10d (%d documented)\n",numFunctions,numDocFunctions);
        if (numAttributes>0) printf("Attributes:  %10d (%d documented)\n",numAttributes,numDocAttributes);
        if (numVariables>0)  printf("Variables:   %10d (%d documented)\n",numVariables,numDocVariables);
        if (numParams>0)     printf("Params:      %10d\n",numParams);
        printf("-----------------------------------\n");
        if (numClasses>0)    printf("Avg. #methods/compound:  %10f\n",(double)numMethods/(double)numClasses);
        if (numMethods>0)    printf("Avg. #params/method:     %10f\n",(double)numParams/(double)numMethods);
        printf("-----------------------------------\n");
    }
};

// TODO: 対象モジュールのインクルードパスを取得
// # BUILTIN_HEADERS_DIR = os.path.join(os.path.dirname(__file__), 'include')
// # Types declared by pycparser fake headers that we should ignore
