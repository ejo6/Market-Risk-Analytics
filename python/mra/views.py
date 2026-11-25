"""Derived, read only views over the lake. Nothing here writes data.

Views are DuckDB table macros registered per connection, so the logic lives in
one SQL definition that Python (and later the C++ core) runs as is.
"""


from __future__ import annotations

import duckdb

from mra.paths import DataPaths

# Latest version of each (symbol, date) bar ingested at or before `as_of`
# (NULL = latest). Every other view builds on this one.
BARS_ASOF = """
create or replace macro bars_asof(as_of := null) as table
select *
from read_parquet('{bars}', hive_partitioning = true)
where as_of is null or ingested_at <= as_of
qualify row_number() over (partition by symbol, date order by ingested_at desc) = 1
"""

# Dividends and splits only: what used to be the corporate_actions table.
CORPORATE_ACTIONS = """
create or replace macro corporate_actions(as_of := null) as table
select symbol, date, div_cash, split_factor
from bars_asof(as_of := as_of)
where div_cash <> 0 or split_factor <> 1
"""

# Daily simple returns, adjusted for splits and dividends.
#   ret       = split * (close + div) / prev_close - 1   total return
#   ret_price = split * close / prev_close - 1           price-only return
# Matches Tiingo's adjClose-based returns to ~1e-12.
RETURNS_DAILY = """
create or replace macro returns_daily(as_of := null) as table
with b as (
    select symbol, date, close, div_cash, split_factor,
           lag(close) over w as prev_close,
           lag(date)  over w as prev_date
    from bars_asof(as_of := as_of)
    window w as (partition by symbol order by date)
)
select symbol, date,
       split_factor * (close + div_cash) / prev_close - 1 as ret,
       split_factor * close / prev_close - 1              as ret_price,
       date - prev_date                                   as gap_days
from b
where prev_close is not null
"""


def register_views(conn: duckdb.DuckDBPyConnection, paths: DataPaths) -> None:
    """Define the lake's views on this connection. Safe to call repeatedly.

    DuckDB checks the glob when a macro is created, so the lake needs at least
    one bars file. Files written later are still picked up: the glob is
    expanded again on every query.
    """
    table = paths.lake_table("bars_daily")
    if not any(table.rglob("*.parquet")):
        raise FileNotFoundError(f"no bars in {table}; run mra-ingest first")
    # Escape quotes: the path is spliced into a SQL string literal.
    bars = str(table / "**" / "*.parquet").replace("'", "''")
    conn.execute(BARS_ASOF.format(bars=bars))  # must come first: the others call it
    conn.execute(CORPORATE_ACTIONS)
    conn.execute(RETURNS_DAILY)