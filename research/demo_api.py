"""Small demo FastAPI application exposing synthetic data and drift scores.

Run with ``uvicorn research.demo_api:app --port 8001``. This is a research
prototype and is unrelated to the DriftGuard product server.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .data import build_demo_dataset, compute_baseline_summary
from .detector import compute_drift_scores

app = FastAPI(title="DriftGuard Research Demo", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    """Report that the demo API is available."""
    return {"status": "ok", "service": "driftguard-research-demo"}


@app.get("/dataset")
def get_dataset() -> dict[str, Any]:
    """Return a sample dataset, baseline summary, and preview rows."""
    samples = build_demo_dataset()
    summary = compute_baseline_summary(samples)
    return {"count": len(samples), "summary": summary, "samples": samples[:12]}


@app.get("/drift")
def get_drift() -> dict[str, Any]:
    """Generate demo samples and return their current drift assessment."""
    samples = build_demo_dataset()
    drift = compute_drift_scores(samples)
    return {
        "sample_count": len(samples),
        "drift": drift,
        "latest_sample": samples[-1],
    }
