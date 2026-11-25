"""Numerical parity: the C++ core must agree with numpy/scipy/sklearn.

Tests for stubs are marked `stub`: xfail while the C++ raises NotImplementedError,
and strict, so once you implement one the test XPASSes and the run fails until
you delete the marker. That deletion is your "done" signal.
"""

import numpy as np
import pytest

from mra import _core

stub = pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="C++ stub")


@pytest.fixture(scope="module")
def returns() -> np.ndarray:
    """750 days x 5 assets of fat-tailed (Student-t, df=4), correlated returns."""
    rng = np.random.default_rng(7)
    loadings = rng.normal(size=(5, 5)) * 0.004
    shocks = rng.standard_t(df=4, size=(750, 5))
    return shocks @ loadings.T + 0.0003


@pytest.fixture(scope="module")
def series(returns) -> np.ndarray:
    """An equal-weight portfolio's daily returns."""
    return returns @ np.full(returns.shape[1], 1 / returns.shape[1])


# -- Registry --


def test_list_models():
    names = [m["name"] for m in _core.list_models("covariance")]
    assert names == ["sample", "ewma", "ledoit_wolf"]
    ewma = next(m for m in _core.list_models("covariance") if m["name"] == "ewma")
    assert ewma["defaults"] == {"decay": 0.94}
    assert ewma["status"] == "ready"


def test_bad_inputs_raise_value_error(returns):
    with pytest.raises(ValueError, match="unknown model"):
        _core.covariance(returns, "nope")
    with pytest.raises(ValueError, match="no parameter 'decy'"):
        _core.covariance(returns, "ewma", decy=0.97)
    with pytest.raises(ValueError, match="unknown model family"):
        _core.list_models("nope")


# -- Covariance --


def test_sample_covariance_matches_numpy(returns):
    np.testing.assert_allclose(
        _core.covariance(returns, "sample"), np.cov(returns, rowvar=False), rtol=1e-12
    )


def test_memory_layout_does_not_matter(returns):
    c_order = np.ascontiguousarray(returns)
    f_order = np.asfortranarray(returns)
    np.testing.assert_array_equal(_core.covariance(c_order), _core.covariance(f_order))


def ewma_reference(r: np.ndarray, lam: float) -> np.ndarray:
    # Seed S_0 = 0, no demeaning (RiskMetrics). If you choose another seed in
    # C++, change it here too: this function IS the spec.
    s = np.zeros((r.shape[1], r.shape[1]))
    for row in r:
        s = lam * s + (1 - lam) * np.outer(row, row)
    return s



def test_ewma_matches_reference(returns):
    np.testing.assert_allclose(
        _core.covariance(returns, "ewma", decay=0.97),
        ewma_reference(returns, 0.97),
        rtol=1e-10,
    )


def test_ledoit_wolf_matches_sklearn(returns):
    sklearn_cov = pytest.importorskip("sklearn.covariance")
    expected = sklearn_cov.LedoitWolf().fit(returns).covariance_
    np.testing.assert_allclose(_core.covariance(returns, "ledoit_wolf"), expected, rtol=1e-10)


# -- Tail Risk --

@pytest.mark.parametrize("confidence", [0.95, 0.99, 0.999])
def test_historical_matches_numpy(series, confidence):
    q = np.quantile(series, 1 - confidence)  # numpy default: linear interpolation
    t = _core.tail_risk(series, "historical", confidence=confidence)
    assert t.var == pytest.approx(-q, rel=1e-12)
    assert t.es == pytest.approx(-series[series <= q].mean(), rel=1e-12)


@pytest.mark.parametrize("confidence", [0.95, 0.99])
def test_parametric_normal_matches_scipy(series, confidence):
    norm = pytest.importorskip("scipy.stats").norm
    mu, sigma = series.mean(), series.std(ddof=1)
    z = norm.ppf(1 - confidence)
    t = _core.tail_risk(series, "parametric_normal", confidence=confidence)
    assert t.var == pytest.approx(-(mu + sigma * z), rel=1e-8)
    assert t.es == pytest.approx(-(mu - sigma * norm.pdf(z) / (1 - confidence)), rel=1e-8)


# -- Portfolio --

def test_portfolio_volatility(returns):
    cov = np.cov(returns, rowvar=False)
    w = np.array([0.4, 0.3, 0.2, 0.2, -0.1])
    assert _core.portfolio_volatility(w, cov) == pytest.approx(np.sqrt(w @ cov @ w), rel=1e-12)


def test_risk_contributions(returns):
    cov = np.cov(returns, rowvar=False)
    w = np.array([0.4, 0.3, 0.2, 0.2, -0.1])
    sigma = np.sqrt(w @ cov @ w)
    np.testing.assert_allclose(_core.risk_contributions(w, cov), w * (cov @ w) / sigma, rtol=1e-12)


# -- Drawdown --


def test_drawdown_matches_numpy(series):
    wealth = np.cumprod(1 + series)
    peak = np.maximum.accumulate(np.concatenate([[1.0], wealth]))[1:]
    dd = 1 - wealth / peak
    d = _core.drawdown_stats(series)
    assert d.max_drawdown == pytest.approx(dd.max(), rel=1e-12)
    assert d.trough == int(dd.argmax())
