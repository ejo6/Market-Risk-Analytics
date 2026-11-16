from pathlib import Path

from mra.paths import LAKE_TABLES, DataPaths, data_dir


def test_data_dir_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MRA_DATA_DIR", str(tmp_path))
    assert data_dir() == tmp_path.resolve()


def test_data_dir_default(monkeypatch):
    monkeypatch.delenv("MRA_DATA_DIR", raising=False)
    assert data_dir() == Path("data").resolve()


def test_ensure_creates_layout(tmp_path):
    paths = DataPaths(tmp_path).ensure()
    for d in (paths.raw, paths.snapshots, paths.models):
        assert d.is_dir()
    for table in LAKE_TABLES:
        assert paths.lake_table(table).is_dir()


def test_raw_landing(tmp_path):
    p = DataPaths(tmp_path).raw_landing("tiingo", "daily", "20261116T000000Z")
    assert p == tmp_path / "raw" / "tiingo" / "daily" / "ingested_at=20261116T000000Z"


def test_core_extension():
    import mra._core as core

    assert core.version() == "0.1.0"
