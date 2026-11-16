from dataclasses import dataclass
from datetime import date
from typing import Protocol
import pyarrow as pa

# DTO for results (immutable)
@dataclass(frozen=True)
class FetchResult:
    symbol: str    # ticker
    payload: bytes # raw response
    ext: str       # type of response suffixing file ("json" | "csv")

# Interface
class PriceProvider(Protocol):
    name: str

    def fetch_daily(self, symbol: str, start: date | None) -> FetchResult: ...
    def parse_daily(self, result: FetchResult) -> pa.Table: ...