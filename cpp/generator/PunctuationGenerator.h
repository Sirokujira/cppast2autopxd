#pragma once

#include <string>
#include "IGenerator.h"

class PunctuationGenerator : public IGenerator
{
private:
    std::string str;

public:
    PunctuationGenerator() = default;
    virtual ~PunctuationGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "punctuation: ";
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


