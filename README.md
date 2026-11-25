# Market Risk Analytics (`mra`)

**Motivation:** I consider myself a bit too financially risk-adverse sometimes. So I wanted to build a portfolio risk analytics applicationto give me some peace of mind

A self hosted platform for market risk and portfolio analytics. It pulls EOD market data into a local, versioned Parquet lake, runs analytics in a C++ core, and exposes that core to Python through pybind11.

**Bring your own keys:** the project ships the pipeline, not the data. You supply your own provider API key (Tiingo to start) and build your own dataset locally.

> Status: early development. The build, Python bindings, and data-directory layout are in place; ingestion and analytics are in progress.

## Layout

- `cpp/include/mra/`: C++ headers for the analytics core
- `cpp/src/`: C++ sources
- `bindings/`: pybind11 module (mra._core)
- `python/mra/`: Python package
- `tests/python/`: Python tests (pytest)
- `tests/cpp/`: C++ tests
- `docs/`: Design documents


## Branching
- `main`: Self explanatory, main branch
- `develop`: Main develop branch, features in test go here (probably the most up to date version)
- `data/*`: All data ingestion and pipleine development
- `inference/*`: All model training
- `feature/*`: All other feature branches

## Requirements

- Python 3.10+
- CMake 3.20+
- A C++20 compiler (Clang or GCC)

Python build dependencies (scikit-build-core, pybind11) are installed automatically by `pip`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create your environment file and add your API key:

```bash
cp .env.example .env
```

| Variable       | Purpose                                                        |
| -------------- | -------------------------------------------------------------- |
| `TIINGO_KEY`   | Your Tiingo API key                                            |
| `MRA_DATA_DIR` | Where all data is stored (default `./data`, gitignored)        |

## Running tests

Python tests, including the C++/numpy parity tests (rebuild the extension first if you changed C++):

```bash
pip install -e ".[dev]"
pytest
```

C++ tests (Catch2), built separately from the Python package:

```bash
cmake -S . -B build -DMRA_BUILD_TESTS=ON -DMRA_BUILD_PYTHON=OFF -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j
./build/mra_tests            # tests for unfinished stubs are tagged [todo] and hidden; run with "[todo]"
```

## Data storage

All data lives under `MRA_DATA_DIR`, never in the repo:

- `raw/`: Vendor responses exactly as fetched (never modified)
- `lake/`: Parquet tables (bars_daily, macro, factors). Derived data such as adjusted returns is computed on read by the views in `python/mra/views.py`
- `snapshots/`: Dataset manifests that tie each model to an exact dataset
- `models/`: Trained models (ONNX) and their metrics
- `meta.sqlite`: Ingest watermarks, job runs, universe definitions

See `python/mra/paths.py` for the code that defines this layout.

## Documentation

- [High-level design](docs/high-level-design.md): architecture, components, and build order
- [Data ingestion](docs/data-ingestion.md): pipeline, lake schema, and the returns views
- [Analytics core](docs/analytics-core.md): conventions, model registry, and how to add a model

