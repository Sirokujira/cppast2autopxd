#pragma once

#include <string>
#include "TokenGenerator.h"

// A reference is a cross-reference to another declared entity (a type or symbol
// name), emitted by cppast's do_write_reference(). It behaves like a token for
// layout purposes — downstream handlers that match TokenGenerator (e.g. template
// type-name detection, RHS type accumulation) must also see references — so it
// derives from TokenGenerator and inherits its GetString()/SetString(). Only
// GetType() differs, keeping references distinguishable for debugging and any
// reference-specific handling.
class ReferenceGenerator : public TokenGenerator
{
public:
    ReferenceGenerator() = default;
    virtual ~ReferenceGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "reference: ";
    };
};
