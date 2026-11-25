#include "mra/models/covariance.hpp"

#include <stdexcept>
#include <string>
#include <algorithm>

#include "mra/models/registry.hpp"

namespace mra {

namespace {

void require_panel(const MatrixRef& returns, Index min_rows) {
    if (returns.cols() == 0) throw std::invalid_argument("returns panel has no assets");
    if (returns.rows() < min_rows) {
        throw std::invalid_argument("returns panel needs at least " + std::to_string(min_rows) +
                                    " rows, got " + std::to_string(returns.rows()));
    }
}

}  // namespace


SampleCovariance::SampleCovariance(const Params&) {}

Matrix SampleCovariance::estimate(const MatrixRef& returns) const {
    require_panel(returns, 2); // need at least 2 assets to compare
    // Num rows
    const auto t = static_cast<double>(returns.rows());

    // 1. Get the mean for each asset (column)
    // 2. Center the matrix (subtract the col_mean from everything)
    const Matrix centered = returns.rowwise() - returns.colwise().mean();

    // 3. multiple by the transpose to get the sum of squared deviations
    // 4. divide by n - 1 to get asset i varaince on centered[i][i] (diagonal), 
    //    and asset i/j covaraince in centered[i][j]
    return (centered.transpose() * centered) / (t - 1.0);
}


// EWMA is basically sample covariance, but wide variance in short timespans counts more
EwmaCovariance::EwmaCovariance(const Params& p) : lambda_(param(p, "decay")) {
    if (!(lambda_ > 0.0 && lambda_ < 1.0)) throw std::invalid_argument("decay must be in (0, 1)");
}

Matrix EwmaCovariance::estimate(const MatrixRef& returns) const {
    /*
    S = N x N zeros         (seed S_0)
    for each row r_t        (oldest first):
        S = lambda * S + (1 - lambda) * outer(r_t, r_t) 
    return S
    */

    require_panel(returns, 1);
    
    const Index n = returns.cols();
    // Seed S_0 = 0. Weights then sum to 1 - lambda^T, so short series are biased low
    Matrix s = Matrix::Zero(n, n);

    for (Index t = 0; t < returns.rows(); t++) {
        const Vector r = returns.row(t).transpose();
        s *= lambda_;
        s.noalias() += (1.0 - lambda_) * r * r.transpose();
    }
    return s;
}



// Ledoit Wolf helps us shrink noise in estimation for small sample sizes
// A good example of where we'd need this is calculating covariance for a recent IPO, say, ANT
LedoitWolfCovariance::LedoitWolfCovariance(const Params&) {}

Matrix LedoitWolfCovariance::estimate(const MatrixRef& returns) const {
    require_panel(returns, 2);
    
    const auto t = static_cast<double> (returns.rows());
    const auto n = static_cast<double> (returns.cols());

    // Demeaned panel and its covariance, divided by T
    const Matrix X = returns.rowwise() - returns.colwise().mean();
    const Matrix S = (X.transpose() * X) / t;

    // Target F = mu * I, every asset gets the average variance, zero correlation
    const double mu = S.trace() / n;

    // delta: how far S is from F, ||S - mu I||^2 / N.
    const double S_norm2 = S.squaredNorm();
    const double delta = (S_norm2 - n * mu * mu) / n;

    // beta: noise in S, i.e. how much the daily snapshots x_t x_t' scatter
    // around S. Uses sklearn's identity instead of a loop over days.
    const Matrix x2 = X.array().square().matrix();
    const double beta = std::min(((x2.transpose() * x2).sum() / t - S_norm2) / (n * t), delta);

    // Shrinkage intensity in [0, 1]. delta == 0 means S already equals F.
    const double shrinkage = delta > 0.0 ? beta / delta : 0.0;

    // S* = shrinkage * mu I + (1 - shrinkage) * S, without building F.
    Matrix out = (1.0 - shrinkage) * S;
    out.diagonal().array() += shrinkage * mu;
    return out;
}

}  // namespace mra
