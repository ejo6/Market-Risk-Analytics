# mra-ingest command tests. Offline: a fake provider is swapped in for Tiingo

from datetime import date

import pyarrow as pa
import pytest

from mra.ingest import cli
from mra.ingest.providers.base import FetchResult
from mra.ingest.ratelimit import BudgetExhausted


class FakeProvider:
    name = "fake"

    def __init__(self, broke=()):
        self.broke = set(broke)

    def fetch_daily(self, symbol, start):
        if symbol in self.broke:
            raise BudgetExhausted("test")
        return FetchResult(symbol, b"{}", "json")

    def parse_daily(self, res):
        closes = [100.0, 101.0]
        return pa.table({
            "symbol": [res.symbol] * 2, "date": [date(2024, 1, 2), date(2024, 1, 3)],
            "open": closes, "high": [c + 1 for c in closes], "low": [c - 1 for c in closes],
            "close": closes, "volume": pa.array([1000] * 2, pa.int64()),
            "div_cash": [0.0] * 2, "split_factor": [1.0] * 2,
        })


@pytest.fixture
def fake(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setitem(cli.PROVIDERS, "tiingo", lambda args: provider)
    return provider


def run(tmp_path, *argv):
    return cli.main([*argv, "--data-dir", str(tmp_path), "--env-file", str(tmp_path / "none.env")])


def test_ingests_symbols_and_reports(tmp_path, fake, capsys):
    assert run(tmp_path, "spy", "qqq") == 0
    out = capsys.readouterr().out
    assert "ok  (2 ok, 0 failed)" in out
    assert "SPY      data through 2024-01-03" in out
    assert (tmp_path / "meta.sqlite").exists()
    assert list((tmp_path / "lake" / "bars_daily").rglob("*.parquet"))


def test_symbols_file_merges_and_dedupes(tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("SPY, qqq   # broad market\n\nTLT\nspy\n")
    args = cli.parse_args(["IWM", "-f", str(f)])
    assert cli.read_symbols(args) == ["IWM", "SPY", "QQQ", "TLT"]


def test_budget_exhausted_exits_1_and_says_so(tmp_path, fake, capsys):
    fake.broke = {"QQQ"}
    assert run(tmp_path, "SPY", "QQQ", "TLT") == 1
    out = capsys.readouterr().out
    assert "Stopped at QQQ" in out
    assert "TLT      data through -" in out


def test_no_symbols_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 2


def test_missing_key_is_a_clear_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TIINGO_KEY", raising=False)
    data = tmp_path / "data"
    with pytest.raises(SystemExit) as e:
        cli.main(["SPY", "--data-dir", str(data), "--env-file", str(tmp_path / "none.env")])
    assert e.value.code == 2
    assert "TIINGO_KEY is not set" in capsys.readouterr().err
    assert not data.exists()          # failed before creating anything


def test_dotenv_does_not_override_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nMRA_TEST_A=from_file\nMRA_TEST_B='quoted'\nMRA_TEST_EMPTY=\n")
    monkeypatch.setenv("MRA_TEST_A", "from_env")
    monkeypatch.delenv("MRA_TEST_B", raising=False)
    monkeypatch.delenv("MRA_TEST_EMPTY", raising=False)
    cli.load_dotenv(env)
    assert cli.os.environ["MRA_TEST_A"] == "from_env"
    assert cli.os.environ["MRA_TEST_B"] == "quoted"
    assert "MRA_TEST_EMPTY" not in cli.os.environ
    monkeypatch.delenv("MRA_TEST_B")
