# Analytics Core

The C++ library `mra_core` (`cpp/`) does the numerics: covariance, tail risk, portfolio risk, and drawdown. It is exposed to Python as `mra._core` through pybind11 (`bindings/module.cpp`).

## Boundary

```
DuckDB returns view -> Python (numpy T x N + symbol list) -> pybind11 -> mra_core (Eigen only)
```

The core has **no I/O**: Mainly done because I don't want to work with any C++ API libraries that could just be python. No DuckDB, no Parquet, no ticker symbols. It takes matrices and returns matrices, which keeps it fast to compile, easy to test, and identical whether Python, a CLI, or the API calls it. 

## Conventions

Every function and model follows these (see `cpp/include/mra/types.hpp`):

- A returns panel is **T x N**: rows are dates (oldest first), columns are assets.
- Returns are **simple daily total returns** from the lake's returns view.
- **No NaNs**: align symbols and drop gaps before calling the core.
- Risk figures (VaR, ES, drawdown) are **positive loss fractions**: `var = 0.023` is a 2.3% loss.
- Everything is **daily**; annualizing is the caller's choice.

## Model registry

Families with several interchangeable implementations get a registry (`cpp/include/mra/models/registry.hpp`). Each entry has a name, description, default parameters, and a source (`builtin` now, `onnx` later once models are trained).

| Family | Interface | Models |
|---|---|---|
| `covariance` | `CovarianceModel::estimate(T x N) -> N x N` | `sample`, `ewma`, `ledoit_wolf` |
| `tail_risk` | `TailRiskModel::estimate(T) -> {var, es}` | `historical`, `parametric_normal`|

Metrics with one correct definition are plain functions, not registered: `portfolio_volatility`, `risk_contributions`, `drawdown_stats`.

```python
from mra import _core
_core.list_models("covariance")
_core.covariance(returns, "ewma", decay=0.97)   # unknown params raise ValueError
_core.tail_risk(portfolio_returns, "historical", confidence=0.99)
```

Design choices:

- **Explicit registration** in `register_builtin_models()`. Static self-registering objects get dropped by the linker from a static library.
- **Immutable models**: configured at construction, `estimate()` is `const`, so one instance can be shared across threads.
- **Unknown parameters are errors**, so a typo never silently runs with the default.

## Models

**Covariance** (`T x N` returns -> `N x N` matrix)

- **`sample`**: equal weight on every day, divides by `T - 1`. Matches `np.cov`. The baseline.
- **`ewma`** (`decay`, default 0.94): RiskMetrics. Recent days weigh more, `S_t = λ S_{t-1} + (1 - λ) r_t r_t'`, so it reacts to volatility regimes. Seeded at zero and not demeaned; about 75 days hold 99% of the weight at 0.94.
- **`ledoit_wolf`**: blends the sample covariance with a target `μ I` (average variance, zero correlation). The blend weight is picked from the data: more noise means more shrinkage. Use it when `T` is small relative to `N` or the matrix feeds an optimizer. Matches sklearn, which divides by `T`.

**Tail risk** (daily return series -> `{var, es}`)

- **`historical`** (`confidence`, default 0.99): the empirical quantile of past returns (VaR) and the mean of the returns beyond it (ES). It makes no distribution assumption, but the tail holds only a few points, so it's noisy.
- **`parametric_normal`** (`confidence`, default 0.99): assumes returns are normal with the sample mean and std, so VaR and ES come from closed-form formulas. Stable, but thin-tailed: on fat-tailed data it understates 99%+ risk compared with `historical`.

**Plain functions**

- **`portfolio_volatility(w, S)`**: `σ_p = √(w' S w)`.
- **`risk_contributions(w, S)`**: Euler split of `σ_p` across assets, `RC_i = w_i (S w)_i / σ_p`. Sums to `σ_p`; negative for hedges; a zero vector when `σ_p = 0`.
- **`drawdown_stats(r)`**: worst peak-to-trough fall of compounded wealth, the peak and trough indices, and the longest stretch below a previous peak. One pass.
- **`normal_pdf` / `normal_cdf` / `inverse_normal_cdf`** (`mra/normal.hpp`, C++ only): standard normal helpers. The inverse uses Acklam plus one Halley step, accurate to about 1e-15.

## Adding a model

1. Declare the class in the family's header (`cpp/include/mra/models/`), with its formula, parameters, and **parity target**.
2. Implement it in `cpp/src/models/`.
3. Register it in `cpp/src/models/registry.cpp` with its defaults.
4. Add a parity test in `tests/python/test_core_parity.py` against numpy/scipy/sklearn, and make it pass the family's invariant tests in `tests/cpp/`.
