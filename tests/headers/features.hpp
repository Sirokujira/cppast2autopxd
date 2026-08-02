// Exercises the wider feature matrix: enums (plain + scoped), typedefs,
// using-aliases, std:: container mapping, overloads, static/const methods,
// operators, default arguments, access filtering, copy/move constructors.
#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace demo {

enum Color {
    RED,
    GREEN = 5,
    BLUE
};

enum class Mode {
    Fast,
    Slow
};

typedef unsigned int index_t;
using name_map = std::map<std::string, int>;

class Widget {
public:
    Widget();
    explicit Widget(int id);
    Widget(const Widget& other);
    Widget(Widget&& other);
    ~Widget();

    int id() const;
    void rename(const std::string& name);
    std::string name() const;
    const std::string& title() const;
    static Widget make(int id = 0);
    double& operator[](std::size_t idx);
    bool operator==(const Widget& other) const;
    Widget* clone() const;

    int visible;

private:
    int secret_;
    void hidden();
};

std::vector<std::string> split(const std::string& text, char sep = ',');
int add(int a, int b);

}  // namespace demo
