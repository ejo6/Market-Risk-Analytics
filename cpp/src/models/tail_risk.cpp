#include "mra/models/tail_risk.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>

#include "mra/models/registry.hpp"
#include "mra/normal.hpp"

namespace mra {

namespace {

double checked_confidence(const Params& p) {
    const double c = param(p, "confidence");
    if (!(c > 0.0 && c < 1.0)) throw std::invalid_argument("confidence must be in (0, 1)");
    return c;
}

void require_series(const VectorRef& returns, Index min_size) {
    if (returns.size() < min_size) {
        throw std::invalid_argument("return series needs at least " + std::to_string(min_size) +
                                    " points, got " + std::to_string(returns.size()));
    }
}

// Quantile with linear interpolation between order statistics; identical to numpy's default (method="linear"). `sorted` must be ascending.
double quantile_linear(const std::vector<double>& sorted, double q) {
    const double h = (static_cast<double>(sorted.size()) - 1.0) * q;
    const auto lo = static_cast<std::size_t>(std::floor(h));
    const std::size_t hi = std::min(lo + 1, sorted.size() - 1);
    return sorted[lo] + (h - static_cast<double>(lo)) * (sorted[hi] - sorted[lo]);
}

}  // namespace

// historical 

HistoricalTailRisk::HistoricalTailRisk(const Params& p) : confidence_(checked_confidence(p)) {}

TailRisk HistoricalTailRisk::estimate(const VectorRef& returns) const {
    require_series(returns, 2);

    // Sort a copy; the input is a read-only view. A full sort is O(T log T);  std::nth_element would be O(T) but we also need the tail for ES.
    std::vector<double> sorted(returns.data(), returns.data() + returns.size());
    std::sort(sorted.begin(), sorted.end());

    const double q = quantile_linear(sorted, 1.0 - confidence_);

    // The tail is every return at or below q. Since q >= sorted[0], it always has at least one point.
    double tail_sum = 0.0;
    std::size_t tail_n = 0;
    for (double r : sorted) {
        if (r > q) break;  // sorted, so the rest are above q too
        tail_sum += r;
        ++tail_n;
    }

    return {-q, -tail_sum / static_cast<double>(tail_n)};
}

// parametric_normal

ParametricNormalTailRisk::ParametricNormalTailRisk(const Params& p)
    : confidence_(checked_confidence(p)) {}

TailRisk ParametricNormalTailRisk::estimate(const VectorRef& returns) const {
    require_series(returns, 2);

    const auto t = static_cast<double>(returns.size());
    const double mu = returns.mean();
    // Sample std, T - 1, to match scipy's series.std(ddof=1).
    const double sigma = std::sqrt((returns.array() - mu).square().sum() / (t - 1.0));

    const double alpha = 1.0 - confidence_;
    const double z = inverse_normal_cdf(alpha);  // negative: the left-tail cutoff

    const double var = -(mu + sigma * z);
    // The mean of a standard normal below z is -phi(z) / alpha.
    const double es = -(mu - sigma * normal_pdf(z) / alpha);
    return {var, es};
}

}  // namespace mra
