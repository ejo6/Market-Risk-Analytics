#pragma once

// Model registry: name -> factory, one registry per model family.
//
// Only families with several interchangeable implementations get a registry
// (covariance estimators, tail-risk models, later volatility forecasters).
// Metrics with one correct definition (drawdown, portfolio volatility) are
// plain functions; see portfolio.hpp and drawdown.hpp.
//
// Registration is explicit (register_builtin_models in registry.cpp) rather
// than through static objects that register themselves. mra_core is a static
// library, and the linker drops object files nothing references, so
// self-registering models can silently disappear.
//
// Later, learned models (ONNX files under MRA_DATA_DIR/models/) register here
// too, with source = "onnx" and the dataset snapshot hash they were trained on.

#include <functional>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "mra/models/model.hpp"
#include "mra/types.hpp"

namespace mra {

enum class ModelStatus { Ready, Stub };

struct ModelInfo {
    std::string name;
    std::string description;
    Params defaults;  // every accepted parameter, with its default value
    ModelStatus status = ModelStatus::Ready;
    std::string source = "builtin";  // later: "onnx"
};

template <class Model>
class Registry {
public:
    using Factory = std::function<std::unique_ptr<Model>(const Params&)>;

    void add(ModelInfo info, Factory factory) {
        if (contains(info.name)) {
            throw std::invalid_argument("model already registered: " + info.name);
        }
        entries_.push_back({std::move(info), std::move(factory)});
    }

    [[nodiscard]] bool contains(std::string_view name) const { return find(name) != nullptr; }

    [[nodiscard]] const ModelInfo& info(std::string_view name) const { return require(name).info; }

    // Insertion order, so listings are stable.
    [[nodiscard]] std::vector<ModelInfo> list() const {
        std::vector<ModelInfo> out;
        out.reserve(entries_.size());
        for (const auto& e : entries_) out.push_back(e.info);
        return out;
    }

    // Builds a model. Overrides are merged over the defaults; an unknown key is
    // an error, so a typo like {"decy": 0.97} fails loudly instead of silently
    // running with the default.
    [[nodiscard]] std::unique_ptr<Model> create(std::string_view name,
                                                const Params& overrides = {}) const {
        const Entry& e = require(name);
        Params params = e.info.defaults;
        for (const auto& [key, value] : overrides) {
            auto it = params.find(key);
            if (it == params.end()) {
                throw std::invalid_argument("model '" + e.info.name + "' has no parameter '" +
                                            key + "'");
            }
            it->second = value;
        }
        return e.factory(params);
    }

private:
    struct Entry {
        ModelInfo info;
        Factory factory;
    };

    [[nodiscard]] const Entry* find(std::string_view name) const {
        for (const auto& e : entries_) {
            if (e.info.name == name) return &e;
        }
        return nullptr;
    }

    [[nodiscard]] const Entry& require(std::string_view name) const {
        if (const Entry* e = find(name)) return *e;
        throw std::invalid_argument("unknown model: '" + std::string(name) + "'");
    }

    std::vector<Entry> entries_;  // a handful of models: a linear scan beats a map
};

struct ModelRegistry {
    Registry<CovarianceModel> covariance;
    Registry<TailRiskModel> tail_risk;
};

// Adds the built-in models to a registry.
void register_builtin_models(ModelRegistry& registry);

// Process-wide registry holding the built-ins. Built on first use (thread-safe
// since C++11 "magic statics"), read-only afterwards.
const ModelRegistry& default_registry();

// Reads a parameter the registry has already validated and filled in.
double param(const Params& p, std::string_view key);

}  // namespace mra
