// pybind11 bindings: the mra._core extension module.
//
// Thin by design. Bindings only convert types (numpy <-> Eigen, kwargs <->
// Params, C++ exceptions -> Python exceptions); all logic lives in mra_core so
// the CLI and API run exactly the same code.

#include <pybind11/eigen.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>

#include "mra/drawdown.hpp"
#include "mra/models/registry.hpp"
#include "mra/portfolio.hpp"
#include "mra/version.hpp"

namespace py = pybind11;

namespace {

mra::Params to_params(const py::kwargs& kwargs) {
    mra::Params p;
    for (const auto& [key, value] : kwargs) p[py::cast<std::string>(key)] = py::cast<double>(value);
    return p;
}

template <class Model>
py::list list_infos(const mra::Registry<Model>& registry) {
    py::list out;
    for (const auto& info : registry.list()) {
        py::dict d;
        d["name"] = info.name;
        d["description"] = info.description;
        d["defaults"] = info.defaults;
        d["status"] = info.status == mra::ModelStatus::Ready ? "ready" : "stub";
        d["source"] = info.source;
        out.append(d);
    }
    return out;
}

}  // namespace

PYBIND11_MODULE(_core, m) {
    m.doc() = "mra C++ core";

    // C++ -> Python exceptions. pybind11 already maps std::invalid_argument to
    // ValueError; NotImplemented derives from std::logic_error, so it needs its
    // own translator or it would surface as a generic RuntimeError.
    py::register_exception_translator([](std::exception_ptr p) {
        try {
            if (p) std::rethrow_exception(p);
        } catch (const mra::NotImplemented& e) {
            PyErr_SetString(PyExc_NotImplementedError, e.what());
        }
    });

    m.def("version", [] { return std::string(mra::version()); },
          "Version of the C++ core library.");

    // ---- registry ----
    m.def("list_models", [](const std::string& family) -> py::list {
              const auto& r = mra::default_registry();
              if (family == "covariance") return list_infos(r.covariance);
              if (family == "tail_risk") return list_infos(r.tail_risk);
              throw std::invalid_argument("unknown model family: '" + family + "'");
          },
          py::arg("family"), "Models in a family ('covariance' or 'tail_risk').");

    // Returns are copied into Eigen's column-major layout if numpy hands us a
    // row-major (C-order) array; that's one O(T*N) copy, negligible next to
    // the estimate. Release the GIL so Python threads can run meanwhile.
    m.def("covariance",
          [](const mra::MatrixRef& returns, const std::string& model, const py::kwargs& kw) {
              auto est = mra::default_registry().covariance.create(model, to_params(kw));
              py::gil_scoped_release release;
              return est->estimate(returns);
          },
          py::arg("returns"), py::arg("model") = "sample",
          "N x N covariance of a T x N returns panel.");

    py::class_<mra::TailRisk>(m, "TailRisk")
        .def_readonly("var", &mra::TailRisk::var)
        .def_readonly("es", &mra::TailRisk::es)
        .def("__repr__", [](const mra::TailRisk& t) {
            return "TailRisk(var=" + std::to_string(t.var) + ", es=" + std::to_string(t.es) + ")";
        });

    m.def("tail_risk",
          [](const mra::VectorRef& returns, const std::string& model, const py::kwargs& kw) {
              auto est = mra::default_registry().tail_risk.create(model, to_params(kw));
              py::gil_scoped_release release;
              return est->estimate(returns);
          },
          py::arg("returns"), py::arg("model") = "historical",
          "One-day VaR and ES of a return series, as positive loss fractions.");

    // ---- portfolio ----
    m.def("portfolio_volatility", &mra::portfolio_volatility, py::arg("weights"), py::arg("cov"),
          "Daily portfolio volatility sqrt(w' S w).");
    m.def("risk_contributions", &mra::risk_contributions, py::arg("weights"), py::arg("cov"),
          "Euler risk contributions; they sum to portfolio volatility.");

    // ---- drawdown ----
    py::class_<mra::DrawdownStats>(m, "DrawdownStats")
        .def_readonly("max_drawdown", &mra::DrawdownStats::max_drawdown)
        .def_readonly("peak", &mra::DrawdownStats::peak)
        .def_readonly("trough", &mra::DrawdownStats::trough)
        .def_readonly("longest_underwater", &mra::DrawdownStats::longest_underwater);
    m.def("drawdown_stats", &mra::drawdown_stats, py::arg("returns"),
          "Max drawdown and time underwater of a daily return series.");
}
