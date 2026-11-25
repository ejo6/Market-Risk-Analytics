#pragma once

// Standard normal distribution helpers. <cmath> has erfc but no inverse CDF.
// Shared by parametric_normal tail risk, and later Monte Carlo and the Kupiec
// backtest.

namespace mra {

// Density phi(x) = exp(-x^2 / 2) / sqrt(2 pi).
[[nodiscard]] double normal_pdf(double x);

// CDF Phi(x), via erfc (accurate in both tails, unlike 1 - erf).
[[nodiscard]] double normal_cdf(double x);

// Inverse CDF Phi^-1(p) for p in (0, 1): Acklam's rational approximation
// (~1e-9 relative error) refined with one Halley step to near machine precision.
// Throws std::invalid_argument outside (0, 1).
[[nodiscard]] double inverse_normal_cdf(double p);

}  // namespace mra
