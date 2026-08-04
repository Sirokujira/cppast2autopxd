#pragma once

#include <string>
#include "IGenerator.h"

class PreprocessorGenerator : public IGenerator
{
private:
    std::string str;

public:
    PreprocessorGenerator() = default;
    virtual ~PreprocessorGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "preprocessor: ";
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


