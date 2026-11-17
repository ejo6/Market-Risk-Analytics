# Data Ingestion
## Data Sourcing
The primary source of data for development is the Tiingo API (stock data is vendor specific, ticket metadata is always Tiingo API). Users bring thier own key and hit the endpoint.

### Tiingo
There are two types of call we'll make:

- 2.1.2 End-of-Day Endpoint (the actual data)
- 2.1.3 Meta Endpoint (metadata about a ticket)


**From Tiingo** Tiingo's End-of-Day prices use a proprietary error checking framework to help clean data feeds and also help catch missing corportate actions (splits, dividends, and exchange listing changes). Most US Equity prices are available at 5:30 PM EST, however exchanges may send corrections until 8 PM EST. As we obtain corrections, we update prices throughout the evening.

Mutual Fund NAVs are available after 12 AM EST. The fields "open", "high", "low", "close" will contain the NAV value for the given day.

We hit this enpoint to grab the following tuple response: `(date,open,high,low,close,volume,divCash,splitFactor)`. For all business days from 1993-2026 current day, a ticker loads around 600KB of data. Along with this, each ticker will have a metadata call.

## Overall data flow
A preliminary design choice was to not write this in C++, since most of the time is spend waiting on I/O (API endpoitns, as well as on-device I/O which is already well optimized in python). Future A/B testing for python vs. C++ will see if there is significant differences.

Will write this mermaid soon:

```
                 ┌-------------- meta.sqlite ---------------┐
                 | watermarks - ingest_runs - ingest_issues |
                 └------▲---------------------------▲-------┘
                  read  |                           | advance (LAST)
symbols -> 1 fetch -> 2 save raw file -> 3 parse -> 4 validate -> 5 normalize -> 6 write to lake
           (HTTP)     raw/…/*.json       Arrow     fail = set      bars +          Parquet,
                      never changed      table     aside           corporate       new or changed
                                                                   actions         rows only
```

## Ingestion Module
For now, the ingestion module will live in `python/mra/ingestion`.
```
python/mra/ingest/
    providers/base.py   # PriceProvider protocol
    providers/tiingo.py
    ratelimit.py
    validate.py         # check raw file before writing to lake
    normalize.py        # split basic EOD data, and EOD data with splits or dividends paid
    lake.py
    meta.py             # watermarks, runs, issues
    run.py              # the pipeline loop + CLI entry poin
```

Fetching and ingestion are kept seperate intentionally (especially inv development). Data transformations may be buggy/require change, so the files are written to disk beforehand to avoid repeat calls.  

### Providers
The base interface for dependency injection lives in `python/mra/ingest/providers/base.py`, and is defined as:
```python
# Interface for providers
class PriceProvider(Protocol):
    name: str

    def fetch_daily(self, symbol: str, start: date | None) -> FetchResult: ...
    def parse_daily(self, result: FetchResult) -> pa.Table: ...

# DTO for results (immutable)
@dataclass(frozen=True)
class FetchResult:
    symbol: str    
    payload: bytes
    ext: str       
```

### Ingestion Helpers
All located in `python/mra/ingest/`
- `lake.py`: writes raw response to correct datapath, preserves atomicity
- `ratelimit.py`: sliding window rate limiting algorithm for multiple rate limit types