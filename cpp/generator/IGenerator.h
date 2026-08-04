#pragma once

#include <string>

class IGenerator
{
public:
    IGenerator() = default;
    virtual ~IGenerator() = default;

    virtual std::string GetType() const noexcept = 0;
    virtual std::string GetString() = 0;
    virtual void SetString(std::string str) = 0;
};


