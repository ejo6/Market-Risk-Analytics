#pragma once

#include "mra/models/model.hpp"

namespace mra {

// "sample": unbiased sample covariance, S = X'X / (T - 1) on demeaned columns.
// Matches np.cov(returns, rowvar=False). The reference implementation.
class SampleCovariance final : public CovarianceModel {
public:
    explicit SampleCovariance(const Params& p);
    [[nodiscard]] Matrix estimate(const MatrixRef& returns) const override;
};

// "ewma": RiskMetrics exponentially weighted covariance.
//   S_t = lambda * S_{t-1} + (1 - lambda) * r_t r_t'
// Params: decay = lambda (default 0.94, the RiskMetrics daily value). Not
// called "lambda" because that is a Python keyword: ewma(..., lambda=0.9)
// would be a syntax error.
// Returns S_T, the estimate after the last row.
//
// Seed: S_0 = 0 (RiskMetrics). Weights then sum to 1 - lambda^T, so short
//   series are biased low; negligible once T >> 1 / (1 - lambda).
// Mean: not demeaned; RiskMetrics assumes a zero daily mean.
// Effective window: 99% of the weight sits in the last ln(0.01) / ln(lambda)
//   days, about 75 at lambda = 0.94 and 151 at 0.97.
class EwmaCovariance final : public CovarianceModel {
public:
    explicit EwmaCovariance(const Params& p);
    [[nodiscard]] Matrix estimate(const MatrixRef& returns) const override;

private:
    double lambda_;
};

// "ledoit_wolf": shrink the sample covariance toward a structured target,
//   S* = delta * F + (1 - delta) * S,   F = mean(diag(S)) * I
// with delta chosen analytically to minimize expected error (Ledoit & Wolf 2004,
// "A well-conditioned estimator for large-dimensional covariance matrices").
// Parity target: sklearn.covariance.LedoitWolf().fit(returns).covariance_
// Watch out: sklearn's S divides by T, not T - 1.
class LedoitWolfCovariance final : public CovarianceModel {
public:
    explicit LedoitWolfCovariance(const Params& p);
    [[nodiscard]] Matrix estimate(const MatrixRef& returns) const override;
};

}  // namespace mra
