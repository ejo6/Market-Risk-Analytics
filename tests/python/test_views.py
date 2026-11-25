from datetime import UTC, date, datetime

import duckdb
import pyarrow as pa
import pytest

from mra.ingest.lake import Lake
from mra.ingest.normalize import normalize
from mra.paths import DataPaths
from mra.views import register_views

T1 = datetime(2024, 1, 10, tzinfo=UTC)
T2 = datetime(2024, 1, 20, tzinfo=UTC)


def write(lake, rows, ingested_at, run_id):
    """rows: (day, close, div_cash, split_factor) for SPY in Jan 2024."""
    t = pa.table({
        "symbol": ["SPY"] * len(rows),
        "date": [date(2024, 1, d) for d, *_ in rows],
        "open": [c for _, c, *_ in rows], "high": [c for _, c, *_ in rows],
        "low": [c for _, c, *_ in rows], "close": [c for _, c, *_ in rows],
        "volume": pa.array([1000] * len(rows), pa.int64()),
        "div_cash": [dv for *_, dv, _ in rows], "split_factor": [s for *_, s in rows],
    })
    b = normalize(lake.conn, t, "tiingo", ingested_at)
    lake.write_lake("bars_daily", lake.only_changed("bars_daily", b, "SPY"), run_id)


@pytest.fixture
def lake(tmp_path):
    return Lake(DataPaths(tmp_path), duckdb.connect())


def rets(lake, as_of=None):
    register_views(lake.conn, lake.paths)
    q = "select date, ret from returns_daily(as_of := ?) order by date"
    return {d.day: r for d, r in lake.conn.execute(q, [as_of]).fetchall()}


def test_split_and_dividend_adjustment(lake):
    write(lake, [(2, 200.0, 0.0, 1.0), (3, 101.0, 0.0, 2.0), (4, 100.0, 1.0, 1.0)], T1, "r1")
    r = rets(lake)
    assert r[3] == pytest.approx(2 * 101 / 200 - 1)   # 2:1 split, not -49.5%
    assert r[4] == pytest.approx((100 + 1) / 101 - 1)  # dividend counts as return
    assert 2 not in r                                   # first bar has no return


def test_as_of_sees_old_version_and_corrected_dividend(lake):
    write(lake, [(2, 100.0, 0.0, 1.0), (3, 100.0, 1.0, 1.0)], T1, "r1")
    write(lake, [(2, 100.0, 0.0, 1.0), (3, 100.0, 0.0, 1.0)], T2, "r2")  # dividend withdrawn
    assert rets(lake, T1)[3] == pytest.approx(0.01)
    assert rets(lake)[3] == pytest.approx(0.0)
    assert lake.conn.execute("select count(*) from corporate_actions()").fetchone()[0] == 0


def test_register_on_empty_lake_says_what_to_do(lake):
    with pytest.raises(FileNotFoundError, match="mra-ingest"):
        register_views(lake.conn, lake.paths)