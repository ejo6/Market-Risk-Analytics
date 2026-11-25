#pragma once

#include "mra/models/model.hpp"

namespace mra {

// "historical": historical simulation. Treat the past T returns as equally
// likely scenarios for tomorrow.
//   q   = quantile(r, 1 - confidence)    linear interpolation, as np.quantile
//   var = -q
//   es  = -mean(r[r <= q])                average of the tail at or beyond VaR
// Params: confidence (default 0.99).
//
// Note how few points the tail has: at 99% with T = 500 days, ES averages 5
// returns. Historical VaR is noisy and jumps when an old crash leaves the window.
class HistoricalTailRisk final : public TailRiskModel {
public:
    explicit HistoricalTailRisk(const Params& p);
    [[nodiscard]] TailRisk estimate(const VectorRef& returns) const override;

private:
    double confidence_;
};

// "parametric_normal": assume r ~ N(mu, sigma^2), the variance-covariance method.
//   z   = Phi^-1(1 - confidence)          standard normal quantile (negative)
//   var = -(mu + sigma * z)
//   es  = -(mu - sigma * phi(z) / (1 - confidence))
// with mu the sample mean, sigma the sample std (T - 1), phi the normal density.
// Params: confidence (default 0.99).
// Parity target: scipy.stats.norm.ppf / norm.pdf with the same mu and sigma.
//
// Phi^-1 comes from mra/normal.hpp (Acklam + one Halley step, ~1e-15).
// The normal has thin tails: on fat-tailed data its VaR/ES sit below
// "historical" at high confidence. That gap is the tail risk it misses.
class ParametricNormalTailRisk final : public TailRiskModel {
public:
    explicit ParametricNormalTailRisk(const Params& p);
    [[nodiscard]] TailRisk estimate(const VectorRef& returns) const override;

private:
    double confidence_;
};

}  // namespace mra
