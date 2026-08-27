"""Synthetic benchmark metrics for comparing drift detectors."""

from __future__ import annotations

from typing import Any

import numpy as np

from .data import build_demo_dataset
from .detector import compute_drift_scores


FEATURE_NAMES = ["feature_a", "feature_b", "feature_c"]


def mean_shift_score(samples: list[dict[str, Any]]) -> float:
    """Estimate drift severity by comparing early and late feature means."""
    if len(samples) < 2:
        return 0.0
    split = max(2, len(samples) // 2)
    early = np.asarray([[s["feature_a"], s["feature_b"], s["feature_c"]] for s in samples[:split]], dtype=float)
    late = np.asarray([[s["feature_a"], s["feature_b"], s["feature_c"]] for s in samples[split:]], dtype=float)
    mean_shift = np.abs(late.mean(axis=0) - early.mean(axis=0))
    return float(mean_shift.mean())


def variance_shift_score(samples: list[dict[str, Any]]) -> float:
    """Estimate drift severity by comparing early and late feature variance."""
    if len(samples) < 2:
        return 0.0
    split = max(2, len(samples) // 2)
    early = np.asarray([[s["feature_a"], s["feature_b"], s["feature_c"]] for s in samples[:split]], dtype=float)
    late = np.asarray([[s["feature_a"], s["feature_b"], s["feature_c"]] for s in samples[split:]], dtype=float)
    variance_shift = np.abs(late.std(axis=0) - early.std(axis=0))
    return float(variance_shift.mean())


def benchmark_report(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a compact quantitative benchmark report for a drift dataset."""
    driftguard_score = compute_drift_scores(samples)["drift_score"]
    mean_shift = mean_shift_score(samples)
    variance_shift = variance_shift_score(samples)

    baselines = {
        "mean_shift": round(mean_shift, 4),
        "variance_shift": round(variance_shift, 4),
        "driftguard": round(driftguard_score, 4),
    }
    ranking = sorted(baselines.items(), key=lambda item: item[1], reverse=True)

    return {
        "detector_scores": baselines,
        "ranking": [name for name, _ in ranking],
        "winner": ranking[0][0] if ranking else None,
        "summary": {
            "largest_shift": max(baselines.values()),
            "smallest_shift": min(baselines.values()),
        },
    }


def benchmark_scenarios() -> list[dict[str, Any]]:
    """Return a small set of named drift scenarios for experiment comparison."""
    return [
        {"name": "light_drift", "length": 200, "drift_start": 120, "drift_magnitude": 0.5},
        {"name": "moderate_drift", "length": 200, "drift_start": 110, "drift_magnitude": 1.5},
        {"name": "strong_drift", "length": 200, "drift_start": 100, "drift_magnitude": 3.0},
    ]


def run_benchmark_suite() -> list[dict[str, Any]]:
    """Execute the drift benchmark scenarios and return a measurable scenario table."""
    results: list[dict[str, Any]] = []
    for scenario in benchmark_scenarios():
        samples = build_demo_dataset(
            length=scenario["length"],
            drift_start=scenario["drift_start"],
            drift_magnitude=scenario["drift_magnitude"],
        )
        suite_result = {
            "scenario": scenario["name"],
            "length": scenario["length"],
            "drift_start": scenario["drift_start"],
            "drift_magnitude": scenario["drift_magnitude"],
            "report": benchmark_report(samples),
        }
        results.append(suite_result)
    return results
