#pragma once

#include <string>
#include "IGenerator.h"

class IdentifierGenerator : public IGenerator
{
private:
    std::string str;

public:
    IdentifierGenerator() = default;
    virtual ~IdentifierGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "identifier: ";
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


