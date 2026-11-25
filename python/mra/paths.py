"""Locations inside the data directory.

All storage lives under one root, set by the MRA_DATA_DIR environment variable.
Locally it defaults to ./data (gitignored); in docker compose it is a volume
mounted at /data. Code should never hard-code paths; go through DataPaths.

Layout:
    raw/<provider>/<dataset>/ingested_at=<ts>/<symbol>.csv   immutable landing
    lake/<table>/                                            Parquet, append-only
    snapshots/<hash>.json                                    dataset manifests
    models/<name>/<version>/                                 ONNX + metrics
    meta.sqlite                                              watermarks, runs, universe
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_VAR = "MRA_DATA_DIR"
DEFAULT_DIR = "data"

LAKE_TABLES = ("bars_daily", "macro", "factors")


def data_dir() -> Path:
    """Root of all stored data, from MRA_DATA_DIR or ./data."""
    return Path(os.environ.get(ENV_VAR, DEFAULT_DIR)).expanduser().resolve()


@dataclass(frozen=True)
class DataPaths:
    root: Path

    @classmethod
    def from_env(cls) -> DataPaths:
        return cls(data_dir())

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def lake(self) -> Path:
        return self.root / "lake"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def meta_db(self) -> Path:
        return self.root / "meta.sqlite"

    def raw_landing(self, provider: str, dataset: str, ingested_at: str) -> Path:
        """Directory for one immutable fetch. ingested_at is compact UTC, e.g. 20261116T000000Z (no colons, safe on every filesystem)."""
        return self.raw / provider / dataset / f"ingested_at={ingested_at}"

    def lake_table(self, table: str) -> Path:
        return self.lake / table

    def ensure(self) -> DataPaths:
        """Create the top-level layout. Safe to call repeatedly."""
        for d in (self.raw, self.snapshots, self.models):
            d.mkdir(parents=True, exist_ok=True)
        for table in LAKE_TABLES:
            self.lake_table(table).mkdir(parents=True, exist_ok=True)
        return self
