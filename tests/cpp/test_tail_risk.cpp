#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>

#include "mra/models/registry.hpp"

using namespace mra;
using Catch::Approx;

namespace {

// -0.50, -0.49, ..., 0.49: 100 evenly spaced returns, easy to reason about.
Vector ladder() {
    Vector r(100);
    for (Index i = 0; i < r.size(); ++i) r(i) = -0.50 + 0.01 * static_cast<double>(i);
    return r;
}

TailRisk run(const std::string& model, const Vector& r, double confidence) {
    return default_registry().tail_risk.create(model, {{"confidence", confidence}})->estimate(r);
}

}  // namespace

TEST_CASE("historical VaR/ES on an evenly spaced series", "[tail_risk]") {
    // 95%: quantile at h = 99 * 0.05 = 4.95 -> between -0.46 and -0.45
    const TailRisk t = run("historical", ladder(), 0.95);
    CHECK(t.var == Approx(0.4505));
    // Tail = the 5 returns <= -0.4505: -0.50 ... -0.46, mean -0.48
    CHECK(t.es == Approx(0.48));
}

TEST_CASE("historical result does not depend on input order", "[tail_risk]") {
    const Vector r = ladder();
    const Vector reversed = r.reverse();
    const TailRisk a = run("historical", r, 0.99);
    const TailRisk b = run("historical", reversed, 0.99);
    CHECK(a.var == b.var);
    CHECK(a.es == b.es);
}

TEST_CASE("tail risk ordering: es >= var, higher confidence is riskier", "[tail_risk]") {
    const TailRisk t95 = run("historical", ladder(), 0.95);
    const TailRisk t99 = run("historical", ladder(), 0.99);
    CHECK(t95.es >= t95.var);
    CHECK(t99.var >= t95.var);
    CHECK(t99.es >= t95.es);
}

TEST_CASE("parametric normal ordering: es >= var, higher confidence is riskier", "[tail_risk]") {
    const std::string name = "parametric_normal";
    const TailRisk t95 = run(name, ladder(), 0.95);
    const TailRisk t99 = run(name, ladder(), 0.99);
    CHECK(t95.es >= t95.var);
    CHECK(t99.var >= t95.var);
}
