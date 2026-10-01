"""Instrument a Python agent's tool functions with DriftGuard agent events.

Wrap the agent run in :class:`AgentContext` and decorate each tool with
:func:`driftguard_tool`. Every call then emits one event with the task ID, tool
name, attempt number, status, error, duration, an input fingerprint, and any LLM
tokens recorded since the previous tool call::

    with AgentContext(client, task_id="fix-tests") as run:
        response = llm.messages.create(...)
        run.record_llm_usage(response)      # tokens are attributed to the next tool call
        run_tests()                         # decorated with @driftguard_tool("terminal")

The context uses :mod:`contextvars`, so it works with threads and asyncio.
"""

from __future__ import annotations

import contextvars
import functools
import hashlib
import inspect
import json
import time
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from driftguard.client import DriftGuardClient

from .usage import usage_from_response

F = TypeVar("F", bound=Callable[..., Any])

# Longest content preview sent per field; the server truncates at the same length.
PREVIEW_LIMIT = 2000

_current: contextvars.ContextVar[AgentContext | None] = contextvars.ContextVar("driftguard_agent_context", default=None)


def fingerprint(*parts: Any) -> str:
    """Return a short stable hash of tool inputs, used to spot duplicate calls."""
    encoded = json.dumps(parts, sort_keys=True, default=repr)
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


def preview(value: Any) -> str:
    """Render a tool argument or result as short text for the activity log."""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=repr, ensure_ascii=False)
        except (TypeError, ValueError):
            text = repr(value)
    return text if len(text) <= PREVIEW_LIMIT else text[:PREVIEW_LIMIT] + " …[truncated]"


class AgentContext:
    """One agent task run. Tools called inside it are attributed to ``task_id``.

    Args:
        client: The :class:`DriftGuardClient` that queues events.
        task_id: Stable identifier for the task the agent is working on.
        trace_id: Identifier for this run; generated when omitted.
        auto_sync: Sync queued agent events when the context exits.
        project_id: Project to sync to when ``auto_sync`` is on (defaults to the
            client's ``project_id``).
    """

    def __init__(
        self,
        client: DriftGuardClient,
        task_id: str,
        trace_id: str | None = None,
        auto_sync: bool = False,
        project_id: str | None = None,
    ) -> None:
        self.client = client
        self.task_id = task_id
        self.trace_id = trace_id or str(uuid.uuid4())
        self.auto_sync = auto_sync
        self.project_id = project_id
        self.tool_attempts: dict[str, int] = {}
        self._pending_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self._token: contextvars.Token[AgentContext | None] | None = None

    def __enter__(self) -> AgentContext:
        self._token = _current.set(self)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._token is not None:
            _current.reset(self._token)
            self._token = None
        if self.auto_sync:
            self.client.sync_agent_events(self.project_id)

    async def __aenter__(self) -> AgentContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.__exit__(exc_type, exc, tb)

    def record_llm_usage(self, response: Any = None, *, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """Record tokens from a model turn; they are attached to the next tool event.

        Pass a provider response object (OpenAI, Anthropic, or Gemini) or explicit
        token counts.
        """
        usage = usage_from_response(response) if response is not None else {}
        self._pending_usage["prompt_tokens"] += usage.get("prompt_tokens", 0) + prompt_tokens
        self._pending_usage["completion_tokens"] += usage.get("completion_tokens", 0) + completion_tokens

    def _take_usage(self) -> dict[str, int]:
        usage = dict(self._pending_usage)
        self._pending_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        if not any(usage.values()):
            return {}
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        return usage

    def record_tool_call(
        self,
        tool_name: str,
        status: str,
        *,
        error: BaseException | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        duration_ms: float | None = None,
        input_hash: str | None = None,
        tool_call_id: str | None = None,
        input: Any = None,
        output: Any = None,
    ) -> dict[str, Any]:
        """Emit one agent event for a tool call. Used by the decorator and MCP adapter.

        ``input`` and ``output`` are sent as previews only when the client has
        ``capture_content`` on.
        """
        self.tool_attempts[tool_name] = self.tool_attempts.get(tool_name, 0) + 1
        event: dict[str, Any] = {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id or str(uuid.uuid4()),
            "attempt": self.tool_attempts[tool_name],
            "status": status,
            "error_type": error_type or (type(error).__name__ if error else None),
            "error_message": error_message or (str(error) if error else None),
        }
        if duration_ms is not None:
            event["duration_ms"] = round(duration_ms, 3)
        if input_hash:
            event["input_hash"] = input_hash
        self._add_content(event, input, output)
        event.update(self._take_usage())
        return self.client.capture_agent_event(**event)

    def record_activity(
        self,
        kind: str,
        *,
        input: Any = None,
        output: Any = None,
        status: str | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        """Log a non-tool activity for this task, such as ``prompt``, ``response`` or ``llm_call``.

        Extra keyword arguments (``model``, ``prompt_tokens``, ``duration_ms``, …)
        are sent as event fields. These events appear in the activity log and are
        ignored by the blocked-tool diagnosis.
        """
        event: dict[str, Any] = {"task_id": self.task_id, "trace_id": self.trace_id, "kind": kind, **fields}
        if status is not None:
            event["status"] = status
        self._add_content(event, input, output)
        return self.client.capture_agent_event(**event)

    def _add_content(self, event: dict[str, Any], input: Any, output: Any) -> None:
        if not self.client.capture_content:
            return
        if input is not None:
            event["input"] = preview(input)
        if output is not None:
            event["output"] = preview(output)


def _call_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """The arguments of a tool call, in the simplest form for a preview."""
    if not kwargs:
        return args[0] if len(args) == 1 else list(args)
    return {"args": list(args), "kwargs": kwargs} if args else kwargs


def get_current_context() -> AgentContext | None:
    """Return the active :class:`AgentContext`, if any."""
    return _current.get()


def driftguard_tool(name: str | None = None) -> Callable[[F], F]:
    """Decorate a sync or async tool so each call emits a DriftGuard agent event.

    Outside an :class:`AgentContext` the tool runs unchanged. Exceptions are
    recorded as failures and re-raised.
    """

    def decorator(func: F) -> F:
        tool_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                ctx = get_current_context()
                if ctx is None:
                    return await func(*args, **kwargs)
                started = time.perf_counter()
                input_hash = fingerprint(tool_name, args, kwargs)
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    ctx.record_tool_call(
                        tool_name,
                        "failed",
                        error=exc,
                        input_hash=input_hash,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        input=_call_args(args, kwargs),
                    )
                    raise
                ctx.record_tool_call(
                    tool_name,
                    "success",
                    input_hash=input_hash,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    input=_call_args(args, kwargs),
                    output=result,
                )
                return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = get_current_context()
            if ctx is None:
                return func(*args, **kwargs)
            started = time.perf_counter()
            input_hash = fingerprint(tool_name, args, kwargs)
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                ctx.record_tool_call(
                    tool_name,
                    "failed",
                    error=exc,
                    input_hash=input_hash,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    input=_call_args(args, kwargs),
                )
                raise
            ctx.record_tool_call(
                tool_name,
                "success",
                input_hash=input_hash,
                duration_ms=(time.perf_counter() - started) * 1000,
                input=_call_args(args, kwargs),
                output=result,
            )
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
