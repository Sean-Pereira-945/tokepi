# DriftGuard

**LLM and AI-Agent Observability, Failed-Tool Diagnosis, and Token-Waste Protection**

DriftGuard is designed to observe LLM applications and AI coding agents. Its target workflow is to detect repetitive failed requests, identify the connected tool blocking a task, estimate tokens wasted by failed or redundant attempts, and explain the problem to the developer. The current release is the telemetry foundation: it captures normalized LLM metrics, stores project-scoped events, evaluates drift thresholds, and displays live dashboard data. Full task/tool retry analysis requires an agent adapter or tool gateway and is not yet shipped.

---

## Key Capabilities

* **Real-Time Drift Detection**: Monitor `prompt_tokens`, `context_length`, `retrieval_score`, and `response_quality` per AI request or agent turn.
* **Mitigation Recommendations**: Recommend context compression, retrieval trimming, or model fallback when configured metrics cross thresholds. The current release does not silently modify an agent or switch a provider.
* **Root-Cause Analysis & Explainability**: Isolate whether degraded AI behavior is caused by prompt inflation, RAG chunk noise, model hallucination, or context dilution.
* **Hosted SaaS Dashboard**: Live dark-glass monitoring UI displaying real-time drift timelines, alert feeds, token savings metrics, and project policy editors.
* **Agent Integration Direction**: Provides the SDK boundary for future multi-turn coding-agent adapters. It does not currently intercept GitHub Copilot sessions or connected tools automatically.

### Product North Star and Current Boundary

The intended agent workflow is:

```text
AI agent -> DriftGuard adapter -> tools
        |
        v
  task/tool/retry telemetry -> DriftGuard -> developer diagnosis
```

The future adapter will report a task ID, tool name, attempt number, success or
failure, error details, and token usage. DriftGuard will then group attempts,
detect repeated failures, calculate wasted tokens, identify the blocking tool, and
show a message such as: "The terminal tool failed three times while running tests;
the task is blocked and 6,420 tokens were spent on retries."

Today, the SDK accepts four normalized metrics (`prompt_tokens`,
`context_length`, `retrieval_score`, and `response_quality`). It does not yet
receive tool-call histories, retry relationships, or Copilot internals.

The first agent-observability slice is now available through the SDK:

```python
client.capture_agent_event(
  task_id="fix-tests",
  trace_id="trace-1",
  tool_name="terminal",
  attempt=3,
  status="failed",
  error_type="command_failed",
  error_message="pytest exited with code 1",
  total_tokens=2200,
)
client.sync_agent_events("my-ai-service")
diagnosis = client.fetch_agent_diagnosis("my-ai-service")
```

The dashboard's **Agent Task Diagnosis** panel reports the blocking tool, failed
attempts, repeated attempts, wasted tokens, severity, and recommendation. An
adapter still needs to call these methods because DriftGuard cannot automatically
observe private Copilot sessions.

---

## Quickstart

### 1. Installation

```bash
pip install driftguard
```

### 2. Basic Python SDK Usage

```python
from driftguard import DriftGuardClient

# Initialize the client (supports local evaluation or SaaS backend sync)
client = DriftGuardClient(
    api_key="dg_live_your_api_key",
    project_name="my-llm-service",
    environment="prod",
    base_url="http://localhost:8000"  # Optional SaaS backend URL
)

# 1. Record telemetry metrics for an AI call
client.capture_metrics(
    prompt_tokens=4200,
    context_length=5500,
    retrieval_score=0.35,  # Low retrieval relevance
    response_quality=0.65  # Quality degradation
)

# 2. Check for real-time drift & risk score (0.0 to 1.0)
drift_report = client.check_drift()
print(drift_report)

# 3. Ship telemetry to the SaaS dashboard (non-blocking)
client.sync_metrics_async(project_id="proj_01")
```

### 3. Example Drift & Mitigation Output

```json
{
  "severity": "critical",
  "risk_score": 0.8,
  "recommendation": "compress_prompt_context_and_reduce_context_window",
  "actions": [
    "compress_prompt_context",
    "trim_retrieval_results"
  ],
  "root_cause": "prompt context inflation; retrieval degradation"
}
```

---

## 🖥️ Launching the Backend & Dashboard

To start the hosted SaaS API and live dashboard locally:

```bash
driftguard-server
# Or directly via uvicorn:
uvicorn driftguard.routes:app --reload --port 8000
```

Open your browser to `http://localhost:8000` to access the interactive **DriftGuard Live Dashboard**.

### Dashboard workflow

1. Select a project and environment from the header dropdowns.
2. Use **Refresh** to reload telemetry, alerts, metrics, and charts.
3. Use **Test Telemetry** to post a real authenticated sample event while wiring an integration.
4. Open **Mitigation Rules** to save project thresholds.
5. Open **SDK Integration** for the provider-neutral integration shape.

The dashboard only needs normalized telemetry. It works with Gemini, OpenAI,
Anthropic, Ollama, or any custom LLM because DriftGuard does not own the model
request. After your existing model call, map token usage, context size, retrieval
quality, and response quality into `capture_metrics(...)`, then call
`sync_metrics(project_id)`.

The dashboard is project-scoped by the **DriftGuard project API key**. Paste the
key returned when you create a project into the dashboard key field. Never paste
your LLM provider secret into DriftGuard; provider credentials remain in your app.

---

## ⚙️ Environment Configuration

Create a `.env` file in your project root:

```env
# Database connection (defaults to local SQLite if unset)
DATABASE_URL=sqlite:///./driftguard.db
# For production SaaS deploy (e.g. Neon DB / PostgreSQL):
# DATABASE_URL=postgresql://user:password@ep-xxxx.neon.tech/driftguard?sslmode=require

# Rate limiting (requests per minute per IP)
RATE_LIMIT_PER_MINUTE=60

# Secret key for session authentication
API_SECRET=your-production-secret-key
```

---

## Using DriftGuard with AI Coding Agents

DriftGuard can be integrated with an AI coding agent when the agent host, extension,
MCP gateway, or wrapper emits telemetry. GitHub Copilot is not automatically
observable from this repository because its private agent session and tool events
are not exposed to DriftGuard.

See **[setup_on_agent.md](docs/setup_on_agent.md)** for the current adapter contract,
the supported telemetry foundation, and the event schema required for full retry
and tool-failure diagnosis.

---

## 📁 Repository Architecture

* `driftguard/client.py`: Developer-facing SDK (`DriftGuardClient`) with telemetry sync and policy caching.
* `driftguard/agent_analysis.py`: Failed-tool, retry, blocked-task, and wasted-token analysis.
* `driftguard/mitigation.py`: Automated token-savings and mitigation recommendation engine.
* `driftguard/routes.py`: FastAPI SaaS backend (Accounts, Ingestion, Policy Management).
* `driftguard/service.py`: SQLite/PostgreSQL persistence layer and query handlers.
* `driftguard/middleware.py`: Rate limiting dependencies and API key authentication.
* `driftguard/api.py`: Hosted SaaS Dashboard UI launcher and dynamic HTML/CSS templates.
* `driftguard/detector.py`: Core mathematical drift scoring engine.
* `docs/setup_on_agent.md`: Comprehensive Antigravity coding agent integration guide.
* `docs/QUICKSTART.md`: Developer onboarding walkthrough.
* `docs/explainability.md`: Explanation of dashboard terms and metrics.

---

## 🧪 Running Tests

Run the complete test suite (62 tests):

```bash
pytest
```
