#pragma once

#include <string>
#include "IGenerator.h"

class FloatliteralGenerator : public IGenerator
{
private:
    std::string str;

public:
    FloatliteralGenerator() = default;
    virtual ~FloatliteralGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "floatliteral: ";
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


