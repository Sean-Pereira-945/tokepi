"""Extract token usage from LLM provider responses without importing provider SDKs."""

from __future__ import annotations

from typing import Any


def _read(obj: Any, name: str) -> Any:
    """Read ``name`` from an object attribute or a mapping key."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def usage_from_response(response: Any) -> dict[str, int]:
    """Return ``prompt_tokens``, ``completion_tokens`` and ``total_tokens`` from a response.

    Understands the usage shapes of the OpenAI (``usage.prompt_tokens`` /
    ``completion_tokens``), Anthropic (``usage.input_tokens`` / ``output_tokens``)
    and Gemini (``usage_metadata.prompt_token_count`` / ``candidates_token_count``)
    Python SDKs, as objects or plain dicts. Returns an empty dict when no usage
    is found.
    """
    usage = _read(response, "usage")
    if usage is not None:
        prompt = _read(usage, "prompt_tokens")
        completion = _read(usage, "completion_tokens")
        if prompt is None and completion is None:
            prompt = _read(usage, "input_tokens")
            completion = _read(usage, "output_tokens")
        total = _read(usage, "total_tokens")
    else:
        metadata = _read(response, "usage_metadata")
        if metadata is None:
            return {}
        prompt = _read(metadata, "prompt_token_count")
        completion = _read(metadata, "candidates_token_count")
        total = _read(metadata, "total_token_count")

    if prompt is None and completion is None and total is None:
        return {}
    prompt_tokens = int(prompt or 0)
    completion_tokens = int(completion or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": int(total) if total is not None else prompt_tokens + completion_tokens,
    }
