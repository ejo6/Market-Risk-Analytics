#pragma once

#include <string_view>

namespace mra {

// Version of the C++ core. Used by the bindings to confirm the build works.
std::string_view version() noexcept;

}  // namespace mra
