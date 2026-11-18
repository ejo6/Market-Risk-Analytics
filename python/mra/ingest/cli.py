"""mra-ingest: pull daily prices for a list of symbols into the data directory.

    mra-ingest SPY QQQ TLT
    mra-ingest --symbols-file universe.txt --tier power
    mra-ingest SPY --data-dir /tmp/mra-scratch      # try it without touching ./data

Reads TIINGO_KEY (and MRA_DATA_DIR) from the environment or the repo's .env
Should be safe to rerun: each symbol resumes from its watermark (minus a 7-day overlap), and unchanged rows are never rewritten

Exit codes: 0 all symbols ingested, 1 some failed or the rate budget ran out, 2 bad usage/config
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from mra.ingest.meta import Meta
from mra.ingest.providers.base import PriceProvider
from mra.ingest.ratelimit import SlidingWindowLimiter
from mra.ingest.run import ingest_daily
from mra.paths import DataPaths

# (max_calls, window_seconds) per plan. Each invocation starts with a fresh limiter,
# so back-to-back invocations can exceed these, Tiingo's 429 then stops the run.
TIINGO_TIERS = {
    "free": [(50, 3600), (1000, 86400)],
    "power": [(10_000, 3600), (100_000, 86400)],
    "commercial": [(20_000, 3600), (150_000, 86400)],
}

BUDGET_MESSAGE = "rate budget exhausted"


def load_dotenv(path: Path) -> None:
    # Minimal .env reader: KEY=VALUE lines and # comments. Never overrides the real environment.
    
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def build_tiingo(args: argparse.Namespace) -> PriceProvider:
    from mra.ingest.providers.tiingo import TiingoProvider   # only import httpx when used

    key = os.environ.get("TIINGO_KEY")
    if not key:
        print("error: TIINGO_KEY is not set (add it to .env or export it)", file=sys.stderr)
        raise SystemExit(2)
    return TiingoProvider(key, SlidingWindowLimiter(TIINGO_TIERS[args.tier], max_wait=args.max_wait))


# Add new providers here: name -> function that builds it from the parsed arguments.
PROVIDERS: dict[str, Callable[[argparse.Namespace], PriceProvider]] = {"tiingo": build_tiingo}


def read_symbols(args: argparse.Namespace) -> list[str]:
    raw = list(args.symbols)
    if args.symbols_file:
        for line in Path(args.symbols_file).read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            raw.extend(s for s in line.replace(",", " ").split() if s)
    # Upper-case and drop duplicates, keeping the order given.
    return list(dict.fromkeys(s.upper() for s in raw))


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="mra-ingest",
        description="Pull daily prices for symbols into the local data lake.",
    )
    p.add_argument("symbols", nargs="*", metavar="SYMBOL", help="tickers, e.g. SPY QQQ TLT")
    p.add_argument("-f", "--symbols-file", help="file with tickers (whitespace/comma separated, # comments)")
    p.add_argument("--provider", choices=sorted(PROVIDERS), default="tiingo")
    p.add_argument("--tier", choices=sorted(TIINGO_TIERS), default="free", help="your Tiingo plan (rate limits)")
    p.add_argument("--max-wait", type=float, default=120,
                   help="longest to sleep for a rate-limit slot before stopping (seconds)")
    p.add_argument("--data-dir", help="override MRA_DATA_DIR for this run")
    p.add_argument("--env-file", default=".env", help="env file to read (default: ./.env)")
    args = p.parse_args(argv)
    if not args.symbols and not args.symbols_file:
        p.error("give at least one SYMBOL or --symbols-file")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(Path(args.env_file))

    symbols = read_symbols(args)
    provider = PROVIDERS[args.provider](args)   # fails fast on config errors, before touching disk
    paths = (DataPaths(Path(args.data_dir).expanduser().resolve()) if args.data_dir
             else DataPaths.from_env()).ensure()

    print(f"Ingesting {len(symbols)} symbol(s) from {provider.name} into {paths.root}")
    with Meta(paths.meta_db) as meta:
        run_id = ingest_daily(symbols, provider, paths, meta)
        run = meta.run(run_id)
        issues = meta.issues(run_id)
        marks = {s: meta.watermark(provider.name, "daily", s) for s in symbols}

    stopped_at = next((sym for sym, _, msg in issues if msg.startswith(BUDGET_MESSAGE)), None)

    print(f"\nRun {run_id}: {run['status']}  ({run['n_ok']} ok, {run['n_failed']} failed)")
    for sym in symbols:
        print(f"  {sym:<8} data through {marks[sym] or '-'}")
    if issues:
        print("\nIssues:")
        for sym, severity, msg in issues:
            print(f"  [{severity}] {sym}: {msg}")
    if stopped_at:
        print(f"\nStopped at {stopped_at}: out of rate-limit budget. Rerun later to continue.")

    return 1 if run["n_failed"] or stopped_at else 0


if __name__ == "__main__":
    sys.exit(main())
