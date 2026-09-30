"""DriftGuard server (FastAPI). Install with ``pip install "driftguard[server]"``."""

from .app import create_app
from .settings import Settings

__all__ = ["Settings", "create_app"]
