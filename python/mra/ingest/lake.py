from pathlib import Path
from mra.paths import DataPaths
from providers.base import FetchResult

def land_raw(paths: DataPaths, provider: str, dataset: str, run_timestamp: str, res: FetchResult) -> Path:
    dp = paths.raw_landing(provider, dataset, run_timestamp)
    dp.mkdir(parents=True, exist_ok=True)

    # Final output directory
    final = dp / f"{res.symbol}.{res.ext}"
    
    # .tmp until we're fully written (atomicity)
    tmp = final.with_suffix(final.suffix + ".tmp")
    tmp.write_bytes(res.payload)
    tmp.replace(final)