# DriftGuard Dashboard Explainability

This guide explains what each dashboard term means, how it is calculated, and what action it is meant to support.

## How to Read the Dashboard

DriftGuard observes the behavior of an LLM application. It does not choose or call the model. Your application sends telemetry after each model request, whether the provider is Gemini, OpenAI, Anthropic, Ollama, or a custom model.

The core telemetry fields are:

- `prompt_tokens`: Tokens sent in the prompt or input portion of a model request.
- `context_length`: Total context size used for the request, including prompt, conversation history, retrieved documents, and other supplied context.
- `retrieval_score`: A normalized retrieval or relevance score from `0.0` to `1.0`. Higher is better. For a non-RAG application, use an application-specific quality signal or `1.0` when retrieval does not apply.
- `response_quality`: A normalized quality score from `0.0` to `1.0`, produced by your evaluator, user feedback, validation checks, or another application signal.
- `environment`: The deployment label for the event, such as `prod`, `staging`, `dev`, or `test`.

### Which API key is used?

Each project receives a **DriftGuard project API key** when it is created. Put that
key in the dashboard's `DRIFTGUARD API KEY` field or configure it in
`DriftGuardClient`. The key scopes telemetry to one project. A user's Gemini,
OpenAI, Anthropic, or other provider key stays in the user's application and is
never sent to or stored by DriftGuard.

## Header Controls

### Project

The project is the application whose telemetry is being displayed. Changing it reloads events, alerts, summaries, and charts for that project.

### Environment

The environment identifies where the application is running. It is attached to newly submitted test telemetry and labels the dashboard view. The current backend event listing is project-scoped, so environment selection is primarily a monitoring and event-labeling context rather than a separate database filter.

### Refresh

Reloads the current project's summary, recent events, alerts, and charts from the backend.

### Test Telemetry

Opens a form that submits one authenticated sample event through the dashboard. It is useful for checking the integration and seeing how a high-token, low-quality event changes monitoring data. It is not a replacement for instrumenting the real LLM application.

## Navigation Sections

### Overview

The operational summary. Use it to answer: Are requests being recorded, is quality changing, are alerts accumulating, and are mitigation signals appearing?

### Alert Feed

The complete list of stored drift alerts for the selected project. Each row contains the alert severity, diagnostic message, estimated savings, and current display context.

### Drift Analytics

Charts for exploring relationships between context growth, token usage, and response quality. Use this section to look for trends rather than treating one point as proof of a problem.

### Mitigation Rules

The project's policy thresholds. These values define when the client-side drift evaluator considers a metric outside its normal operating band.

### SDK Integration

A provider-neutral example showing how to capture metrics after an existing model call and synchronize them with DriftGuard.

## Overview Metrics

### Total Telemetry Events

The number of recent telemetry events returned for the selected project. The API currently returns up to 100 recent events, so this is a recent-window count rather than a lifetime total.

A value of `0` means DriftGuard has not received any events in the returned window. It does not mean the LLM application has made zero lifetime requests.

### Saved Tokens / Cost

The sum of `saved_tokens` recorded on the project's alerts. The displayed cost estimate uses the dashboard's fixed approximation of `$0.00002` per saved token.

This is an estimate, not a provider invoice. Actual savings depend on the model, provider pricing, cached requests, and the mitigation that was ultimately applied.

### Active Alerts

The number of alerts stored for the selected project. An alert is a recorded signal that an application condition needs attention.

The dashboard currently treats all returned alerts as active; there is no resolved-alert state in the current data model.

### Critical Alerts

The count of alerts whose severity is `critical` or `warning` in the dashboard's current summary wording. Critical conditions require the fastest response; warnings indicate a meaningful deviation that should be investigated.

### Mean Retrieval Score

The arithmetic mean of `retrieval_score` across the returned telemetry events. Scores near `1.0` indicate stronger retrieval relevance; scores near `0.0` indicate weaker relevance.

The displayed `0.50` floor is the default policy threshold. A project can change it in Mitigation Rules.

## Charts

### Telemetry & Drift Timeline

The line chart compares three series across recent events:

- **Prompt Tokens**: Input token volume. A rising line can indicate prompt growth or context bloat.
- **Retrieval Score**: Retrieval relevance from `0.0` to `1.0`. A falling line can indicate noisier or less relevant retrieved context.
- **Quality Score**: Response quality from `0.0` to `1.0`. A falling line can indicate degraded answers, validation failures, or user dissatisfaction.

The series use separate axes: prompt tokens use the left axis, while normalized scores use the right axis. This prevents token counts from visually flattening the quality signals.

### Drift Risk Breakdown

The radar labels represent possible risk dimensions:

- **Prompt Drift**: Change or growth in prompt content or prompt token volume.
- **Retrieval Shift**: Change in retrieval relevance or retrieved context behavior.
- **Quality Loss**: Decline in response quality.
- **Context Bloat**: Growth beyond the intended context window or context policy.
- **Latency Risk**: Operational risk associated with larger prompts, retrieval work, or model response time.

The radar is calculated from the selected project's live events. Prompt and context
risk are compared with the default thresholds, retrieval and quality are inverted
into risk, and latency risk is shown as unavailable because latency is not currently
ingested. It is a directional diagnostic, not a calibrated probabilistic score.

### Context Length Distribution

Shows `context_length` across recent events. A sustained increase can signal conversation history accumulation, excessive retrieved documents, or prompt assembly growth.

### Tokens vs Quality Correlation

Plots `prompt_tokens` on the horizontal axis and `response_quality` on the vertical axis. Points moving right while moving down suggest that more context is costing tokens without improving results.

Correlation is a diagnostic clue, not proof of causation. Compare it with retrieval quality, latency, model changes, and application behavior.

## Alerts and Severity

### Stable

The observed values remain within the configured baseline bands, or no action is currently recommended.

### Warning

The application has a meaningful drift signal. Investigate the related metric and consider the recommended mitigation before the condition affects users or cost materially.

### Critical

Multiple or severe drift signals are present. Prioritize investigation and mitigation because quality, context size, or cost may be outside acceptable operating limits.

Alert diagnostics can mention root causes such as:

- **Prompt context inflation**: Prompt tokens or context length exceeded their limits.
- **Retrieval degradation**: Retrieval score fell below its floor.
- **Trajectory quality degradation**: Response quality fell below its floor.

## Automated Mitigation Status

These tiles describe the mitigation concepts DriftGuard is designed to use:

- **Semantic Cache**: Reuse a suitable prior result for semantically similar requests to reduce latency and cost.
- **Prompt Compression**: Reduce unnecessary prompt or history content while preserving useful context.
- **Fallback Model Routing**: Send suitable non-critical requests to a lower-cost or alternate model.
- **Strict Output Parsing**: Validate and constrain model output against an expected structure.

`ACTIVE`, `STANDBY`, and `DISABLED` are currently dashboard status labels. They are not interactive switches, and the current UI does not execute these four actions automatically from the tiles.

## Mitigation Rules and Defaults

The default policy is:

| Rule | Default | Meaning |
| --- | ---: | --- |
| Prompt Token Limit | `3000` | Warn when `prompt_tokens` is greater than this value. |
| Context Length Limit | `4000` | Warn when `context_length` is greater than this value. |
| Retrieval Score Floor | `0.50` | Warn when `retrieval_score` is below this value. |
| Response Quality Floor | `0.80` | Warn when `response_quality` is below this value. |

The client adds risk contributions for each violated rule:

- Prompt token limit: `0.25`
- Retrieval score floor: `0.35`
- Context length limit: `0.20`
- Response quality floor: `0.20`

The combined risk is capped at `1.0`. Client severity is `stable` below `0.4`, `warning` from `0.4` through `0.749`, and `critical` at `0.75` or above.

The mitigation recommender may suggest:

- `compress_prompt_context`
- `trim_retrieval_results`
- `fallback_to_lower_cost_model`
- `no_action_required`

These are recommendations for the host application. DriftGuard does not silently modify prompts or switch providers on its own.

## Provider Integration

The integration contract is provider-neutral:

1. Call Gemini, OpenAI, Anthropic, Ollama, or your own model as usual.
2. Map the provider's usage metadata and your quality signals to the four telemetry fields.
3. Call `client.capture_metrics(...)`.
4. Call `client.check_drift()` for a local recommendation.
5. Call `client.sync_metrics(project_id)` to send events to the dashboard.

For Gemini, `response.usage_metadata.prompt_token_count` can provide `prompt_tokens`, and `response.usage_metadata.total_token_count` can provide `context_length` when those fields are available. Retrieval and response quality must come from your RAG pipeline or evaluation layer.

## Evidence and Limitations

- Empty KPI values are live zeros, not invented historical totals.
- Empty alert panels and charts explicitly show that no project data is available.
- The dashboard does not currently expose request latency as an ingested metric, even though latency risk appears as a radar concept.
- Saved cost is an estimate based on alert metadata and a fixed approximation.
- A drift alert is a signal for investigation, not a claim that the model is objectively incorrect.

## Agent and Tool Observability Status

The current release now accepts task IDs, trace IDs, tool names, tool-call IDs,
attempt numbers, failure types, error messages, and token counts through the agent
event API and SDK methods. It can diagnose repeated failed attempts and estimate
wasted tokens. It still cannot automatically obtain these events from GitHub
Copilot or another private agent session.

The required next event contract is:

```json
{
	"task_id": "implement-login",
	"trace_id": "task-123",
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

An agent adapter, VS Code extension, MCP gateway, or other host integration must
emit these events. DriftGuard cannot obtain GitHub Copilot's private tool history
from the dashboard alone.
