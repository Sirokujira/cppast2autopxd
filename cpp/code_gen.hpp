#pragma once
#include <iostream>
#include <fstream>
#include <stack>

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

// code_generator
#include "generator/IGenerator.h"
#include "generator/CommentGenerator.h"
#include "generator/FloatliteralGenerator.h"
#include "generator/IdentifierGenerator.h"
#include "generator/IntliteralGenerator.h"
#include "generator/KeywordGenerator.h"
#include "generator/PreprocessorGenerator.h"
#include "generator/PunctuationGenerator.h"
#include "generator/ReferenceGenerator.h"
#include "generator/StrliteralGenerator.h"
#include "generator/TokenGenerator.h"

// 細かい書き出しは、pxd_generator 内で対応する?
// override で対応?
// print the declaration of the entity
// it will only use a single line
// derive from code_generator and implement various callbacks for printing
// it will print into a std::string
class pxd_generator : public cppast::code_generator
{
    std::string str_;                // the result
    bool was_newline_ = false;       // whether or not the last token was a newline
    // IGenetator?
    std::vector<IGenerator*> generators;
    // needed for lazily printing them

public:
    pxd_generator(const cppast::cpp_entity& e)
    {
        // kickoff code generation here
        cppast::generate_code(*this, e);
    }

    // return the result
    const std::string& str() const noexcept
    {
        return str_;
    }

    std::vector<IGenerator*>& generatorLists()
    {
        return generators;
    }

private:
    cppast::formatting do_get_formatting() const override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_get_formatting";
        std::cout << "\n";
#endif
        // operator(+-/*)/comma(,)
        // return formatting_flags::brace_nl | formatting_flags::operator_ws | formatting_flags::comma_ws;

        return {};
    }
    // called to retrieve the generation options of an entity
    generation_options do_get_options(const cppast::cpp_entity& e,
                                      cppast::cpp_access_specifier_kind kind) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_get_options";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        //std::cout << (void)e;
        //std::cout << (void)kind;

        // generate declaration only
        return pxd_generator::declaration;
    }

    /// \effects Will be invoked before code of an entity is generated.
    /// The base class version has no effect.
    void on_begin(const output& out, const cppast::cpp_entity& e) override
    {
        // str_ += "on_begin";
        // str_ += "\n";
        // std::cout << "on_begin";
        // std::cout << "\n";

        //std::cout << out;
        //std::cout << e;

        (void)out;
        (void)e;
    }

    /// \effects Will be invoked after all code of an entity has been generated.
    /// The base class version has no effect.
    void on_end(const output& out, const cppast::cpp_entity& e) override
    {
#ifdef GENERATOR_DEBUG
        // str_ += "on_end";
        // str_ += "\n";
        std::cout << "on_end";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        (void)out;
        (void)e;
    }

    void on_container_end(const output& out, const cppast::cpp_entity& e) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "on_container_end";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        (void)out;
        (void)e;
    }

    // no need to handle indentation, as only a single line is used
    void do_indent() override {}
    void do_unindent() override {}

    void do_write_keyword(cppast::string_view keyword) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_keyword";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "keyword : ";
        // const
        // void
        // int
        // class
        // public
        // override
        // 戻り値か、内部の引数か判断はどうやるか？
        // 他のデータがないことから対応する？
        str_ += keyword.c_str();
        str_ += "\n";
        // std::cout << str_;

        // 2
        IGenerator* generator = new KeywordGenerator();
        generator->SetString(keyword.c_str());
        generators.push_back(generator);
    }

    void do_write_identifier(cppast::string_view str) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_identifier";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "identifier : ";
        // AttributeOctahedronTransform::
        str_ += str.c_str();
        str_ += "\n";
        // std::cout << str_;

        // 2
        IGenerator* generator = new IdentifierGenerator();
        generator->SetString(str.c_str());
        generators.push_back(generator);
    }

    // Called for a cross-reference to another declared entity (a type/symbol
    // name). The base class default just forwards `name` to do_write_token_seq;
    // we instead capture it as a ReferenceGenerator (which derives from
    // TokenGenerator, so downstream token-matching still works) so references
    // are tagged distinctly. Must return bool (false == reference excluded).
    bool do_write_reference(type_safe::array_ref<const cppast::cpp_entity_id> id,
                            cppast::string_view name) override
    {
        (void)id;
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_reference";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "reference : ";
        str_ += name.c_str();
        str_ += "\n";

        IGenerator* generator = new ReferenceGenerator();
        generator->SetString(name.c_str());
        generators.push_back(generator);
        return true;
    }

    void do_write_punctuation(cppast::string_view punct) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_punctuation";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "punctuation : ";
        // <PointIndex
        // <PointIndex
        // >
        // &
        // ,
        // (draco::PointAttribute
        // )
        // ;
        // *
        str_ += punct.c_str();
        str_ += "\n";
        // std::cout << str_;

        // 2
        IGenerator* generator = new PunctuationGenerator();
        generator->SetString(punct.c_str());
        generators.push_back(generator);
    }

    void do_write_str_literal(cppast::string_view str) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_str_literal";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "str : ";
        str_ += "\n";
        str_ += str.c_str();
        str_ += "\n";

        // 2
        IGenerator* generator = new StrliteralGenerator();
        generator->SetString(str.c_str());
        generators.push_back(generator);
    }

    void do_write_int_literal(cppast::string_view str) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_int_literal";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "int : ";
        str_ += str.c_str();
        str_ += "\n";

        // 2
        IGenerator* generator = new IntliteralGenerator();
        generator->SetString(str.c_str());
        generators.push_back(generator);
    }

    void do_write_float_literal(cppast::string_view str) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_float_literal";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "float : ";
        str_ += str.c_str();
        str_ += "\n";
        // std::cout << str_;

        // 2
        IGenerator* generator = new FloatliteralGenerator();
        generator->SetString(str.c_str());
        generators.push_back(generator);
    }

    void do_write_preprocessor(cppast::string_view punct) override
    {
        str_ += "preprocessor : ";
        // 先頭 : #include/#define
        // include の場合
        // 次 : "file
        // 次 : "
        // define の場合
        // 次 : identifier
        str_ += punct.c_str();
        str_ += "\n";
        // std::cout << str_;

        // 2
        IGenerator* generator = new PreprocessorGenerator();
        generator->SetString(punct.c_str());
        generators.push_back(generator);
    }

    void do_write_comment(cppast::string_view str) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_comment";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        str_ += "comment : ";
        str_ += str.c_str();
        str_ += "\n";
        // std::cout << str_;

        // 2
        IGenerator* generator = new CommentGenerator();
        generator->SetString(str.c_str());
        generators.push_back(generator);
    }

    // called when a generic token sequence should be generated
    // there are specialized callbacks for various token kinds,
    // to e.g. implement syntax highlighting
    void do_write_token_seq(cppast::string_view tokens) override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_token_seq";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        if (was_newline_)
        {
            // lazily append newline as space
            str_ += ',';
            was_newline_ = false;
        }

        // append tokens
        str_ += "token : ";
        str_ += tokens.c_str();
        str_ += "\n";
        // std::cout << str_;

        // 2
        IGenerator* generator = new TokenGenerator();
        generator->SetString(tokens.c_str());
        generators.push_back(generator);
    }

    // called when a newline should be generated
    // we're lazy as it will always generate a trailing newline,
    // we don't want
    void do_write_newline() override
    {
#ifdef GENERATOR_DEBUG
        std::cout << "do_write_newline";
        std::cout << "\n";
#endif // GENERATOR_DEBUG
        was_newline_ = true;
    }
};
