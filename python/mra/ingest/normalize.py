def normalize(conn, table, source: str, ingested_at):
    """Shape a parsed provider table into lake rows for bars_daily

    div_cash and split_factor stay on the bar: they arrive on the same vendor row, 
    so they are versioned with it. A dividend later corrected to 0 is then just another changed row, picked up by Lake.only_changed.
    """
    conn.register("t", table)
    bars = conn.execute("""
        select symbol, date, open, high, low, close, volume, div_cash, split_factor,
               ? as source, ?::timestamptz as ingested_at, year(date) as year
        from t""", [source, ingested_at]).to_arrow_table()
    conn.unregister("t")
    return bars