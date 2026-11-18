def normalize(conn, table, source: str, ingested_at):
    conn.register("t", table)

    # Our basic data
    data = conn.execute("""
        select symbol, date, open, high, low, close, volume,
               ? as source, ?::timestamptz as ingested_at, year(date) as year
        from t""", [source, ingested_at]).to_arrow_table()
    
    # Actions like splits, or dividends paid
    actions = conn.execute("""
        select symbol, date, div_cash, split_factor,
               ? as source, ?::timestamptz as ingested_at, year(date) as year
        from t where div_cash <> 0 or split_factor <> 1""", [source, ingested_at]).to_arrow_table()
    conn.unregister("t")
    return data, actions