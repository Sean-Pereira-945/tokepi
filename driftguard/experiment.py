"""Experiment entry points that run individual or complete benchmark suites."""

from __future__ import annotations

from typing import Any

from .benchmark import benchmark_report, run_benchmark_suite
from .data import build_demo_dataset


def run_experiment(length: int = 200, drift_start: int = 110, drift_magnitude: float = 3.5) -> dict[str, Any]:
    """Run a reproducible benchmark scenario for DriftGuard and baseline detectors."""
    samples = build_demo_dataset(length=length, drift_start=drift_start, drift_magnitude=drift_magnitude)
    report = benchmark_report(samples)
    return {
        "config": {
            "length": length,
            "drift_start": drift_start,
            "drift_magnitude": drift_magnitude,
        },
        "sample_count": len(samples),
        "summary": report,
    }


def run_experiment_suite() -> dict[str, Any]:
    """Run the published benchmark matrix across several realistic drift conditions."""
    results = run_benchmark_suite()
    scenarios = [entry["scenario"] for entry in results]
    return {
        "scenario_count": len(results),
        "scenarios": scenarios,
        "results": results,
    }
