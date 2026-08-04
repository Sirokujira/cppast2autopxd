#pragma once

#include <string>
#include "IGenerator.h"

class CommentGenerator : public IGenerator
{
private:
    std::string str;

public:
    CommentGenerator() = default;
    virtual ~CommentGenerator() = default;

    virtual std::string GetType() const noexcept override
    {
        return "comment: ";
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


