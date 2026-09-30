# DriftGuard research prototypes

This folder holds the Phase 1 research code: a synthetic feature-drift model and
the benchmark used to compare it against simple statistical baselines. It is
kept for reference and reproducibility. The `driftguard` product package does
not import anything from here.

| Module | Purpose |
| --- | --- |
| `data.py` | Generates synthetic three-feature datasets with a known drift onset. |
| `detector.py` | Mean-shift drift score with per-feature attribution. |
| `benchmark.py` | Compares the detector against mean-shift and variance-shift baselines. |
| `experiment.py` | Runs single scenarios or the full benchmark matrix. |
| `reporting.py` | Formats results as a Markdown table and a research summary. |
| `demo_api.py` | Tiny FastAPI app exposing `/dataset` and `/drift` for demos. |

## Running

```bash
pip install -e ".[research,dev]"
pytest research/tests
python -c "from research.experiment import run_experiment_suite; from research.reporting import format_benchmark_markdown; print(format_benchmark_markdown(run_experiment_suite()['results']))"
uvicorn research.demo_api:app --port 8001
```

The datasets are random, so scores vary between runs.
