# Setting up DriftGuard on an AI Coding Agent

This guide explains the intended integration between **DriftGuard** and an AI
coding agent such as Antigravity, GitHub Copilot, or a custom tool-calling agent.
The product goal is to detect repeated failed tool requests, identify the tool
blocking a task, estimate tokens wasted by retries, and explain the problem to the
developer.

## Current implementation boundary

The repository currently implements the telemetry foundation: an SDK, project API
keys, event storage, threshold-based drift checks, recommendations, and a live
dashboard. It does not automatically intercept GitHub Copilot or Antigravity
sessions, observe private tool calls, count retries, or calculate retry waste.

The examples below show the adapter shape needed to connect an agent host. Some
agent-specific methods are placeholders because each agent exposes different
hooks.

---

## 1. Why Antigravity Agents Suffer from Drift

Antigravity is an agentic AI coding assistant that executes multi-turn tasks (reading workspace files, running shell commands, executing tests, and generating code edits).

As an Antigravity agent session progresses through multiple turns, it encounters three primary forms of **runtime drift**:

1. **Context Window Bloat (Prompt Drift)**:
   - Tool execution outputs (e.g. reading 500-line source files or long terminal error logs) get appended to conversation history.
   - `prompt_tokens` balloon rapidly, increasing API costs exponentially and causing model attention dilution (where the LLM misses subtle instructions in long prompts).
2. **Code Search / Retrieval Noise**:
   - As workspace size grows, ripgrep / semantic code search returns irrelevant files or outdated snippets, dropping the `retrieval_score`.
3. **Quality Collapse**:
   - Long history can lead to repeated tool failures, syntax errors, or hallucinated method signatures, dropping the `response_quality`.

DriftGuard is intended to act as an **observability and mitigation layer** around
an agent loop. The current SDK returns recommendations to the host application; it
does not automatically prune context or execute tool changes unless the host
application implements those actions.

---

## 2. Current LLM Telemetry Metrics

The current SDK accepts four normalized metrics for an agent turn:

| Metric | Description | Healthy Range | Drift Threshold |
|---|---|---|---|
| `prompt_tokens` | Tokens sent in the current agent prompt | `< 3,000` | `> 3,000` (Warning) |
| `context_length` | Total active conversation history length | `< 4,000` | `> 4,000` (Critical) |
| `retrieval_score` | Relevance score of code search / file context | `0.7 – 1.0` | `< 0.5` (Degraded) |
| `response_quality` | Tool execution success rate & syntax validity | `0.8 – 1.0` | `< 0.8` (Quality Drop) |

---

## 3. Step-by-Step Adapter Integration

### Step 1: Install DriftGuard in your Agent Environment

```bash
pip install driftguard
```

### Step 2: Initialize `DriftGuardClient`

Initialize the SDK when your Antigravity agent starts up:

```python
from driftguard import DriftGuardClient

# Initialize DriftGuard SDK for the Antigravity Agent
drift_client = DriftGuardClient(
    api_key="dg_live_your_project_api_key",
    project_name="antigravity-agent",
    environment="prod",
    base_url="http://localhost:8000"  # Points to hosted SaaS backend
)

# Fetch project drift policy thresholds from the backend
drift_client.fetch_policy(project_id="proj_antigravity_01")
```

---

### Step 3: Wrap the Agent Execution Loop

Wrap your agent turn execution function to capture telemetry, check for drift, and trigger mitigation actions:

```python
import time
from typing import Dict, Any, List

def run_antigravity_step(
    agent_session: Any,
    user_prompt: str,
    history: List[Dict[str, Any]],
    retrieved_code_chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    
    # 1. Execute agent turn (LLM generation + tool execution)
    turn_start = time.time()
    response = agent_session.step(prompt=user_prompt, history=history)
    tool_success = agent_session.last_tool_status == "SUCCESS"
    
    # 2. Calculate runtime metrics
    prompt_tokens = response.usage.prompt_tokens
    context_len = sum(len(msg.get("content", "")) for msg in history) // 4  # approx tokens
    
    # Calculate code search relevance (e.g. ratio of matching code blocks used)
    retrieval_relevance = calculate_search_relevance(retrieved_code_chunks)
    
    # Calculate response quality (1.0 for clean tool run, 0.3 for error/syntax fail)
    quality_score = 1.0 if tool_success else 0.3

    # 3. Capture metrics in DriftGuard
    drift_client.capture_metrics(
        prompt_tokens=prompt_tokens,
        context_length=context_len,
        retrieval_score=retrieval_relevance,
        response_quality=quality_score
    )

    # 4. Perform real-time drift check
    drift_report = drift_client.check_drift()
    
    print(f"📊 [DriftGuard] Severity: {drift_report['severity'].upper()} | Risk Score: {drift_report['risk_score']}")

    # 5. Return a recommendation to the host agent
    if drift_report["severity"] in ["warning", "critical"]:
        print(f"⚠️ [DriftGuard Alert] {drift_report['recommendation']}")
        print(f"🔍 Root Cause: {drift_report['root_cause']}")
        
        # The host may apply these actions to agent state
        history = apply_mitigation_to_antigravity_history(history, drift_report["actions"])

    # 6. Ship telemetry asynchronously to SaaS dashboard
    drift_client.sync_metrics_async(project_id="proj_antigravity_01")

    return response
```

---

### Step 4: Optional Host-Side Mitigation Handler

When DriftGuard identifies drift actions (`compress_prompt_context`, `trim_retrieval_results`, `reduce_context_window`), the host application may apply state adjustments like these:

```python
def apply_mitigation_to_antigravity_history(
    history: List[Dict[str, Any]], 
    actions: List[str]
) -> List[Dict[str, Any]]:
    """Prunes history and compresses context when DriftGuard flags drift."""
    
    if "compress_prompt_context" in actions or "reduce_context_window" in actions:
        # Prune old file content views and terminal outputs older than 3 turns
        pruned_history = []
        for idx, msg in enumerate(history):
            # Retain system prompt and recent turns, truncate large intermediate outputs
            if idx < 2 or idx >= len(history) - 4:
                pruned_history.append(msg)
            elif msg.get("role") == "tool_output":
                # Compress large tool outputs to a summary note
                pruned_history.append({
                    "role": "tool_output",
                    "content": f"[DriftGuard Compressed: Truncated {len(msg['content'])} chars of past log context]"
                })
            else:
                pruned_history.append(msg)
        print("✂️ [Mitigation Applied] Pruned old tool output logs from agent context.")
        return pruned_history

    if "trim_retrieval_results" in actions:
        # Reduce top-k retrieved file chunks to prevent prompt noise
        print("✂️ [Mitigation Applied] Trimmed top-k code retrieval results to 3 chunks.")

    return history
```

---

## 4. Complete End-to-End Code Example

Here is a complete, self-contained Python script implementing a **Drift-Monitored Antigravity Agent**:

```python
import sys
from driftguard import DriftGuardClient

class DriftMonitoredAntigravityAgent:
    def __init__(self, api_key: str, backend_url: str = "http://localhost:8000"):
        self.dg = DriftGuardClient(
            api_key=api_key,
            project_name="antigravity-core",
            environment="prod",
            base_url=backend_url
        )
        self.history = []
        self.project_id = "proj_antigravity_01"

    def process_turn(self, user_instruction: str):
        print(f"\n🚀 Agent processing: '{user_instruction}'")
        
        # Simulate agent history growth & token metrics
        self.history.append({"role": "user", "content": user_instruction})
        
        # Simulated metrics for an agent turn (e.g. line viewing + bash output)
        simulated_prompt_tokens = 3500  # High token count
        simulated_context_length = 4800 # High context window
        simulated_retrieval = 0.42      # Low retrieval relevance
        simulated_quality = 0.70        # Minor tool failure
        
        # Record & Check Drift
        self.dg.capture_metrics(
            prompt_tokens=simulated_prompt_tokens,
            context_length=simulated_context_length,
            retrieval_score=simulated_retrieval,
            response_quality=simulated_quality
        )
        
        report = self.dg.check_drift()
        
        print(f"🛡️ Drift Severity : {report['severity'].upper()}")
        print(f"📈 Risk Score      : {report['risk_score']}")
        print(f"💡 Root Cause     : {report['root_cause']}")
        print(f"🛠️ Actions Needed : {report['actions']}")

        # Apply mitigation if drift warning/critical
        if report["severity"] in ["warning", "critical"]:
            self._mitigate(report["actions"])

        # Sync telemetry to SaaS dashboard
        sync_res = self.dg.sync_metrics(project_id=self.project_id)
        print(f"📡 Dashboard Sync : {sync_res}")

    def _mitigate(self, actions: list):
        if "compress_prompt_context" in actions:
            print("  -> [ACTION] Compressing agent prompt history...")
            self.history = self.history[-2:] # Keep only recent turns

if __name__ == "__main__":
    agent = DriftMonitoredAntigravityAgent(api_key="dg_live_demo_123")
    agent.process_turn("Fix bug in routes.py and rerun pytest")
```

---

## 5. Live SaaS Dashboard Monitoring

Once your Antigravity agent is connected, start the backend to view live metrics in your browser:

```bash
uvicorn driftguard.routes:app --reload --port 8000
```

Open `http://localhost:8000` to view:
1. **Live Agent Event Feed**: Inspection table showing each agent turn's tokens, quality, and retrieval score.
2. **Drift Timeline Chart**: Real-time canvas chart plotting risk score over agent session turns.
3. **Token Savings Tracker**: Total saved tokens and cost reductions achieved through automated context pruning.
4. **Policy Configurator**: Live panel to adjust `prompt_token_limit` and `retrieval_score_floor` thresholds without redeploying your agent.

## 6. Required telemetry for full retry and tool diagnosis

To implement the complete product behavior, an adapter must emit one structured
event for every task, model turn, tool call, retry, result, and failure:

```json
{
    "task_id": "implement-login",
    "trace_id": "task-123",
    "agent_name": "coding-agent",
    "tool_name": "terminal",
    "tool_call_id": "call-42",
    "attempt": 3,
    "status": "failed",
    "error_type": "command_failed",
    "error_message": "pytest exited with code 1",
    "prompt_tokens": 1800,
    "completion_tokens": 400,
    "total_tokens": 2200
}
```

The agent event storage and analysis slice is now implemented through
`DriftGuardClient.capture_agent_event`, `sync_agent_events`, and
`fetch_agent_diagnosis`. The adapter still must emit these events. The analyzer
groups attempts by task, detects repeated failures, calculates failed or redundant
token waste, identifies the blocking tool, and publishes a diagnosis such as:
"The terminal tool failed three times while running tests; the task is blocked."
