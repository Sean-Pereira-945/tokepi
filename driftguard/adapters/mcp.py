"""Record Model Context Protocol (MCP) tool calls as DriftGuard agent events.

Two integration styles are supported:

* **JSON-RPC interception** for gateways and proxies that see raw MCP messages:
  pass each ``tools/call`` request and its response to
  :meth:`MCPMiddleware.intercept_response`.
* **Session instrumentation** for agents using the official ``mcp`` Python SDK:
  ``session = middleware.instrument_session(session)`` wraps ``call_tool`` so
  every call is recorded. The ``mcp`` package itself is not required here.

MCP observes tool calls only. Pair it with
:meth:`~driftguard.adapters.python_agent.AgentContext.record_llm_usage` (via
:attr:`MCPMiddleware.context`) to attribute model tokens to tool attempts.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from driftguard.client import DriftGuardClient

from .python_agent import AgentContext, fingerprint


def _text_content(result: Any) -> str:
    """Join the text blocks of an MCP tool result (dict or SDK object)."""
    content = result.get("content") if isinstance(result, Mapping) else getattr(result, "content", None)
    texts = []
    for block in content or []:
        text = block.get("text") if isinstance(block, Mapping) else getattr(block, "text", None)
        if text:
            texts.append(str(text))
    return "\n".join(texts)


class MCPMiddleware:
    """Record MCP ``tools/call`` executions for one agent task."""

    def __init__(self, client: DriftGuardClient, task_id: str, trace_id: str | None = None) -> None:
        self.context = AgentContext(client, task_id=task_id, trace_id=trace_id)
        self.client = client

    @property
    def task_id(self) -> str:
        return self.context.task_id

    @property
    def trace_id(self) -> str:
        return self.context.trace_id

    @property
    def tool_attempts(self) -> dict[str, int]:
        return self.context.tool_attempts

    def intercept_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Pass an outgoing MCP request through unchanged (hook for future tracing)."""
        return request

    def intercept_response(
        self, request: dict[str, Any], response: dict[str, Any], duration_ms: float | None = None
    ) -> dict[str, Any]:
        """Record a JSON-RPC ``tools/call`` response and return it unchanged."""
        if request.get("method") != "tools/call":
            return response

        params = request.get("params") or {}
        tool_name = str(params.get("name") or "unknown_tool")
        input_hash = fingerprint(tool_name, params.get("arguments"))
        call_id = str(request["id"]) if request.get("id") is not None else None

        if "error" in response:
            error = response["error"] or {}
            self.context.record_tool_call(
                tool_name,
                "failed",
                error_type=str(error.get("code", "unknown_error")),
                error_message=str(error.get("message", "MCP tool error")),
                duration_ms=duration_ms,
                input_hash=input_hash,
                tool_call_id=call_id,
                input=params.get("arguments"),
            )
        elif (response.get("result") or {}).get("isError"):
            self.context.record_tool_call(
                tool_name,
                "failed",
                error_type="tool_execution_error",
                error_message=_text_content(response["result"]) or "MCP tool returned isError",
                duration_ms=duration_ms,
                input_hash=input_hash,
                tool_call_id=call_id,
                input=params.get("arguments"),
            )
        else:
            self.context.record_tool_call(
                tool_name,
                "success",
                duration_ms=duration_ms,
                input_hash=input_hash,
                tool_call_id=call_id,
                input=params.get("arguments"),
                output=_text_content(response.get("result") or {}) or None,
            )
        return response

    def instrument_session(self, session: Any) -> _InstrumentedSession:
        """Wrap an MCP ``ClientSession`` so ``call_tool`` calls are recorded."""
        return _InstrumentedSession(session, self)


class _InstrumentedSession:
    """Proxy around an MCP client session that records each ``call_tool``."""

    def __init__(self, session: Any, middleware: MCPMiddleware) -> None:
        self._session = session
        self._middleware = middleware

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> Any:
        ctx = self._middleware.context
        input_hash = fingerprint(name, arguments)
        started = time.perf_counter()
        try:
            result = await self._session.call_tool(name, arguments, *args, **kwargs)
        except Exception as exc:
            ctx.record_tool_call(
                name,
                "failed",
                error=exc,
                input_hash=input_hash,
                duration_ms=(time.perf_counter() - started) * 1000,
                input=arguments,
            )
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        is_error = result.get("isError") if isinstance(result, Mapping) else getattr(result, "isError", False)
        if is_error:
            ctx.record_tool_call(
                name,
                "failed",
                error_type="tool_execution_error",
                error_message=_text_content(result) or "MCP tool returned isError",
                input_hash=input_hash,
                duration_ms=duration_ms,
                input=arguments,
            )
        else:
            ctx.record_tool_call(
                name,
                "success",
                input_hash=input_hash,
                duration_ms=duration_ms,
                input=arguments,
                output=_text_content(result) or None,
            )
        return result
