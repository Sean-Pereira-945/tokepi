"""Public package exports for the DriftGuard SDK and detection helpers."""

from .client import DriftGuardClient
from .detector import compute_drift_scores
from .mitigation import recommend_mitigation

__version__ = "0.3.0"

__all__ = [
    "DriftGuardClient",
    "compute_drift_scores",
    "recommend_mitigation",
    "__version__",
]

