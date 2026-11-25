from typing import Literal, TypedDict

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.float64]

class ModelInfo(TypedDict):
    name: str
    description: str
    defaults: dict[str, float]
    status: Literal["ready", "stub"]
    source: str

class TailRisk:
    @property
    def var(self) -> float: ...
    @property
    def es(self) -> float: ...

class DrawdownStats:
    @property
    def max_drawdown(self) -> float: ...
    @property
    def peak(self) -> int: ...
    @property
    def trough(self) -> int: ...
    @property
    def longest_underwater(self) -> int: ...

def version() -> str:
    """Version of the C++ core library."""

def list_models(family: Literal["covariance", "tail_risk"]) -> list[ModelInfo]:
    """Models in a family, in registration order."""

def covariance(returns: Array, model: str = "sample", **params: float) -> Array:
    """N x N covariance of a T x N returns panel (rows = dates, oldest first)."""

def tail_risk(returns: Array, model: str = "historical", **params: float) -> TailRisk:
    """One-day VaR and ES of a return series, as positive loss fractions."""

def portfolio_volatility(weights: Array, cov: Array) -> float:
    """Daily portfolio volatility sqrt(w' S w)."""

def risk_contributions(weights: Array, cov: Array) -> Array:
    """Euler risk contributions; they sum to portfolio volatility."""

def drawdown_stats(returns: Array) -> DrawdownStats:
    """Max drawdown and time underwater of a daily return series."""
