// Invariants every covariance model must satisfy. Exact values are checked
// against numpy/sklearn in tests/python/test_core_parity.py.
//
// Tests for a new stub model get the [.][todo] tags, which hide them by default.
// Run them with ./build/mra_tests "[todo]" and remove the tags once they pass.

#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>

#include <Eigen/Eigenvalues>

#include "mra/models/registry.hpp"

using namespace mra;
using Catch::Approx;

namespace {

// Small deterministic panel: 250 days x 4 assets with some correlation.
Matrix panel() {
    Matrix r(250, 4);
    for (Index t = 0; t < r.rows(); ++t) {
        const double x = std::sin(0.37 * static_cast<double>(t));
        const double y = std::cos(0.11 * static_cast<double>(t) + 1.0);
        r(t, 0) = 0.010 * x;
        r(t, 1) = 0.008 * x + 0.004 * y;
        r(t, 2) = 0.012 * y;
        r(t, 3) = 0.005 * std::sin(1.7 * static_cast<double>(t));
    }
    return r;
}

void check_invariants(const std::string& name) {
    const Matrix r = panel();
    const Matrix s = default_registry().covariance.create(name)->estimate(r);

    REQUIRE(s.rows() == r.cols());
    REQUIRE(s.cols() == r.cols());
    CHECK(s.isApprox(s.transpose()));  // symmetric

    // Positive semi-definite: no eigenvalue meaningfully below zero.
    Eigen::SelfAdjointEigenSolver<Matrix> eig(s);
    CHECK(eig.eigenvalues().minCoeff() > -1e-12);

    // Reordering assets must reorder the matrix, nothing else.
    Eigen::PermutationMatrix<Eigen::Dynamic> perm(r.cols());
    perm.indices() << 2, 0, 3, 1;
    const Matrix s_perm = default_registry().covariance.create(name)->estimate(r * perm);
    CHECK(s_perm.isApprox(perm.transpose() * s * perm));
}

}  // namespace

TEST_CASE("sample covariance invariants", "[covariance]") { check_invariants("sample"); }

TEST_CASE("sample covariance of a hand-sized example", "[covariance]") {
    Matrix r(3, 2);
    r << 0.01, 0.02,
         0.03, 0.00,
        -0.01, 0.04;
    const Matrix s = default_registry().covariance.create("sample")->estimate(r);
    // Column 0: mean 0.01, deviations (0, .02, -.02) -> var = .0008 / 2
    CHECK(s(0, 0) == Approx(0.0004));
    // Column 1: mean 0.02, deviations (0, -.02, .02) -> var = .0008 / 2
    CHECK(s(1, 1) == Approx(0.0004));
    // Perfectly opposite moves -> covariance = -variance
    CHECK(s(0, 1) == Approx(-0.0004));
}

TEST_CASE("sample covariance rejects too little data", "[covariance]") {
    const Matrix one_row = Matrix::Ones(1, 3);
    CHECK_THROWS_AS(default_registry().covariance.create("sample")->estimate(one_row),
                    std::invalid_argument);
}

TEST_CASE("ewma covariance invariants", "[covariance]") {
    const std::string name = "ewma";
    INFO("model: " << name);
    check_invariants(name);
}

TEST_CASE("ledoit_wolf covariance invariants", "[covariance]") {
    const std::string name = "ledoit_wolf";
    INFO("model: " << name);
    check_invariants(name);
}
