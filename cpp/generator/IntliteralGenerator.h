#pragma once

#include <string>
#include "IGenerator.h"

class IntliteralGenerator : public IGenerator
{
private:
    std::string str;

public:
    IntliteralGenerator() = default;
    virtual ~IntliteralGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "intliteral: ";
    };
    
    virtual std::string GetString() override
    {
        return str;
    };
    
    virtual void SetString(std::string str) override
    {
        this->str = str;
    };
};


