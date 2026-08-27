# DriftGuard Project Handoff

This document captures the current project state, delivery scope, architecture, critical decisions, and the next actions so that future AI agents or collaborators can continue without losing context.

## 1. Product goal

DriftGuard is a developer-facing observability and cost-protection product for LLM applications and AI coding agents. Its purpose is to detect when an agent repeatedly fails at a task or tool call, measure tokens consumed by failed or redundant attempts, identify the failing tool, and give the developer an actionable explanation. The current release provides the project API, telemetry storage, threshold-based drift checks, agent/tool retry analysis, and dashboard. The remaining integration gap is connecting these APIs to a real agent runtime.

The primary product model is:
- Python SDK installed into developer apps
- Hosted SaaS dashboard for monitoring and analysis
- Optional self-hosted or enterprise deployment later

## 2. Current status

The project is now in a launch-ready telemetry foundation stage:
- SDK-level drift checks are implemented
- mitigation and token-saving recommendations are implemented
- benchmark and experiment workflow exists
- reporting output is available for research or product summaries
- tests pass for the current functionality (including the new dashboard metrics validation suite)
- project API-key isolation and live dashboard data are implemented
- dashboard connected to metrics and filtering APIs (environment, severity, time range)
- complete backend codebase docstring documentation added
- first agent task/tool/retry diagnosis slice is implemented; provider and IDE adapters are not
- agent wrappers, MCP gateway integrations, and VS Code/Copilot event integrations are not implemented

## 3. Current deliverables in the repo

### Core product
- `driftguard/client.py` — developer SDK for telemetry capture and drift detection
- `driftguard/mitigation.py` — mitigation recommendation engine and token-savings logic
- `driftguard/routes.py` — FastAPI backend, project API keys, ingestion, and dashboard data/filtering routes
- `driftguard/service.py` — persistent database service logic
- `driftguard/static/` — live dashboard assets (with interactive filtering and explorer workflows)

### Research and validation layer
- `driftguard/data.py` — synthetic dataset generation and drift modeling
- `driftguard/detector.py` — drift scoring logic
- `driftguard/benchmark.py` — benchmark scenarios and scoring comparison
- `driftguard/experiment.py` — reproducible experiment runner
- `driftguard/reporting.py` — markdown and summary generation for results

### Supporting docs and configuration (in `docs/`)
- `README.md` (root) — product overview and launch context
- `requirements.txt` (root) — package dependencies
- `pyproject.toml` (root) — project metadata and build configuration
- `tests/` — implementation validation suite (including dashboard metrics tests)
- `docs/PROJECT_HANDOFF.md` — handoff document and roadmap
- `docs/QUICKSTART.md` — developer onboarding and quickstart guide
- `docs/explainability.md` — dashboard metrics and terms overview
- `docs/setup_on_agent.md` — coding agent adapter integration guide
- `docs/architecture_and_design.md` — system architecture details
- `docs/phases.md` — development roadmap phases

## 4. Product architecture

### SDK / developer integration
The developer-facing SDK is the current integration point. It lets developers:
- initialize DriftGuard with project metadata and environment
- send runtime metrics like prompt_token usage, context length, retrieval score, and response quality
- trigger drift checks or health evaluation
- receive recommendations and mitigation actions

For the intended agent product, this integration must be extended to emit one event
for each agent task, model turn, tool call, retry, result, and failure. The host
agent or an adapter must provide those events; DriftGuard cannot inspect GitHub
Copilot's private session or tools automatically.

Implemented SDK methods:
- `capture_agent_event(...)` — queue one structured task/tool attempt
- `sync_agent_events(project_id)` — send queued attempts using the project API key
- `fetch_agent_diagnosis(project_id)` — retrieve failure and retry analysis

Adapter options:
- **Agent wrapper** — recommended first path; wrap the model and tool loop
- **MCP gateway** — observe MCP tools routed through the gateway
- **VS Code extension** — use public editor or agent events when available
- **Provider or agent integration** — use an official event hook when available

An MCP gateway or wrapper can observe tools routed through it, but it cannot reveal
private GitHub Copilot conversation state or hidden token usage that the host does
not expose.

### Backend / SaaS service
The hosted service currently provides:
- project and environment management
- event ingestion from SDK clients
- alert creation and severity evaluation
- root-cause summaries and trend history
- token-savings and mitigation tracking
- dashboard data endpoints

The current hosted service additionally provides:
- task and trace fields on agent events
- tool-call and retry event storage
- failed/redundant token accounting
- blocking-tool diagnosis
- developer-facing diagnosis data for the dashboard

It still needs push notifications, richer task correlation, configurable retry
windows, and production adapters.

### Dashboard UI
The dashboard should display:
- alert feed
- drift severity timeline
- token savings impact
- root-cause explanations
- environment/project filters
- agent task diagnosis
- failed and repeated attempt counts
- wasted-token totals
- blocking tool and recommendation

## 5. Product value proposition

The product should be positioned as:

Agent and LLM observability that explains failed tool loops and protects against wasted tokens.

It solves the problem of:
- quality degradation in AI applications over time
- unnecessary token usage and cost spikes
- poor visibility into why behavior changed
- lack of actionable mitigation guidance
- repeated failed agent requests that consume tokens without advancing the task
- poor visibility into which connected tool is blocking an agent

## 6. Primary customer type

The primary customers are developers and teams building AI-enabled products that:
- use LLMs in production
- rely on prompt engineering and retrieval systems
- face variable context, token usage, and response quality
- want automated drift monitoring and cost protection

## 7. Launch strategy

The preferred launch path is:
1. Python package for devs
2. Hosted dashboard for alert monitoring
3. SaaS analytics for projects and environments
4. team/enterprise controls later

The product is not a repo-only monitor. It requires an SDK, agent adapter, or tool
gateway in the execution path. A future VS Code extension or MCP gateway may make
this easy for coding agents, but the current repository does not intercept Copilot.

## 8. Current technical truths

The project currently has working functionality validated by tests:
- drift scoring works
- mitigation recommendations are generated
- benchmark scenarios run
- project reporting can generate summary outputs
- the system is in a valid launch foundation state

Current verified status:
- `pytest` passes for the current test suite
- live dashboard data is project-scoped by DriftGuard API key
- agent/tool retry events and wasted-token calculations are implemented
- the dashboard shows the current agent diagnosis
- no automatic GitHub Copilot interception exists

## 9. Key design decisions

### Why package-first
A developer can integrate DriftGuard with minimal friction via a simple install and SDK call pattern, rather than requiring a full infrastructure clone or repo-level integration.

### Why hosted dashboard
The dashboard is needed for the operational story: visibility, root-cause insight, alerts, and policy review. This complements the SDK rather than replacing it.

### Why mitigation layer matters
The product is not just monitoring; it also reduces risk and token waste. This is a strong business and customer value proposition.

## 10. What Is Done

- SDK drift metrics and local drift checks
- Project creation and generated project API keys
- Project-scoped dashboard reads and writes
- Persistent LLM telemetry event storage
- Alert and policy APIs
- Structured agent task/tool event schema
- API-key-authenticated agent-event ingestion
- Retry and failed-attempt analysis
- Blocking-tool diagnosis and wasted-token calculation
- Agent Task Diagnosis dashboard panel
- SDK methods for agent event capture, synchronization, and diagnosis retrieval
- Documentation for the product boundary and adapter architecture
- Automated tests for the agent diagnosis slice

## 11. What Is Needed

- Build an agent wrapper for the first supported coding-agent runtime
- Build an MCP gateway integration for tools that use MCP
- Investigate public VS Code/Copilot event hooks before claiming Copilot support
- Add streaming or push notifications for newly blocked tasks
- Add configurable retry windows and duplicate-attempt detection
- Add richer task completion and successful-attempt analysis
- Add provider-specific token usage adapters
- Add production authentication, secret rotation, TLS, and deployment hardening
- Add retention, privacy, and deletion controls for agent traces and errors
- Package and publish the SDK with a stable agent-event API

## 12. Critical implementation priorities next

The next build phase should focus on launch readiness:

1. Package publication setup
   - build packaging metadata
   - versioning and release process
   - install and distribution workflow

2. SaaS backend and project management
   - project creation and environment models
   - event ingestion endpoints
   - alert persistence and history

3. Dashboard polish
   - summary cards, alerts, charts, policy configuration
   - root-cause drill-down views

4. Alert automation and mitigation execution
   - configurable rules
   - action execution pipeline
   - expected savings reporting

5. Agent and tool observability expansion
   - add richer task/trace correlation and successful-attempt analysis
   - add provider, IDE, and MCP adapters for coding agents
   - add streaming or push notifications for blocked tasks
   - add configurable waste windows and deduplication rules

6. Security and production hardening
   - API auth
   - environment isolation
   - rate limiting and validation

7. Onboarding and docs
   - install guide
   - quickstart tutorial
   - dashboard walkthrough
   - pricing / usage model

## 13. What should not be lost

These are the important product truths to protect:
- the product is practical and installable, not a repo-only artifact
- the dashboard exists to support understanding and action, not just visualization
- root-cause analysis is central to usefulness
- cost savings and token management are a major product value
- the project must stay developer-centric and fast to adopt

## 14. Suggested next immediate work

The immediate next implementation should focus on:
- packaging the SDK for release
- creating a proper backend service contract
- adding project/environment storage
- building alert and mitigation APIs
- creating the hosted dashboard shell with core screens
- building the first local agent wrapper around terminal, file, browser, and API tools
- adding an end-to-end sample that produces a blocked-task diagnosis
- adding a VS Code or MCP feasibility spike based on available public hooks

## 15. Handoff note

This project is no longer just a research prototype. It is a product concept in active build toward a package + SaaS launch model. The first diagnosis slice is shipped and tested. The product north star is agent/tool failure explainability and wasted-token protection; the next proof point is a real adapter that observes an agent's tools and sends these events without manual instrumentation per call.
