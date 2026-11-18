import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Meta:
    # Ingest bookkeeping in meta.sqlite: runs, per-symbol watermarks, and issues

    # Every write commits immediately. That matters most for advance_watermark:
    #   once it returns, a crash wont lose it, and a crash before it means the symbol is just redone next run

    SCHEMA = """
    create table if not exists ingest_runs(
        run_id text primary key, provider text, dataset text,
        started_at text, finished_at text, status text, n_ok int, n_failed int);
    create table if not exists watermarks(
        provider text, dataset text, symbol text, last_date text, last_ingested_at text,
        primary key (provider, dataset, symbol));
    create table if not exists ingest_issues(
        run_id text, symbol text, severity text, message text);
    """

    def __init__(self, db_path: Path | str):
        """db_path is usually DataPaths.meta_db; ":memory:" works for tests."""
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(self.SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Meta":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # Runs

    def start_run(self, run_id: str, provider: str, dataset: str) -> None:
        # Status stays "running" if the process dies, which is how you spot a crashed run
        with self.conn:
            self.conn.execute(
                "insert into ingest_runs (run_id, provider, dataset, started_at, status) "
                "values (?, ?, ?, ?, 'running')",
                (run_id, provider, dataset, _now()),
            )

    def finish_run(self, run_id: str, status: str, n_ok: int, n_failed: int) -> None:
        with self.conn:
            self.conn.execute(
                "update ingest_runs set finished_at = ?, status = ?, n_ok = ?, n_failed = ? "
                "where run_id = ?",
                (_now(), status, n_ok, n_failed, run_id),
            )

    # Watermarks

    def watermark(self, provider: str, dataset: str, symbol: str) -> str | None:
        """Last fetched date as ISO text (YYYY-MM-DD), or None if never fetched."""
        row = self.conn.execute(
            "select last_date from watermarks where provider = ? and dataset = ? and symbol = ?",
            (provider, dataset, symbol),
        ).fetchone()
        return row[0] if row else None

    def advance_watermark(self, provider: str, dataset: str, symbol: str, last_date: date, ingested_at: str) -> None:
        # max(): a refetch of an older window must never move the watermark backwards
        # ISO dates sort correctly as text, so SQLite's max() works on them
        with self.conn:
            self.conn.execute(
                """
                insert into watermarks (provider, dataset, symbol, last_date, last_ingested_at)
                values (?, ?, ?, ?, ?)
                on conflict (provider, dataset, symbol) do update set
                    last_date = max(excluded.last_date, watermarks.last_date),
                    last_ingested_at = excluded.last_ingested_at
                """,
                (provider, dataset, symbol, last_date.isoformat(), ingested_at),
            )

    # Issues

    def record_issue(self, run_id: str, symbol: str, severity: str, message: str) -> None:
        with self.conn:
            self.conn.execute(
                "insert into ingest_issues (run_id, symbol, severity, message) values (?, ?, ?, ?)",
                (run_id, symbol, severity, message),
            )

    def issues(self, run_id: str) -> list[tuple[str, str, str]]:
        """(symbol, severity, message) for one run, in the order they were recorded."""
        return self.conn.execute(
            "select symbol, severity, message from ingest_issues where run_id = ? order by rowid",
            (run_id,),
        ).fetchall()

    def run(self, run_id: str) -> dict | None:
        cur = self.conn.execute("select * from ingest_runs where run_id = ?", (run_id,))
        row = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row)) if row else None
