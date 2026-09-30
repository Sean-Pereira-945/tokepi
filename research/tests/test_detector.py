import pytest

pytest.importorskip("numpy")

from research.data import build_demo_dataset, compute_baseline_summary
from research.detector import compute_drift_scores


def test_dataset_has_expected_shape():
    samples = build_demo_dataset(length=90, drift_start=45)
    assert len(samples) == 90
    assert all(
        set(sample.keys()) == {"timestamp", "feature_a", "feature_b", "feature_c", "label", "drift_zone"}
        for sample in samples
    )


def test_baseline_summary_outputs_expected_features():
    samples = build_demo_dataset(length=50)
    summary = compute_baseline_summary(samples)
    assert list(summary.keys()) == ["feature_means", "feature_stds"]
    assert len(summary["feature_means"]) == 3
    assert len(summary["feature_stds"]) == 3


def test_drift_scoring_returns_severity_and_features():
    samples = build_demo_dataset(length=100, drift_start=55, drift_magnitude=3.0)
    result = compute_drift_scores(samples)
    assert "drift_score" in result
    assert result["severity"] in {"stable", "warning", "critical"}
    assert set(result["feature_scores"].keys()) == {"feature_a", "feature_b", "feature_c"}
