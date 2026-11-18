from pathlib import Path
from uuid import uuid4
from mra.paths import DataPaths
from mra.ingest.providers.base import FetchResult
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb

class Lake:
    # Writing only new or changed rows
    KEY = {"bars_daily": ["open", "high", "low", "close", "volume"],
        "corporate_actions": ["div_cash", "split_factor"]}

    def __init__(self, paths: DataPaths, conn: duckdb.DuckDBPyConnection | None = None):
        self.paths = paths
        self.conn = conn or duckdb.connect()


    def land_raw(self, provider: str, dataset: str, run_timestamp: str, res: FetchResult) -> Path:
        dp = self.paths.raw_landing(provider, dataset, run_timestamp)
        dp.mkdir(parents=True, exist_ok=True)

        # Final output directory
        final = dp / f"{res.symbol}.{res.ext}"
        
        # .tmp until we're fully written (atomicity)
        tmp = final.with_suffix(final.suffix + ".tmp")
        tmp.write_bytes(res.payload)
        tmp.replace(final)
        return final


    def only_changed(self, table_name: str, new, symbol: str):
        files = list(self.paths.lake_table(table_name).rglob("*.parquet"))

        if not files:
            return new

        self.conn.register("n", new)
        diff = " or ".join(f"n.{c} is distinct from cur.{c}" for c in self.KEY[table_name])

        out = self.conn.execute(f"""
            with cur as (
            select * from read_parquet(?, hive_partitioning = true)
            where symbol = ?
            qualify row_number() over (partition by symbol, date order by ingested_at desc) = 1
            )
            select n.* from n left join cur using (symbol, date)
            where cur.symbol is null or {diff}""",
            [[str(f) for f in files], symbol]).to_arrow_table()
        self.conn.unregister("n")
        return out


    def write_lake(self, table_name: str, t: pa.Table, run_id: str) -> None:
        if t.num_rows == 0:
            return
        pq.write_to_dataset(
            t, 
            root_path=self.paths.lake_table(table_name), partition_cols=["year"],
            # Unique per write: every symbol in a run writes to the same year folders, and:
            # "overwrite_or_ignore" would let a later symbol replace an earlier one's file.
            basename_template=f"part-{run_id}-{uuid4().hex[:12]}-{{i}}.parquet",
            existing_data_behavior="overwrite_or_ignore",
        )
