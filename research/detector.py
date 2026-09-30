"""Feature-distribution drift scoring utilities."""

from __future__ import annotations

from typing import Any

import numpy as np

FEATURE_NAMES = ["feature_a", "feature_b", "feature_c"]


def mean_abs_change(current: list[float], reference: list[float]) -> float:
    """Return the mean absolute difference from the reference mean."""
    current_arr = np.asarray(current, dtype=float)
    reference_arr = np.asarray(reference, dtype=float)
    if reference_arr.size == 0:
        return 0.0
    return float(np.mean(np.abs(current_arr - reference_arr.mean())))


def compute_drift_scores(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute a simple drift score based on distributional shift relative to early samples."""
    reference = [
        [sample["feature_a"], sample["feature_b"], sample["feature_c"]]
        for sample in samples[: max(1, len(samples) // 3)]
    ]
    reference_means = np.asarray(reference, dtype=float).mean(axis=0)

    latest_window = [
        [sample["feature_a"], sample["feature_b"], sample["feature_c"]]
        for sample in samples[-max(1, len(samples) // 3) :]
    ]
    latest_window_arr = np.asarray(latest_window, dtype=float)
    latest_means = latest_window_arr.mean(axis=0)

    per_feature_shift = np.abs(latest_means - reference_means)
    total_shift = float(per_feature_shift.mean())
    drift_score = min(1.0, max(0.0, total_shift / 2.0))

    feature_scores = {
        feat: float(abs(latest_means[idx] - reference_means[idx])) for idx, feat in enumerate(FEATURE_NAMES)
    }

    return {
        "drift_score": round(drift_score, 4),
        "severity": "critical" if drift_score > 0.7 else "warning" if drift_score > 0.35 else "stable",
        "feature_scores": feature_scores,
        "reference_means": reference_means.round(4).tolist(),
        "latest_means": latest_means.round(4).tolist(),
    }
