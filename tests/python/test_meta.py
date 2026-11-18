from datetime import date

import pyarrow as pa
import pytest

from mra.ingest.meta import Meta
from mra.ingest.providers.base import FetchResult
from mra.ingest.ratelimit import BudgetExhausted
from mra.ingest.run import ingest_daily
from mra.paths import DataPaths


@pytest.fixture
def meta():
    with Meta(":memory:") as m:
        yield m


# -- Meta on its own --

def test_watermark_starts_empty(meta):
    assert meta.watermark("tiingo", "daily", "SPY") is None


def test_watermark_advances_and_never_moves_back(meta):
    meta.advance_watermark("tiingo", "daily", "SPY", date(2024, 1, 10), "r1")
    assert meta.watermark("tiingo", "daily", "SPY") == "2024-01-10"
    meta.advance_watermark("tiingo", "daily", "SPY", date(2024, 1, 5), "r2")   # older re-fetch
    assert meta.watermark("tiingo", "daily", "SPY") == "2024-01-10"


def test_run_lifecycle(meta):
    meta.start_run("r1", "tiingo", "daily")
    assert meta.run("r1")["status"] == "running"
    meta.finish_run("r1", "partial", 2, 1)
    run = meta.run("r1")
    assert (run["status"], run["n_ok"], run["n_failed"]) == ("partial", 2, 1)
    assert run["finished_at"] is not None


def test_meta_file_is_created(tmp_path):
    db = DataPaths(tmp_path).meta_db
    with Meta(db):
        pass
    assert db.exists()


# -- The whole pipeline with a fake provider (no network) --

class FakeProvider:
    """Stands in for Tiingo. Symbols in `bad` return high < low; `broke` raises BudgetExhausted."""
    name = "fake"

    def __init__(self, bad=(), broke=()):
        self.bad, self.broke = set(bad), set(broke)
        self.starts = {}

    def fetch_daily(self, symbol, start):
        if symbol in self.broke:
            raise BudgetExhausted("test")
        self.starts[symbol] = start
        return FetchResult(symbol, b"{}", "json")

    def parse_daily(self, res):
        closes = [100.0, 101.0, 102.0]
        high = [50.0] * 3 if res.symbol in self.bad else [c + 1 for c in closes]
        return pa.table({
            "symbol": [res.symbol] * 3,
            "date": [date(2024, 1, d) for d in (2, 3, 4)],
            "open": closes, "high": high, "low": [c - 1 for c in closes], "close": closes,
            "volume": pa.array([1000] * 3, pa.int64()),
            "div_cash": [0.0] * 3, "split_factor": [1.0] * 3,
        })


def test_pipeline_happy_path(tmp_path, meta):
    paths = DataPaths(tmp_path)
    run_id = ingest_daily(["SPY", "TLT"], FakeProvider(), paths, meta)

    assert meta.run(run_id)["status"] == "ok"
    assert meta.watermark("fake", "daily", "SPY") == "2024-01-04"
    assert (paths.raw_landing("fake", "daily", run_id) / "TLT.json").exists()
    assert list(paths.lake_table("bars_daily").rglob("*.parquet"))


def test_pipeline_uses_watermark_minus_overlap(tmp_path, meta):
    meta.advance_watermark("fake", "daily", "SPY", date(2024, 1, 10), "earlier")
    provider = FakeProvider()
    ingest_daily(["SPY"], provider, DataPaths(tmp_path), meta)
    assert provider.starts["SPY"] == date(2024, 1, 3)   # 10th minus 7 days


def test_invalid_symbol_is_set_aside(tmp_path, meta):
    run_id = ingest_daily(["SPY", "BAD"], FakeProvider(bad={"BAD"}), DataPaths(tmp_path), meta)

    run = meta.run(run_id)
    assert (run["status"], run["n_ok"], run["n_failed"]) == ("partial", 1, 1)
    assert meta.watermark("fake", "daily", "BAD") is None          # not advanced
    assert any(s == "BAD" and sev == "error" for s, sev, _ in meta.issues(run_id))


def test_budget_exhausted_stops_the_run(tmp_path, meta):
    run_id = ingest_daily(["SPY", "QQQ", "TLT"], FakeProvider(broke={"QQQ"}), DataPaths(tmp_path), meta)

    assert meta.watermark("fake", "daily", "SPY") == "2024-01-04"
    assert meta.watermark("fake", "daily", "TLT") is None          # never reached
    assert meta.issues(run_id) == [("QQQ", "info", "rate budget exhausted; resuming next run")]
