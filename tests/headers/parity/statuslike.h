// statuslike.h - self-contained, committed fixture capturing the hard
// real-world constructs found in draco's core/status.h: a class-nested enum,
// =default / move constructors, std:: types, and a scoped enum return type.
#pragma once

#include <string>

namespace draco {

class Status {
 public:
  enum Code {
    OK = 0,
    DRACO_ERROR = -1,
    IO_ERROR = -2,
    INVALID_PARAMETER = -3,
  };

  Status();
  Status(const Status& status) = default;
  Status(Status&& status) = default;
  explicit Status(Code code);
  Status(Code code, const std::string& error_msg);

  Code code() const;
  const std::string& error_msg_string() const;
  bool ok() const;

 private:
  Code code_;
  std::string error_msg_;
};

}  // namespace draco
