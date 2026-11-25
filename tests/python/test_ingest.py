from datetime import UTC, date, datetime

import duckdb
import pyarrow as pa
import pytest

from mra.ingest.lake import Lake
from mra.ingest.normalize import normalize
from mra.ingest.providers.base import FetchResult
from mra.ingest.ratelimit import BudgetExhausted, SlidingWindowLimiter
from mra.ingest.validate import validate_bars
from mra.paths import DataPaths


def bars(closes, start_day=1, symbol="SPY", divs=None):
    """Small parsed-provider table: one row per close, flat OHLC around it."""
    n = len(closes)
    divs = divs or [0.0] * n
    return pa.table({
        "symbol": [symbol] * n,
        "date": [date(2024, 1, start_day + i) for i in range(n)],
        "open": closes, "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes], "close": closes,
        "volume": pa.array([1000] * n, pa.int64()),
        "div_cash": divs, "split_factor": [1.0] * n,
    })


def test_dividend_corrected_to_zero_is_written(tmp_path):
    lake = Lake(DataPaths(tmp_path))
    assert ingest(lake, bars([100.0, 101.0], divs=[0.0, 1.5]), "r1") == 2
    assert ingest(lake, bars([100.0, 101.0], divs=[0.0, 0.0]), "r2") == 1  # correction to 0

# -- Rate Limiter --

def test_acquire_takes_exactly_one_slot():
    lim = SlidingWindowLimiter([(50, 3600)])
    lim.acquire()
    assert len(lim.calls) == 1


def test_acquire_raises_when_budget_spent():
    lim = SlidingWindowLimiter([(3, 3600)], max_wait=1)
    for _ in range(3):
        lim.acquire()
    with pytest.raises(BudgetExhausted):
        lim.acquire()


# -- Validation -- 

def test_clean_bars_pass():
    assert validate_bars(duckdb.connect(), bars([100.0, 101.0, 102.0])) == ([], [])


def test_bad_bars_fail():
    t = bars([100.0, 101.0]).set_column(3, "high", pa.array([50.0, 50.0]))  # high < low
    errors, _ = validate_bars(duckdb.connect(), t)
    assert any(e.startswith("high < low") for e in errors)


def test_jump_without_split_is_a_warning():
    errors, warnings = validate_bars(duckdb.connect(), bars([100.0, 200.0]))
    assert errors == [] and warnings == ["jump without split: 1"]


# -- Lake -- 

def test_land_raw_is_written_and_returned(tmp_path):
    lake = Lake(DataPaths(tmp_path))
    p = lake.land_raw("tiingo", "daily", "20240101T000000Z", FetchResult("SPY", b"[]", "json"))
    assert p.read_bytes() == b"[]"
    assert not list(p.parent.glob("*.tmp"))


def ingest(lake, table, run_id):
    b = normalize(lake.conn, table, "tiingo", datetime.now(UTC))    
    changed = lake.only_changed("bars_daily", b, "SPY")
    lake.write_lake("bars_daily", changed, run_id)
    return changed.num_rows


def test_rerun_writes_nothing_and_corrections_write_one_row(tmp_path):
    lake = Lake(DataPaths(tmp_path))
    assert ingest(lake, bars([100.0, 101.0, 102.0]), "r1") == 3
    assert ingest(lake, bars([100.0, 101.0, 102.0]), "r2") == 0 # idempotent
    assert ingest(lake, bars([100.0, 101.0, 102.5]), "r3") == 1 # vendor correction
