#pragma once

// Portfolio-level risk from weights and a covariance matrix. Plain functions:
// each has one correct definition, so there is nothing to register.
//
// weights: N-vector, same column order as the covariance matrix. Weights are
// fractions of portfolio value; they need not sum to 1 (leverage, cash) and may
// be negative (shorts).

#include "mra/types.hpp"

namespace mra {

// sigma_p = sqrt(w' S w), daily.
[[nodiscard]] double portfolio_volatility(const VectorRef& weights, const MatrixRef& cov);

// Euler risk contributions: how much of sigma_p each asset is responsible for.
//   RC_i = w_i * (S w)_i / sigma_p
// They sum exactly to sigma_p (Euler's theorem: sigma_p is homogeneous of
// degree 1 in w). Divide by sigma_p for percentage contributions.
// Risk parity is the portfolio where every RC_i is equal; HRP builds on this.
//
// A zero-risk portfolio (sigma_p == 0, e.g. all weights 0) returns a zero
// vector rather than throwing: all cash is a valid portfolio, and the
// contributions still sum to sigma_p.
[[nodiscard]] Vector risk_contributions(const VectorRef& weights, const MatrixRef& cov);

}  // namespace mra
