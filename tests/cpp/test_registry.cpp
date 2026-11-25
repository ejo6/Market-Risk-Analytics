#include <catch2/catch_test_macros.hpp>

#include "mra/models/registry.hpp"

using namespace mra;

TEST_CASE("built-in models are registered in a stable order", "[registry]") {
    const auto& r = default_registry();

    const auto cov = r.covariance.list();
    REQUIRE(cov.size() == 3);
    CHECK(cov[0].name == "sample");
    CHECK(cov[1].name == "ewma");
    CHECK(cov[2].name == "ledoit_wolf");

    CHECK(r.tail_risk.contains("historical"));
    CHECK(r.tail_risk.contains("parametric_normal"));
}

TEST_CASE("create merges overrides over defaults", "[registry]") {
    const auto& r = default_registry();
    CHECK(r.tail_risk.info("historical").defaults.at("confidence") == 0.99);
    CHECK_NOTHROW(r.tail_risk.create("historical", {{"confidence", 0.95}}));
}

TEST_CASE("bad names and parameters fail loudly", "[registry]") {
    const auto& r = default_registry();
    CHECK_THROWS_AS(r.covariance.create("nope"), std::invalid_argument);
    CHECK_THROWS_AS(r.covariance.create("ewma", {{"decy", 0.97}}), std::invalid_argument);
    CHECK_THROWS_AS(r.covariance.create("ewma", {{"decay", 1.5}}), std::invalid_argument);
    CHECK_THROWS_AS(r.tail_risk.create("historical", {{"confidence", 1.0}}), std::invalid_argument);
}

TEST_CASE("duplicate registration is rejected", "[registry]") {
    ModelRegistry r;
    register_builtin_models(r);
    CHECK_THROWS_AS(register_builtin_models(r), std::invalid_argument);
}
