#include <pybind11/pybind11.h>
#include <string>
#include "mra/version.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_core, m) {
    m.doc() = "mra C++ core";
    m.def("version", [] { return std::string(mra::version()); },
          "Version of the C++ core library.");
}
