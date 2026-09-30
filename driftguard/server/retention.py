"""PII and secret scrubbing for stored text, and the periodic retention job."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service import DriftGuardService

logger = logging.getLogger(__name__)

# Credentials that commonly leak into agent tool errors. Checked before generic PII.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdg_live_[A-Za-z0-9_-]{20,}"), "[DRIFTGUARD KEY REDACTED]"),
    (re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"), "[API KEY REDACTED]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}"), "[GITHUB TOKEN REDACTED]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[SLACK TOKEN REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[AWS KEY REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "[GOOGLE KEY REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*"), "Bearer [TOKEN REDACTED]"),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
        "[PRIVATE KEY REDACTED]",
    ),
)
_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _luhn_valid(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def scrub_pii(text: str) -> str:
    """Redact credentials, emails, US SSNs, and Luhn-valid card numbers from ``text``.

    This is a heuristic safety net, not a guarantee. Avoid sending sensitive data
    in telemetry in the first place.
    """
    if not text:
        return text
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    text = _EMAIL.sub("[EMAIL REDACTED]", text)
    text = _SSN.sub("[SSN REDACTED]", text)
    return _CARD.sub(lambda m: "[CREDIT CARD REDACTED]" if _luhn_valid(m.group()) else m.group(), text)


async def run_retention_loop(service: DriftGuardService, retention_days: int, interval_hours: float) -> None:
    """Prune old telemetry now and then every ``interval_hours`` until cancelled."""
    while True:
        try:
            removed = await asyncio.to_thread(service.prune, retention_days)
            logger.info("Retention prune (> %d days): %s", retention_days, removed)
        except Exception:
            logger.exception("Retention prune failed")
        await asyncio.sleep(max(interval_hours, 0.01) * 3600)
