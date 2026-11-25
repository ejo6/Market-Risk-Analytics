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
           (HTTP)     raw/…/*.json       Arrow     fail = set      bars, incl.     Parquet,
                      never changed      table     aside           div_cash +      new or changed
                                                                   split_factor    rows only
```

## Ingestion Module
For now, the ingestion module will live in `python/mra/ingest`.
```
python/mra/ingest/
    providers/base.py   # PriceProvider protocol
    providers/tiingo.py 
    ratelimit.py        # sliding window rate limiter, takes args specific to data vendor
    validate.py         # check raw file before writing to lake 
    normalize.py        # shape parsed rows into bars_daily (raw prices + div_cash, split_factor)
    lake.py             # database access layer for the datalake
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
- `normalize.py`: shapes parsed rows into `bars_daily` rows. Dividends and splits stay on the bar (see [Lake Schema](#lake-schema))
- `meta.py`: metadata about previous pulls
- `validate.py`: validate the data


### CLI Data Fetch
In lieu of a proper UI during development, `python/mra/ingest/cli.py` allows for pulling data:

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/mra-ingest SPY QQQ TLT # ingests SPY, QQQ, TLT symbol data, default first date
```

## Lake Schema
### `bars_daily`
One table, partitioned by `year`, append-only. Prices are stored **raw** (as traded, unadjusted):

| column | notes |
| --- | --- |
| `symbol`, `date` | logical key |
| `open`, `high`, `low`, `close`, `volume` | raw, unadjusted |
| `div_cash` | cash dividend per share on the ex-date, `0.0` otherwise |
| `split_factor` | e.g. `2.0` on the ex-date of a 2:1 split, `1.0` otherwise |
| `source`, `ingested_at` | provider, and when this version of the row was written |

Rows are versioned, never overwritten: when a vendor corrects a bar (any of the price, volume, dividend or split columns), `Lake.only_changed` appends a new row with a newer `ingested_at`. The latest version as of a given time is what readers see.

Dividends and splits used to live in a separate `corporate_actions` table that only held non-zero rows. That meant a dividend later corrected to `0` was filtered out before it reached the lake, and the wrong dividend stayed forever. Keeping them on the bar means they are versioned with it, so a correction is just another changed row.

### Views (`python/mra/views.py`)
Nothing derived is stored. Views are DuckDB table macros, registered per connection with `register_views(conn, paths)`, and every one takes an optional `as_of` timestamp (`NULL` = latest):

| view | returns |
| --- | --- |
| `bars_asof(as_of)` | latest version of each `(symbol, date)` ingested at or before `as_of`. Every other view builds on it |
| `corporate_actions(as_of)` | rows with a dividend or split, i.e. the old table |
| `returns_daily(as_of)` | daily simple returns per symbol, adjusted for splits and dividends |

```python
conn = duckdb.connect()
register_views(conn, DataPaths.from_env())
conn.sql("select * from returns_daily() where symbol in ('SPY', 'TLT')")
conn.sql("select * from returns_daily(as_of := '2026-11-18'::timestamptz)")  # point in time
```

Returns are computed from two consecutive bars, so they never need rewriting when new data arrives:

```
ret       = split_factor * (close + div_cash) / prev_close - 1    total return (default for risk)
ret_price = split_factor * close / prev_close - 1                 price-only return
gap_days  = date - prev_date                                      3 on Mondays, longer for market closures
```

Each symbol's first bar has no return and is dropped. `returns_daily` matches returns computed from Tiingo's own `adjClose` to ~1e-12.

**Why compute on read, and why not C++:** DuckDB is already a vectorized C++ engine, and the cost is dominated by reading Parquet, not the arithmetic. On a synthetic lake of 5,000 symbols x 31 years (41.5M rows), the full universe took 1.3 s and a 20-symbol portfolio 0.03 s. If the C++ core later needs returns itself, it can run the same SQL through DuckDB's C++ API, so there is still one implementation.