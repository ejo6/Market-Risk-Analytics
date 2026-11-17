import duckdb, pyarrow as pa

# Hard failiures mean the data is not valid and is NOT written
HARD = {
    "duplicate dates":       "select count(*) - count(distinct date) from t",
    "high < low":            "select count(*) from t where high < low",
    "high < open/close":     "select count(*) from t where high < greatest(open, close)",
    "low > open/close":      "select count(*) from t where low > least(open, close)",
    "non-positive price":    "select count(*) from t where least(open, high, low, close) <= 0",
    "negative volume":       "select count(*) from t where volume < 0",
    "bad split factor":      "select count(*) from t where split_factor <= 0",
    "future date":           "select count(*) from t where date > current_date",
}

# Soft failiures mean data is valid with a recorded is, and IS written
SOFT = {
    # a 40%+ daily move with no split is usually a data error, not a market event
    "jump without split": """
        select count(*) from (
          select close / lag(close) over (order by date) as r, split_factor from t
        ) where split_factor = 1 and (r > 1.4 or r < 0.6)""",
}

def validate_bars(conn: duckdb.DuckDBPyConnection, table: pa.Table) -> tuple[list[str], list[str]]:
    # Bind our pyarrow tale into a SQL
    conn.register("t", table)
    def run(checks: dict[str][str]):
        results = []
        for name, query in checks.items():
            count = conn.execute(query).fetchone()[0]
            if count:  # skip checks that return 0 | None
                results.append(f"{name}: {count}")
        return results

    errors, warnings = run(HARD), run(SOFT)
    conn.unregister("t")
    return errors, warnings
