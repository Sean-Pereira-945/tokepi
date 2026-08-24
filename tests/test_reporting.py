from driftguard.experiment import run_experiment_suite
from driftguard.reporting import build_research_summary, format_benchmark_markdown


def test_format_benchmark_markdown_contains_expected_columns():
    results = run_experiment_suite()["results"]
    markdown = format_benchmark_markdown(results)

    assert "| Scenario | Drift Start | Drift Magnitude | Mean Shift | Variance Shift | DriftGuard | Winner |" in markdown
    assert "light_drift" in markdown
    assert "strong_drift" in markdown


def test_build_research_summary_returns_publication_ready_sections():
    summary = build_research_summary(run_experiment_suite()["results"])

    assert "title" in summary
    assert "abstract" in summary
    assert "research_question" in summary
    assert "methodology" in summary
    assert "results" in summary
    assert isinstance(summary["results"], list)
