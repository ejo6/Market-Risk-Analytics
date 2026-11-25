#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "mra/drawdown.hpp"
#include "mra/portfolio.hpp"

using namespace mra;
using Catch::Approx;

namespace {

// Two assets: 20% and 10% daily vol (absurd, but round), correlation 0.5.
Matrix cov2() {
    Matrix s(2, 2);
    s << 0.04, 0.01,
         0.01, 0.01;
    return s;
}

}  // namespace

TEST_CASE("portfolio volatility by hand", "[portfolio]") {
    Vector w(2);
    w << 0.5, 0.5;
    // w'Sw = .25*.04 + 2*.25*.01 + .25*.01 = .0175
    CHECK(portfolio_volatility(w, cov2()) == Approx(std::sqrt(0.0175)));
}

TEST_CASE("portfolio volatility rejects mismatched shapes", "[portfolio]") {
    Vector w(3);
    w << 1, 0, 0;
    CHECK_THROWS_AS(portfolio_volatility(w, cov2()), std::invalid_argument);
}

TEST_CASE("all-zero weights", "[portfolio]") {
    Vector w(2);
    w << 0.0, 0.0;
    const Vector rc = risk_contributions(w, cov2());
    CHECK(rc.isZero());
}

TEST_CASE("risk contributions sum to portfolio volatility", "[portfolio]") {
    Vector w(2);
    w << 0.5, 0.5;
    const Vector rc = risk_contributions(w, cov2());
    CHECK(rc.sum() == Approx(portfolio_volatility(w, cov2())));    // The riskier asset contributes more at equal weight
    CHECK(rc(0) > rc(1));
}

TEST_CASE("drawdown of a simple path", "[drawdown]") {
    // 1.0 -> 1.1 -> 0.88 -> 0.968 -> 1.1616
    Vector r(4);
    r << 0.10, -0.20, 0.10, 0.20;
    const DrawdownStats d = drawdown_stats(r);
    CHECK(d.max_drawdown == Approx(0.20));
    CHECK(d.peak == 0);
    CHECK(d.trough == 1);
}

TEST_CASE("drawdown of a series that only rises", "[drawdown]") {
    Vector r = Vector::Constant(10, 0.01);
    CHECK(drawdown_stats(r).max_drawdown == 0.0);
}
