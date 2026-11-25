# TiingoProvider tests. All offline: httpx's MockTransport stands in for the network.
# To pull real data, use the `mra-ingest` command instead (see python/mra/ingest/cli.py).

import json
from datetime import date

import httpx
import pyarrow as pa
import pytest

from mra.ingest.meta import Meta
from mra.ingest.providers.tiingo import RateLimited, TiingoProvider
from mra.ingest.ratelimit import SlidingWindowLimiter
from mra.ingest.run import ingest_daily
from mra.paths import DataPaths

# Same shape as Tiingo's /tiingo/daily/<ticker>/prices JSON. Values are made up.
ROWS = [
    {"date": "2024-03-14T00:00:00.000Z", "open": 514.0, "high": 516.0, "low": 510.0, "close": 513.0,
     "volume": 80_000_000, "adjOpen": 510.0, "adjHigh": 512.0, "adjLow": 506.0, "adjClose": 509.0,
     "adjVolume": 80_000_000, "divCash": 0.0, "splitFactor": 1.0},
    {"date": "2024-03-15T00:00:00.000Z", "open": 510.0, "high": 511.0, "low": 507.0, "close": 509.0,
     "volume": 120_000_000, "adjOpen": 506.0, "adjHigh": 507.0, "adjLow": 503.0, "adjClose": 505.0,
     "adjVolume": 120_000_000, "divCash": 1.6, "splitFactor": 1.0},
]
PAYLOAD = json.dumps(ROWS).encode()


class Recorder:
    """httpx transport that records requests and answers with a canned response."""

    def __init__(self, status=200, body=PAYLOAD):
        self.status, self.body, self.requests = status, body, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, content=self.body)


def make_provider(transport, key="test-key", limiter=None):
    limiter = limiter or SlidingWindowLimiter([(50, 3600), (1000, 86400)])
    provider = TiingoProvider(key, limiter)
    # Swap only the network layer; keep the client (and its headers) that TiingoProvider built.
    provider.client._transport = httpx.MockTransport(transport)
    return provider


# -- fetch_daily --

def test_sends_token_auth_header():
    rec = Recorder()
    make_provider(rec, key="abc123").fetch_daily("SPY", None)
    assert rec.requests[0].headers.get("Authorization") == "Token abc123"


def test_first_fetch_asks_for_full_history():
    # Omitting startDate makes Tiingo return only the latest bar, so it must always be sent.
    rec = Recorder()
    res = make_provider(rec).fetch_daily("SPY", None)
    req = rec.requests[0]
    assert req.url.path == "/tiingo/daily/SPY/prices"
    assert req.url.params.get("format") == "json"
    assert req.url.params.get("startDate") == "1900-01-01"
    assert (res.symbol, res.payload, res.ext) == ("SPY", PAYLOAD, "json")


def test_start_date_is_sent():
    rec = Recorder()
    make_provider(rec).fetch_daily("SPY", date(2024, 3, 1))
    assert rec.requests[0].url.params.get("startDate") == "2024-03-01"


def test_each_fetch_uses_one_rate_limit_slot():
    limiter = SlidingWindowLimiter([(50, 3600)])
    provider = make_provider(Recorder(), limiter=limiter)
    provider.fetch_daily("SPY", None)
    provider.fetch_daily("QQQ", None)
    assert len(limiter.calls) == 2


def test_429_raises_rate_limited():
    with pytest.raises(RateLimited):
        make_provider(Recorder(status=429, body=b"")).fetch_daily("SPY", None)


def test_unknown_ticker_raises_http_error():
    body = b'{"detail": "Error: Ticker \'NOPE\' not found"}'
    with pytest.raises(httpx.HTTPStatusError):
        make_provider(Recorder(status=404, body=body)).fetch_daily("NOPE", None)


# -- parse_daily --

def test_parse_columns_and_types():
    rec = Recorder()
    provider = make_provider(rec)
    t = provider.parse_daily(provider.fetch_daily("SPY", None))

    assert t.column_names == ["symbol", "date", "open", "high", "low", "close",
                              "volume", "div_cash", "split_factor"]          # adj* dropped
    assert t.schema.field("date").type == pa.date32()
    assert t.schema.field("volume").type == pa.int64()
    assert t.column("date").to_pylist() == [date(2024, 3, 14), date(2024, 3, 15)]
    assert t.column("div_cash").to_pylist() == [0.0, 1.6]
    assert set(t.column("symbol").to_pylist()) == {"SPY"}


def test_parse_empty_response():
    provider = make_provider(Recorder(body=b"[]"))
    assert provider.parse_daily(provider.fetch_daily("SPY", date(2030, 1, 1))).num_rows == 0


# -- through the whole pipeline, still offline --

def test_pipeline_with_tiingo_provider(tmp_path):
    paths = DataPaths(tmp_path)
    with Meta(paths.meta_db) as meta:
        run_id = ingest_daily(["SPY"], make_provider(Recorder()), paths, meta)
        assert meta.run(run_id)["status"] == "ok", meta.issues(run_id)
        assert meta.watermark("tiingo", "daily", "SPY") == "2024-03-15"

    assert (paths.raw_landing("tiingo", "daily", run_id) / "SPY.json").read_bytes() == PAYLOAD
    bars = pa.concat_tables(
        pa.parquet.read_table(f) for f in paths.lake_table("bars_daily").rglob("*.parquet")
    ).sort_by("date")
    assert bars.column("div_cash").to_pylist() == [0.0, 1.6]

