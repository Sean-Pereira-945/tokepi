# DriftGuard Architecture & Detailed Design

This document details the system design, components, and data flows of **DriftGuard**, explaining how it accomplishes LLM observability, cost-protection, and agent tool-loop diagnosis.

---

## 1. System Overview

DriftGuard is designed to solve runtime degradation and cost overrun issues in LLM applications and agentic workflows. It acts as an observability and mitigation layer, sitting between client-side agent runtimes and LLM provider endpoints.

### Key Capabilities
1. **Real-time Drift Detection**: Scoring context bloat, prompt token creep, retrieval degradation, and response quality drops.
2. **Mitigation Engine**: Formulating actionable instructions (e.g. compressing history, trimming files) returned to the host application.
3. **Agent Tool-Loop Diagnosis**: Grouping model turns by task trace to flag looping attempts, calculate wasted tokens, and find the blocking tool.
4. **SaaS Dashboard**: Displaying aggregated metrics, alerts history, and tool-loop debugging analytics.

---

## 2. Core Architecture Diagram

```mermaid
graph TD
    subgraph Client Application
        AgentLoop[Agent Execution Loop]
        DG_SDK[DriftGuard SDK Client]
    end

    subgraph DriftGuard Backend (FastAPI)
        API_Gateway[API Ingestion Layer]
        DiagEngine[Diagnosis & Analytics Engine]
        MitEngine[Mitigation Recommendation Engine]
    end

    subgraph Persistent Storage
        Database[("SQLite / SQLAlchemy")]
    end

    subgraph Frontend Interface
        Dashboard[Web Dashboard UI]
    end

    AgentLoop -->|1. Capture Telemetry & Events| DG_SDK
    DG_SDK -->|2. POST /api/v1/telemetry| API_Gateway
    API_Gateway -->|3. Persist Logs| Database
    API_Gateway -->|4. Analyze| DiagEngine
    API_Gateway -->|4. Analyze| MitEngine
    Dashboard -->|5. Read Diagnostics & Metrics| API_Gateway
```

---

## 3. Component Details

### A. Developer SDK (`driftguard/client.py`)
Provides the client interface for Python applications.
- **`capture_agent_event(task_id, trace_id, event_type, prompt_tokens, completion_tokens, tool_name, status, error_message)`**: Accumulates structured events locally for a specific agent step.
- **`sync_agent_events(project_id)`**: Serializes and sends accumulated events to the SaaS backend under the project's API key.
- **`fetch_agent_diagnosis(project_id)`**: Retrieves the computed list of blocking tools and retry counts for active developer review.

### B. Ingestion & API Layer (`driftguard/routes.py`)
A FastAPI server handling communication with both the SDK client and the web frontend.
- **Project Isolation**: Authenticates and filters telemetry using project API keys (`dg_live_...`).
- **Telemetry Ingestion**: Receives individual turn metrics and multi-event agent trace sequences.
- **Dashboard Routes**: Compiles real-time metrics, system health timeline, and task diagnostic summaries for the UI.

### C. Diagnosis & Analytics Engine (`driftguard/analytics.py` & `driftguard/dashboard_data.py`)
Performs trace-level analyses on ingested logs.
- **Trace Aggregation**: Groups event logs by unique `trace_id` (individual user-task runs).
- **Tool-Loop Detection**: Identifies repeated executions of a specific tool within a trace window.
- **Wasted-Token Calculation**: Calculates prompt and completion tokens consumed by failed turns and redundant attempts.
- **Root-Cause Isolation**: Identifies the specific tool responsible for the failure (the "blocking tool") by analyzing trailing error codes and repeats.

---

## 4. Key Algorithm Implementations

### A. Wasted Token Calculation
Tokens are considered "wasted" when they are consumed during tool executions that ultimately fail, or during repetitive, redundant model calls that do not change state.
For any given task trace:
$$\text{Wasted Tokens} = \sum (\text{Prompt Tokens} + \text{Completion Tokens})_{\text{Failed Events}} + \sum (\text{Prompt Tokens} + \text{Completion Tokens})_{\text{Redundant Retries}}$$
This value is converted to a dollar equivalent based on provider-specific rate profiles (e.g., standard GPT-4o / Claude 3.5 Sonnet costs per million tokens) to show financial impact in the dashboard.

### B. Blocking-Tool Diagnosis
To find which connected tool is blocking the agent from completing its task:
1. Fetch all events for a specific trace, ordered chronologically.
2. Group consecutive failures by tool name.
3. If a tool fails more than a specified threshold (e.g. 3 times) or repeatedly throws system errors without a successful outcome, flag it as the **Blocking Tool**.
4. Retrieve the mitigation suggestion associated with that tool's failure signature from the recommendation engine.

---

## 5. Integrating with Agent Runtimes (Future Design)

For an agent like Antigravity, DriftGuard does not intercept the communication implicitly. Instead, developers can run a wrapper pattern:

### Wrapper Integration Pattern
```
[Agent Step Start] ──> [Run LLM & Tools] ──> [Capture Result & Token Cost] ──> [Send to DriftGuard SDK] ──> [Get Recommendation] ──> [Adjust context/state if drifting]
```

### MCP Gateway Middleware Pattern
For agents utilizing **Model Context Protocol (MCP)**, a gateway proxy can be set up:
- The agent sends tool execution queries through the MCP Gateway.
- The Gateway logs the target tool, arguments, execution status, and token size.
- If a tool fails, the Gateway logs the error trace and reports it directly to DriftGuard, offering automatic monitoring without codebase modifications.
