#pragma once

#include <string>
#include "IGenerator.h"

class TokenGenerator : public IGenerator
{
protected:
    std::string str;

public:
    TokenGenerator() = default;
    virtual ~TokenGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "token: ";
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


