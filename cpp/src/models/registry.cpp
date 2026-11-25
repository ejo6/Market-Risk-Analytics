#include "mra/models/registry.hpp"

#include <memory>
#include <string>

#include "mra/models/covariance.hpp"
#include "mra/models/tail_risk.hpp"

namespace mra {

namespace {

// Factory for a model class constructed from Params.
template <class Base, class Concrete>
typename Registry<Base>::Factory make() {
    return [](const Params& p) -> std::unique_ptr<Base> { return std::make_unique<Concrete>(p); };
}

}  // namespace

void register_builtin_models(ModelRegistry& r) {
    // covariance 
    r.covariance.add({"sample", "Unbiased sample covariance (T - 1), matches np.cov", {}},
                     make<CovarianceModel, SampleCovariance>());
    r.covariance.add({"ewma", "RiskMetrics exponentially weighted covariance",
                      {{"decay", 0.94}}},
                     make<CovarianceModel, EwmaCovariance>());
    r.covariance.add({"ledoit_wolf", "Ledoit-Wolf shrinkage toward scaled identity", {},},
                     make<CovarianceModel, LedoitWolfCovariance>());

    // tail risk 
    r.tail_risk.add({"historical", "Historical simulation VaR/ES", {{"confidence", 0.99}}},
                    make<TailRiskModel, HistoricalTailRisk>());
    r.tail_risk.add({"parametric_normal", "Gaussian (variance-covariance) VaR/ES",
                     {{"confidence", 0.99}}},
                    make<TailRiskModel, ParametricNormalTailRisk>());
}

const ModelRegistry& default_registry() {
    static const ModelRegistry registry = [] {
        ModelRegistry r;
        register_builtin_models(r);
        return r;
    }();
    return registry;
}

double param(const Params& p, std::string_view key) {
    auto it = p.find(key);
    if (it == p.end()) throw std::invalid_argument("missing parameter: " + std::string(key));
    return it->second;
}

}  // namespace mra
