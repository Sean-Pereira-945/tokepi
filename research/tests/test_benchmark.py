import pytest

pytest.importorskip("numpy")

from research.benchmark import benchmark_report, benchmark_scenarios, run_benchmark_suite
from research.data import build_demo_dataset


def test_benchmark_report_produces_scores_and_ranking():
    samples = build_demo_dataset(length=200, drift_start=110, drift_magnitude=3.5)
    report = benchmark_report(samples)

    assert set(report["detector_scores"].keys()) == {"mean_shift", "variance_shift", "driftguard"}
    assert isinstance(report["ranking"], list)
    assert report["winner"] in {"mean_shift", "variance_shift", "driftguard"}
    assert "summary" in report


def test_benchmark_scenarios_are_defined():
    scenarios = benchmark_scenarios()
    assert len(scenarios) >= 3
    assert all("name" in item for item in scenarios)


def test_benchmark_suite_runs_all_scenarios():
    results = run_benchmark_suite()
    assert len(results) == len(benchmark_scenarios())
    assert all("report" in item for item in results)
