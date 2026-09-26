import uuid
import json
from typing import Any, Dict, Optional, Callable

from driftguard.client import DriftGuardClient


class MCPMiddleware:
    """Model Context Protocol (MCP) Middleware for DriftGuard.
    
    This middleware sits between an MCP client (the agent) and an MCP server (the tools).
    It intercepts `call_tool` requests and responses to automatically record
    telemetry events to DriftGuard.
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

    def intercept_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Intercepts an outgoing MCP request.
        
        Currently, this just passes the request through, as we need the response
        to determine success or failure. But it can be used to inject trace IDs.
        """
        return request

    def intercept_response(
        self,
        request: Dict[str, Any],
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Intercepts an MCP response and logs telemetry.
        
        Assumes standard JSON-RPC 2.0 format for MCP messages where
        method="tools/call" (or similar depending on MCP version).
        """
        method = request.get("method")
        
        # We primarily care about tool executions
        if method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "unknown_tool")
            
            # Track attempts
            self.tool_attempts[tool_name] = self.tool_attempts.get(tool_name, 0) + 1
            attempt = self.tool_attempts[tool_name]
            
            tool_call_id = str(uuid.uuid4())
            
            event_data = {
                "task_id": self.task_id,
                "trace_id": self.trace_id,
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "attempt": attempt,
            }

            if "error" in response:
                error_info = response["error"]
                event_data.update({
                    "status": "failed",
                    "error_type": str(error_info.get("code", "unknown_error")),
                    "error_message": error_info.get("message", "MCP Tool Error"),
                })
            else:
                # Check for "isError" flag inside tool result
                result = response.get("result", {})
                if result.get("isError"):
                    event_data.update({
                        "status": "failed",
                        "error_type": "tool_execution_error",
                        "error_message": str(result),
                    })
                else:
                    event_data.update({
                        "status": "success",
                        "error_type": None,
                        "error_message": None,
                    })

            self.client.capture_agent_event(**event_data)

        return response
