# Status and roadmap

This page replaces the older `phases.md` and `PROJECT_HANDOFF.md`. An item is
marked done only when its code path is wired up and covered by tests. The dates
are for planning only; they aren't commitments.

## Product principles

- **Installable, not a repo artifact.** `pip install driftguard` gives you a
  dependency-light SDK. The server is one command or one `docker compose up`.
- **Explain, then act.** The value is in naming the blocking tool, counting the
  wasted tokens, and saying what to do. The dashboard exists to support that
  decision, not to decorate data.
- **Honest boundaries.** DriftGuard sees only what an SDK call, adapter, or
  gateway reports. It doesn't intercept private agent sessions, such as GitHub
  Copilot's, and it never changes prompts or providers on its own.
- **Developer-first.** Integrating should take minutes and work with any LLM
  provider.

## Done

### Phase 1: research foundation (June 2026)
- [x] Synthetic feature-drift model, benchmark against baselines, experiment
  runner, and Markdown reporting. These now live in `research/`.

### Phase 2: SaaS core and SDK (July 2026)
- [x] SDK client with local drift checks and server sync
- [x] FastAPI server with projects, ingestion, alerts, and policy

### Phase 3: agent tool-loop observability (August 2026)
- [x] Agent event schema and ingestion
- [x] Blocking-tool diagnosis and wasted-token accounting

### Phase 4 and 5 foundation rebuild, v0.4.0 (September 2026)
- [x] **Real authentication.** Email and password accounts with scrypt hashing,
  revocable sessions, and hashed project API keys with rotation. The shared
  unauthenticated `default` account is removed, and project-ID takeover is fixed.
- [x] **PostgreSQL that works.** A SQLAlchemy Core layer that CI tests on SQLite
  and PostgreSQL 16, with automatic additive migrations from v0.3.
- [x] **Redis** for rate limits shared across workers (atomic script) and for
  realtime alert fan-out.
- [x] **Live alerts.** WebSocket push that actually works, plus Slack and generic
  webhooks sent off the request path.
- [x] **Automatic alerts.** Critical drift raises alerts with a cooldown. Blocked
  agent tasks raise one alert per task, which stays updated and resolves itself
  when the task recovers.
- [x] **Better diagnosis.** Per-task status (blocked, failing, recovered,
  healthy), recovery detection, a configurable retry window and block
  threshold, redundant-call detection via `input_hash`, and error-specific
  recommendations.
- [x] **Adapters.** `@driftguard_tool` for sync and async code with
  `AgentContext` built on contextvars; token attribution from OpenAI, Anthropic,
  and Gemini responses; MCP session instrumentation and JSON-RPC interception.
- [x] **SDK.** Batched sync that keeps failed batches queued, a bounded queue,
  client-side timestamps, and policy-aware mitigation.
- [x] **Data handling.** A scheduled retention job and scrubbing of credentials
  and PII before storage.
- [x] **Packaging.** An httpx-only SDK with `[server]`, `[postgres]`, `[redis]`,
  and `[research]` extras; a working `driftguard-server` command; a
  multi-stage non-root Docker image; and a compose file.
- [x] **CI.** Lint, a Python 3.10–3.13 matrix, PostgreSQL and Redis tests, the
  dashboard build, and security scans that fail on findings.
- [x] **Dashboard** rebuilt against the real API under the DriftGuard brand:
  sign-in, live alerts, agent diagnosis, and no mock data.

## Next

### Integrations
- [ ] A standalone **MCP gateway** (`driftguard-mcp-proxy`) that sits between
  any MCP client and its servers. This is the most direct way to observe closed
  agents that support MCP.
- [ ] Framework adapters: LangChain/LangGraph callbacks, the OpenAI Agents SDK,
  and the Claude Agent SDK hooks.
- [ ] A JavaScript/TypeScript SDK.
- [ ] A VS Code extension that reports on tools it controls and on MCP traffic.
  It can't read Copilot's private session; see
  [agent-integration.md](agent-integration.md#what-driftguard-cannot-observe).

### Product
- [ ] Trace waterfall view: a timeline of a task's model turns and tool calls.
- [ ] Per-project notification settings (webhooks, email) instead of global
  environment variables.
- [ ] Latency as a first-class metric: ingest `latency_ms` and add a policy rule.
- [ ] Provider pricing profiles, to show wasted tokens as cost.
- [ ] Teams: several users per account, with roles.

### Operations
- [ ] Alembic migrations once the schema needs destructive changes.
- [ ] Integration with an external secret store (Vault, AWS Secrets Manager).
- [ ] Helm chart.
- [ ] OpenTelemetry export of events and alerts.
- [ ] Password reset and email verification. These need an outbound email
  provider.
