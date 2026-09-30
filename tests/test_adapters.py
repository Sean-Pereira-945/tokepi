import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from driftguard.adapters import AgentContext, MCPMiddleware, driftguard_tool, get_current_context, usage_from_response
from driftguard.client import DriftGuardClient


@pytest.fixture
def client():
    return DriftGuardClient(api_key="k", project_name="agent", environment="test")


def test_tool_outside_context_runs_unchanged(client):
    @driftguard_tool()
    def add(a, b):
        return a + b

    assert add(1, 2) == 3
    assert client.agent_events == []


def test_success_and_failure_are_recorded(client):
    @driftguard_tool("terminal")
    def run(cmd):
        if cmd == "bad":
            raise RuntimeError("exit 1")
        return "ok"

    with AgentContext(client, task_id="t1") as ctx:
        run("pytest")
        with pytest.raises(RuntimeError):
            run("bad")
    first, second = client.agent_events
    assert first["status"] == "success" and first["attempt"] == 1
    assert second["status"] == "failed" and second["attempt"] == 2
    assert second["error_type"] == "RuntimeError" and second["error_message"] == "exit 1"
    assert first["trace_id"] == ctx.trace_id
    assert first["input_hash"] != second["input_hash"]
    assert first["duration_ms"] >= 0
    assert get_current_context() is None


def test_identical_inputs_share_a_fingerprint(client):
    @driftguard_tool("search")
    def search(query):
        return query

    with AgentContext(client, task_id="t"):
        search("x")
        search("x")
    assert client.agent_events[0]["input_hash"] == client.agent_events[1]["input_hash"]


def test_async_tools_and_async_context(client):
    @driftguard_tool("fetch")
    async def fetch(url):
        await asyncio.sleep(0)
        return url

    async def run():
        async with AgentContext(client, task_id="async-task"):
            return await fetch("https://example.test")

    assert asyncio.run(run()) == "https://example.test"
    assert client.agent_events[0]["tool_name"] == "fetch"
    assert client.agent_events[0]["task_id"] == "async-task"


def test_llm_usage_is_attributed_to_the_next_tool_call(client):
    @driftguard_tool("terminal")
    def run():
        return None

    anthropic_like = SimpleNamespace(usage=SimpleNamespace(input_tokens=1200, output_tokens=300))
    with AgentContext(client, task_id="t") as ctx:
        ctx.record_llm_usage(anthropic_like)
        run()
        run()
    first, second = client.agent_events
    assert (first["prompt_tokens"], first["completion_tokens"], first["total_tokens"]) == (1200, 300, 1500)
    assert "total_tokens" not in second


def test_auto_sync_on_exit():
    client = MagicMock(spec=DriftGuardClient)
    with AgentContext(client, task_id="t", auto_sync=True, project_id="p1"):
        pass
    client.sync_agent_events.assert_called_once_with("p1")


@pytest.mark.parametrize(
    "response, expected",
    [
        (SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)), (10, 5, 15)),
        ({"usage": {"input_tokens": 7, "output_tokens": 3}}, (7, 3, 10)),
        (
            SimpleNamespace(
                usage_metadata=SimpleNamespace(prompt_token_count=4, candidates_token_count=6, total_token_count=11)
            ),
            (4, 6, 11),
        ),
    ],
)
def test_usage_from_provider_responses(response, expected):
    usage = usage_from_response(response)
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == expected


def test_usage_from_unknown_response_is_empty():
    assert usage_from_response(object()) == {}


def tools_call(name="calculator", arguments=None):
    return {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": arguments}}


def test_mcp_success(client):
    mw = MCPMiddleware(client, task_id="t1")
    response = {"jsonrpc": "2.0", "id": 7, "result": {"content": [{"type": "text", "text": "42"}]}}
    assert mw.intercept_response(tools_call(), response) is response
    event = client.agent_events[0]
    assert (event["tool_name"], event["status"], event["attempt"], event["tool_call_id"]) == (
        "calculator",
        "success",
        1,
        "7",
    )


def test_mcp_jsonrpc_error(client):
    mw = MCPMiddleware(client, task_id="t1")
    mw.intercept_response(tools_call(), {"id": 7, "error": {"code": -32603, "message": "Division by zero"}})
    event = client.agent_events[0]
    assert (event["status"], event["error_type"], event["error_message"]) == ("failed", "-32603", "Division by zero")


def test_mcp_is_error_result(client):
    mw = MCPMiddleware(client, task_id="t1")
    mw.intercept_response(
        tools_call(), {"result": {"content": [{"type": "text", "text": "Command failed"}], "isError": True}}
    )
    event = client.agent_events[0]
    assert event["error_type"] == "tool_execution_error"
    assert event["error_message"] == "Command failed"


def test_mcp_ignores_other_methods(client):
    MCPMiddleware(client, task_id="t").intercept_response({"method": "tools/list"}, {"result": {}})
    assert client.agent_events == []


def test_mcp_instrumented_session(client):
    class FakeSession:
        server_name = "fake"

        async def call_tool(self, name, arguments=None):
            if name == "boom":
                raise ConnectionError("server gone")
            return SimpleNamespace(isError=name == "bad", content=[SimpleNamespace(text="nope")])

    session = MCPMiddleware(client, task_id="t").instrument_session(FakeSession())
    assert session.server_name == "fake"

    async def run():
        await session.call_tool("good", {"a": 1})
        await session.call_tool("bad", {})
        with pytest.raises(ConnectionError):
            await session.call_tool("boom")

    asyncio.run(run())
    statuses = [(e["tool_name"], e["status"]) for e in client.agent_events]
    assert statuses == [("good", "success"), ("bad", "failed"), ("boom", "failed")]
    assert client.agent_events[1]["error_message"] == "nope"
    assert client.agent_events[2]["error_type"] == "ConnectionError"
