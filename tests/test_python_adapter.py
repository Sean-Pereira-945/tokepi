import pytest
from unittest.mock import MagicMock
from driftguard.client import DriftGuardClient
from driftguard.adapters.python_agent import AgentContext, driftguard_tool

@pytest.fixture
def mock_client():
    client = MagicMock(spec=DriftGuardClient)
    client.project_name = "test_project"
    client.environment = "test"
    return client

def test_python_adapter_success(mock_client):
    @driftguard_tool(name="dummy_tool")
    def dummy_success():
        return "success"
    
    with AgentContext(client=mock_client, task_id="task-1"):
        result = dummy_success()
        
    assert result == "success"
    mock_client.capture_agent_event.assert_called_once()
    call_args = mock_client.capture_agent_event.call_args[1]
    
    assert call_args["task_id"] == "task-1"
    assert call_args["tool_name"] == "dummy_tool"
    assert call_args["status"] == "success"
    assert call_args["attempt"] == 1

def test_python_adapter_failure(mock_client):
    @driftguard_tool(name="dummy_fail")
    def dummy_fail():
        raise ValueError("Oops")
    
    with AgentContext(client=mock_client, task_id="task-1"):
        with pytest.raises(ValueError):
            dummy_fail()
            
    mock_client.capture_agent_event.assert_called_once()
    call_args = mock_client.capture_agent_event.call_args[1]
    
    assert call_args["task_id"] == "task-1"
    assert call_args["tool_name"] == "dummy_fail"
    assert call_args["status"] == "failed"
    assert call_args["error_type"] == "ValueError"
    assert call_args["error_message"] == "Oops"
    assert call_args["attempt"] == 1

def test_python_adapter_retry(mock_client):
    @driftguard_tool(name="retry_tool")
    def retry_tool(fail=True):
        if fail:
            raise ValueError("Failed")
        return "Success"
        
    with AgentContext(client=mock_client, task_id="task-1"):
        try:
            retry_tool(fail=True)
        except ValueError:
            pass
            
        retry_tool(fail=False)
        
    assert mock_client.capture_agent_event.call_count == 2
    first_call = mock_client.capture_agent_event.call_args_list[0][1]
    second_call = mock_client.capture_agent_event.call_args_list[1][1]
    
    assert first_call["status"] == "failed"
    assert first_call["attempt"] == 1
    
    assert second_call["status"] == "success"
    assert second_call["attempt"] == 2
