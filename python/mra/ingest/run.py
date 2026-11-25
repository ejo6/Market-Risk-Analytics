from datetime import UTC, date, datetime, timedelta

import duckdb

from mra.ingest.lake import Lake
from mra.ingest.normalize import normalize
from mra.ingest.ratelimit import BudgetExhausted
from mra.ingest.validate import validate_bars

# re-fetch the last week to catch vendor corrections
# common in Tiingo
OVERLAP = timedelta(days=7)

def ingest_daily(symbols, provider, paths, meta):
    now = datetime.now(UTC)
    run_ts = now.strftime("%Y%m%dT%H%M%SZ")
    meta.start_run(run_ts, provider.name, "daily")
    con = duckdb.connect()
    lake = Lake(paths, con)   # share one connection with validate/normalize
    ok = failed = 0

    for sym in symbols:
        try:
            wm = meta.watermark(provider.name, "daily", sym)   # ISO date text from SQLite, or None
            start = date.fromisoformat(wm) - OVERLAP if wm else None

            # 1
            res = provider.fetch_daily(sym, start)            
            # 2      
            lake.land_raw(provider.name, "daily", run_ts, res)
            # 3
            table = provider.parse_daily(res)
            if table.num_rows == 0:
                ok += 1; continue

            # 4
            errors, warnings = validate_bars(con, table)
            for w in warnings: meta.record_issue(run_ts, sym, "warn", w)
            if errors:
                for e in errors: meta.record_issue(run_ts, sym, "error", e)
                failed += 1; continue

            # 5
            bars = normalize(con, table, provider.name, now)
            # 6
            lake.write_lake("bars_daily", lake.only_changed("bars_daily", bars, sym), run_ts)

            last = max(table.column("date").to_pylist())
            # 7: ALWAYS LAST
            meta.advance_watermark(provider.name, "daily", sym, last, run_ts)
            ok += 1
        except BudgetExhausted:
            meta.record_issue(run_ts, sym, "info", "rate budget exhausted; resuming next run")
            break
        except Exception as e:
            meta.record_issue(run_ts, sym, "error", repr(e))
            failed += 1

    meta.finish_run(run_ts, "ok" if not failed else "partial", ok, failed)
    return run_ts