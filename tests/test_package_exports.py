from __future__ import annotations

import driftguard
from driftguard import (
    DriftGuardClient,
    compute_drift_scores,
    recommend_mitigation,
    __version__,
)


def test_package_exports() -> None:
    assert __version__ == "0.3.0"
    assert DriftGuardClient is not None
    assert callable(compute_drift_scores)
    assert callable(recommend_mitigation)


def test_client_init() -> None:
    client = DriftGuardClient(
        api_key="test_key",
        project_name="my-app",
        environment="test",
    )
    assert client.project_name == "my-app"
    assert client.environment == "test"
