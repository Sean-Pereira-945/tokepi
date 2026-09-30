"""Synthetic telemetry data models and generators used by demos and benchmarks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass
class DriftSample:
    """One synthetic observation with features and its known drift label."""

    timestamp: int
    feature_a: float
    feature_b: float
    feature_c: float
    label: int
    drift_zone: bool = False


def build_demo_dataset(length: int = 120, drift_start: int = 65, drift_magnitude: float = 2.5) -> list[dict[str, Any]]:
    """Create a synthetic drift dataset with a visible change in distribution after drift_start."""
    timestamps = list(range(length))
    stable_base = np.array([1.0, 0.5, 1.5], dtype=float)
    drift_delta = np.array([drift_magnitude, drift_magnitude * 0.7, -drift_magnitude * 0.5], dtype=float)
    samples: list[dict[str, Any]] = []

    for idx, ts in enumerate(timestamps):
        if idx < drift_start:
            feature_a = np.random.normal(stable_base[0], 0.25)
            feature_b = np.random.normal(stable_base[1], 0.2)
            feature_c = np.random.normal(stable_base[2], 0.3)
            label = 0
            drift_zone = False
        else:
            feature_a = np.random.normal(stable_base[0] + drift_delta[0], 0.35)
            feature_b = np.random.normal(stable_base[1] + drift_delta[1], 0.28)
            feature_c = np.random.normal(stable_base[2] + drift_delta[2], 0.32)
            label = 1
            drift_zone = True

        sample = DriftSample(
            timestamp=ts,
            feature_a=float(feature_a),
            feature_b=float(feature_b),
            feature_c=float(feature_c),
            label=int(label),
            drift_zone=bool(drift_zone),
        )
        samples.append(asdict(sample))

    return samples


def compute_baseline_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract baseline statistics from a stable reference slice."""
    feature_values = np.asarray(
        [[sample["feature_a"], sample["feature_b"], sample["feature_c"]] for sample in samples],
        dtype=float,
    )
    return {
        "feature_means": feature_values.mean(axis=0).round(4).tolist(),
        "feature_stds": feature_values.std(axis=0).round(4).tolist(),
    }
