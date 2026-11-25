#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <stdexcept>

#include "mra/normal.hpp"

using namespace mra;
using Catch::Approx;

// Reference values from scipy.stats.norm.ppf.
TEST_CASE("inverse normal CDF hits known quantiles", "[normal]") {
    CHECK(inverse_normal_cdf(0.5) == Approx(0.0).margin(1e-15));
    CHECK(inverse_normal_cdf(0.95) == Approx(1.6448536269514722).epsilon(1e-12));   // upper tail region
    CHECK(inverse_normal_cdf(0.975) == Approx(1.959963984540054).epsilon(1e-12));
    CHECK(inverse_normal_cdf(0.01) == Approx(-2.326347874040841).epsilon(1e-12));   // lower tail region
    CHECK(inverse_normal_cdf(1e-10) == Approx(-6.361340902404056).epsilon(1e-12));  // deep tail
}

TEST_CASE("inverse normal CDF is symmetric and inverts the CDF", "[normal]") {
    CHECK(inverse_normal_cdf(0.3) == Approx(-inverse_normal_cdf(0.7)).epsilon(1e-14));
    for (double p : {1e-8, 0.001, 0.02425, 0.123, 0.5, 0.9, 0.99999}) {
        INFO("p = " << p);
        CHECK(normal_cdf(inverse_normal_cdf(p)) == Approx(p).epsilon(1e-13));
    }
}

TEST_CASE("inverse normal CDF rejects p outside (0, 1)", "[normal]") {
    CHECK_THROWS_AS(inverse_normal_cdf(0.0), std::invalid_argument);
    CHECK_THROWS_AS(inverse_normal_cdf(1.0), std::invalid_argument);
}
