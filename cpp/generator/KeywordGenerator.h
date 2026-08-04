#pragma once

#include <string>
#include "IGenerator.h"

class KeywordGenerator : public IGenerator
{
private:
    std::string str;

public:
    KeywordGenerator() = default;
    virtual ~KeywordGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "keyword: ";
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


