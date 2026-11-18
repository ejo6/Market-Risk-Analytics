import json
from datetime import date
import httpx
import pyarrow as pa
from mra.ingest.providers.base import FetchResult
from mra.ingest.ratelimit import SlidingWindowLimiter
from mra.ingest.ratelimit import BudgetExhausted

class RateLimited(BudgetExhausted): ...

# Note: don't need to explicity inherit from PriceProvider
class TiingoProvider:
    name = "tiingo"
    BASE = "https://api.tiingo.com/tiingo/daily"

    def __init__(self, api_key: str, limiter: SlidingWindowLimiter, client: httpx.Client | None = None):
        self.limiter = limiter
        self.client = client or httpx.Client(timeout=30, headers={"Authorization": f"Token {api_key}"})

    def fetch_daily(self, symbol: str, start: date | None) -> FetchResult:
        # Might want to switch to .csv later
        params = {"format": "json"}
        if start:
            params["startDate"] = start.isoformat()
        self.limiter.acquire()
        res = self.client.get(f"{self.BASE}/{symbol}/prices", params=params)

        if res.status_code == 429:
            raise RateLimited(symbol)
        res.raise_for_status()
        return FetchResult(symbol, res.content, "json")

    def parse_daily(self, res: FetchResult) -> pa.Table:
        rows = json.loads(res.payload)
        col = lambda k: [r[k] for r in rows]

        return pa.table({
            "symbol":[res.symbol] * len(rows),
            "date": [date.fromisoformat(r["date"][:10]) for r in rows],
            "open": col("open"),
            "high": col("high"),
            "low": col("low"),
            "close": col("close"),
            "volume": pa.array(col("volume"), pa.int64()),
            "div_cash": col("divCash"),
            "split_factor": col("splitFactor"),
        })

        
