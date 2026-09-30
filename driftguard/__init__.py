"""DriftGuard SDK: capture LLM and agent telemetry, check drift, and diagnose failed tools.

The SDK depends only on ``httpx``. The hosted server lives in
:mod:`driftguard.server` and needs ``pip install "driftguard[server]"``.
"""

from .agent_analysis import analyze_agent_events
from .client import DriftGuardClient
from .policy import DEFAULT_POLICY, evaluate_drift, recommend_mitigation

__version__ = "0.4.0"

__all__ = [
    "DEFAULT_POLICY",
    "DriftGuardClient",
    "analyze_agent_events",
    "evaluate_drift",
    "recommend_mitigation",
    "__version__",
]
