#include "mra/portfolio.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace mra {

namespace {

void require_shapes(const VectorRef& w, const MatrixRef& cov) {
    if (cov.rows() != cov.cols()) throw std::invalid_argument("covariance must be square");
    if (w.size() != cov.rows()) {
        throw std::invalid_argument("weights and covariance have different sizes");
    }
}

}  // namespace

double portfolio_volatility(const VectorRef& weights, const MatrixRef& cov) {
    require_shapes(weights, cov);
    // w' S w is a 1 x 1 expression; .value() pulls out the scalar.
    const double variance = (weights.transpose() * cov * weights).value();
    // A valid covariance is PSD, so variance >= 0 up to rounding. A clearly
    // negative value means the matrix is broken; don't hide that behind a NaN.
    if (variance < -1e-12) throw std::invalid_argument("covariance is not positive semi-definite");
    return std::sqrt(std::max(variance, 0.0));
}


Vector risk_contributions(const VectorRef& weights, const MatrixRef& cov) {
    require_shapes(weights, cov);
    
    // Each asset's covariance with the portfolio: Sw_i = Cov(r_i, r_p).
    // A vector Sw_i = covariance between asset i and its WHOLE portfolio,
    const Vector Sw = cov * weights;
    
    // Variance is the weighted sum of (covariance of the portfolio)
    const double variance = weights.dot(Sw);

    // If our variance is negative (barring flop arithmetic issue)
    if (variance < -1e-12) throw std::invalid_argument("covariance is not positive semi-definite");
    
    // The whole portfolios volatility
    const double sigma_p = std::sqrt(std::max(variance, 0.0));

    // If we have a "zero risk" portfolio, return a N size 0-vector
    if (sigma_p == 0.0) return Vector::Zero(weights.size());

    // RC_i = w_i * Sw_i / sigma_p
    // This is a vector of how much risk each asset contributes based on its weighted covariance
    return weights.cwiseProduct(Sw) / sigma_p;
}

}  // namespace mra
