#pragma once

#include <string>
#include "IGenerator.h"

class StrliteralGenerator : public IGenerator
{
private:
    std::string str;

public:
    StrliteralGenerator() = default;
    virtual ~StrliteralGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "strliteral: ";
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


