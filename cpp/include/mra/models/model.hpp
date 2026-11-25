#pragma once

// Model interfaces, one per family. A family is defined by its inputs and
// outputs, not by how it works: a classical EWMA estimator and an ONNX model
// trained in Python can both be CovarianceModels.
//
// Models are immutable once built: all configuration comes in through Params
// at construction, and estimate() is const. That makes one instance safe to
// share across threads (Monte Carlo, backtest sweeps) without locks.

#include "mra/types.hpp"

namespace mra {

// Estimates the N x N covariance matrix of daily returns.
class CovarianceModel {
public:
    virtual ~CovarianceModel() = default;

    // returns: T x N panel (see types.hpp). Result is N x N, symmetric, and
    // positive semi-definite.
    [[nodiscard]] virtual Matrix estimate(const MatrixRef& returns) const = 0;
};

struct TailRisk {
    double var;  // Value at Risk, positive loss fraction
    double es;   // Expected Shortfall (CVaR), positive loss fraction, es >= var
};

// Estimates one-day VaR and ES of a single return series, usually the
// portfolio return series w' r_t. Confidence comes from the "confidence" param.
class TailRiskModel {
public:
    virtual ~TailRiskModel() = default;

    [[nodiscard]] virtual TailRisk estimate(const VectorRef& returns) const = 0;
};

}  // namespace mra
