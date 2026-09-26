import functools
import threading
import uuid
import time
from typing import Any, Callable, Optional, Dict

from driftguard.client import DriftGuardClient

# Thread-local storage to hold the current agent context during execution.
_local = threading.local()


class AgentContext:
    """Context manager for an agent's execution trace.
    
    This holds the current task and trace IDs so that any tools executed
    within this context can automatically pick them up.
    """

    def __init__(
        self,
        client: DriftGuardClient,
        task_id: str,
        trace_id: Optional[str] = None
    ):
        self.client = client
        self.task_id = task_id
        self.trace_id = trace_id or str(uuid.uuid4())
        self.tool_attempts: Dict[str, int] = {}

    def __enter__(self):
        _local.context = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _local.context = None
        # You could optionally sync events here
        # self.client.sync_agent_events(...)


def get_current_context() -> Optional[AgentContext]:
    """Return the active AgentContext if one exists."""
    return getattr(_local, "context", None)


def driftguard_tool(name: Optional[str] = None):
    """Decorator to automatically capture tool telemetry.
    
    Logs tool executions, tracks retries, captures exceptions, and sends
    them via the DriftGuardClient if an AgentContext is active.
    """
    def decorator(func: Callable):
        tool_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            ctx = get_current_context()
            if not ctx:
                return func(*args, **kwargs)

            # Keep track of attempts per tool
            ctx.tool_attempts[tool_name] = ctx.tool_attempts.get(tool_name, 0) + 1
            attempt = ctx.tool_attempts[tool_name]
            tool_call_id = str(uuid.uuid4())

            event_data = {
                "task_id": ctx.task_id,
                "trace_id": ctx.trace_id,
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "attempt": attempt,
            }

            try:
                result = func(*args, **kwargs)
                
                # Success
                event_data.update({
                    "status": "success",
                    "error_type": None,
                    "error_message": None,
                })
                ctx.client.capture_agent_event(**event_data)
                return result

            except Exception as e:
                # Failure
                event_data.update({
                    "status": "failed",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                })
                ctx.client.capture_agent_event(**event_data)
                raise

        return wrapper
    return decorator
