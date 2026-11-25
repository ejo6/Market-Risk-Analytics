#pragma once

// Shared numeric types and conventions for the analytics core.
//
// Conventions (every function and model in mra follows these; parity tests
// depend on them):
//   * A returns panel is a T x N matrix: rows are dates (oldest first), columns
//     are assets. The core never sees symbols; the caller keeps the symbol list
//     next to the matrix.
//   * Returns are SIMPLE daily TOTAL returns, r_t = s_t (P_t + D_t) / P_{t-1} - 1,
//     as produced by the lake's returns view. Simple returns aggregate across
//     assets (portfolio return = w' r); log returns aggregate across time.
//   * No NaNs. Aligning symbols and dropping gaps happens before the core.
//   * Risk figures (VaR, ES, drawdown) are POSITIVE fractions of portfolio
//     value: var = 0.023 means "a 2.3% loss".
//   * Everything is daily. Annualizing (x sqrt(252)) is the caller's choice.

#include <Eigen/Dense>

#include <functional>
#include <map>
#include <stdexcept>
#include <string>

namespace mra {

using Vector = Eigen::VectorXd;
using Matrix = Eigen::MatrixXd;
using Index = Eigen::Index;

// Read-only views: callers can pass Eigen blocks or numpy arrays without a copy
// (as long as the memory layout matches; otherwise Eigen makes a temporary).
using VectorRef = Eigen::Ref<const Vector>;
using MatrixRef = Eigen::Ref<const Matrix>;

// Model hyperparameters, e.g. {"decay": 0.94} or {"confidence": 0.99}.
// name -> double so it maps 1:1 onto Python kwargs and a JSON config.
// std::less<> enables lookups by string_view without building a std::string.
using Params = std::map<std::string, double, std::less<>>;

// Thrown by code that is declared but not written yet.
// Surfaces in Python as NotImplementedError.
class NotImplemented : public std::logic_error {
public:
    using std::logic_error::logic_error;
};

}  // namespace mra
