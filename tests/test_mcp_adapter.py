import pytest
from unittest.mock import MagicMock
from driftguard.client import DriftGuardClient
from driftguard.adapters.mcp import MCPMiddleware

@pytest.fixture
def mock_client():
    client = MagicMock(spec=DriftGuardClient)
    client.project_name = "test_project"
    client.environment = "test"
    return client

def test_mcp_adapter_success(mock_client):
    middleware = MCPMiddleware(client=mock_client, task_id="task-1")
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "calculator"
        }
    }
    
    response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "value": 42
        }
    }
    
    middleware.intercept_response(request, response)
    
    mock_client.capture_agent_event.assert_called_once()
    call_args = mock_client.capture_agent_event.call_args[1]
    
    assert call_args["task_id"] == "task-1"
    assert call_args["tool_name"] == "calculator"
    assert call_args["status"] == "success"
    assert call_args["attempt"] == 1

def test_mcp_adapter_error(mock_client):
    middleware = MCPMiddleware(client=mock_client, task_id="task-1")
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "calculator"
        }
    }
    
    response = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32603,
            "message": "Division by zero"
        }
    }
    
    middleware.intercept_response(request, response)
    
    mock_client.capture_agent_event.assert_called_once()
    call_args = mock_client.capture_agent_event.call_args[1]
    
    assert call_args["task_id"] == "task-1"
    assert call_args["tool_name"] == "calculator"
    assert call_args["status"] == "failed"
    assert call_args["error_type"] == "-32603"
    assert call_args["error_message"] == "Division by zero"
    assert call_args["attempt"] == 1

def test_mcp_adapter_tool_isError(mock_client):
    middleware = MCPMiddleware(client=mock_client, task_id="task-1")
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "calculator"
        }
    }
    
    # MCP format where error is returned inside the result with isError flag
    response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": "Command failed"}],
            "isError": True
        }
    }
    
    middleware.intercept_response(request, response)
    
    mock_client.capture_agent_event.assert_called_once()
    call_args = mock_client.capture_agent_event.call_args[1]
    
    assert call_args["task_id"] == "task-1"
    assert call_args["tool_name"] == "calculator"
    assert call_args["status"] == "failed"
    assert call_args["error_type"] == "tool_execution_error"
    assert call_args["attempt"] == 1
