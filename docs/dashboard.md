# Dashboard guide

The dashboard is served at the root of your DriftGuard server. Every number on
it comes from the API. A missing value shows as **—**, and an empty list tells
you how to start sending data. Nothing is estimated or filled in by the browser.

## Signing in

Create an account or sign in with an email and password. Administrators can turn
off new sign-ups with `DRIFTGUARD_ALLOW_SIGNUP=false`, which hides the sign-up
form. If your session expires or is revoked, you return to the sign-in screen.

## The header

| Control | What it does |
| --- | --- |
| **Project** | The application being viewed. Use **+** to create a project. Its API key is shown **once**, so copy it. |
| **Environment** | `All`, `prod`, `staging`, `dev`, or `test`. Filters every view. |
| **Time range** | Last 15 minutes up to 30 days, or all. Filters every view. Default: 24 hours. |
| **Live indicator** | State of the realtime connection: **Live**, **Connecting**, **Reconnecting**, or **Offline**. When live, new alerts appear without a refresh, and a new critical alert shows a notification. |
| **Refresh** | Reloads every view. |
| **Test Telemetry** | Sends one event with the four metrics you enter and shows how the server scored it. Use it to check thresholds. It doesn't replace instrumenting your app. |

The dashboard remembers your project and filters in this browser.

## Overview

- **Total events.** Telemetry events in the window, split into critical and
  warning.
- **Open alerts.** Unresolved alerts in the window, split into critical and
  warning. The project **status** is `critical` if any open alert is critical,
  `warning` if any is a warning, and `stable` otherwise.
- **Tokens at stake.** The sum of `saved_tokens` over open alerts. For a
  **drift** alert it's the estimated tokens a mitigation would save
  (`prompt_tokens × savings ratio`). For an **agent** alert it's the tokens
  already spent on the blocked task's failed or redundant attempts. These are
  estimates, not provider invoices.
- **Mean retrieval score / mean response quality.** Averages from 0 to 1 over
  the window. Higher is better. The card shows the policy floor.
- **Mean risk score.** The average of each event's server-computed risk (see
  [scoring](#how-events-are-scored)).
- **Agent Task Diagnosis.** The most urgent agent problem in one sentence: the
  blocking tool, the wasted tokens for that task, and the recommendation.
  **Wasted tokens (all tasks)** adds up every task in the window, so it can be
  larger than the figure in the sentence.
- **Telemetry & Drift Timeline.** Up to the latest 500 events, oldest to newest.
  Prompt tokens use the left axis. Retrieval score and response quality use the
  right axis (0–1). A dashed line marks the prompt-token limit.
- **Drift Risk Breakdown.** The share of events in the window that broke each
  policy rule. The threshold is shown beside each rule.
- **Top Root Causes.** The most frequent causes among warning and critical
  events.
- **Active Alerts.** The five newest open alerts.

## Agent Diagnosis

This view covers tasks reported through agent events (see
[agent-integration.md](agent-integration.md)).

- **Blocked tasks** have an unbroken run of failures of one tool at or above the
  project's *blocked after failures* setting (3 by default).
- **Failing tasks** have a shorter unbroken run.
- **Repeated attempts** are failures that came after an earlier failure in the
  same run: the agent retrying something that just failed.
- **Redundant attempts** are successful calls that repeated input which had
  already succeeded in the same task.
- **Wasted tokens** are the tokens spent on failed attempts plus redundant ones.

The tasks table lists every task, most urgent first. A task's status is
**Blocked**, **Failing**, **Recovered** (it failed, but the same tool later
succeeded), or **Healthy**. Select a task to open its detail panel. It shows the
diagnosis, the recommendation, and every attempt in order, with tool, status,
error, tokens, and duration.

A blocked task also creates an **agent** alert. The alert keeps its wasted-token
count current while the task stays blocked, and resolves itself when the task
recovers.

## Events

This view is the raw telemetry, newest first, 100 rows at a time. **Load more**
fetches older rows, and the search box filters the rows already loaded. Each row
shows the server's scoring: severity, risk, and root cause. Select a row to see
every field, including any `metadata` your app attached.

## Alerts

This view has **Open**, **Resolved**, and **All** tabs, plus a severity filter.
Each alert shows a severity, a source, and the tokens at stake. There are three
sources:

- **drift**: a critical telemetry event. Within the cooldown (15 minutes by
  default), repeats of the same root cause don't create new alerts.
- **agent**: a blocked task. Resolves itself on recovery.
- **manual**: created here with **New alert**, or through the API.

**Resolve** and **Reopen** change an alert's state for everyone on the project.
Resolved alerts stop counting toward the project status and the badge. The
retention job eventually removes them. Open alerts are never pruned.

## Analytics

These charts cover up to the latest 500 events:

- **context length over time**, with the limit marked
- **prompt tokens vs. response quality**, one point per event, shaped and
  coloured by severity. Points moving right and down mean more context is
  costing tokens without improving answers. Treat that as a clue, not proof.
- **retrieval score over time**, with the floor marked
- **severity distribution** for the window

## Policy

These are the project's thresholds. Saving changes how new events are scored and
how the agent diagnosis runs, on the server and in any SDK that calls
`fetch_policy()`. Events already stored keep their original scores.

| Setting | Default | Meaning |
| --- | ---: | --- |
| Prompt token limit | 3000 | Rule broken when `prompt_tokens` is above it. |
| Context length limit | 4000 | Rule broken when `context_length` is above it. |
| Retrieval score floor | 0.50 | Rule broken when `retrieval_score` is below it. |
| Response quality floor | 0.80 | Rule broken when `response_quality` is below it. |
| Blocked after failures | 3 | Consecutive failures of one tool before a task counts as blocked. |
| Retry window (minutes) | 60 | Failures further apart than this start a new run. 0 turns the window off. |

**Reset** discards unsaved edits.

## SDK Integration

This view has copyable Python snippets for the current project and server URL:
install, telemetry, agent events, the decorator, and MCP. The API key appears
only as its prefix (`dg_live_ab12…`). Use the key you saved when you created the
project, or rotate a new one in Project Settings.

## Project Settings

- **Rotate API key** issues a new key, shown once. The old key stops working
  immediately, so update your applications.
- **Delete project** permanently removes the project and all of its telemetry,
  alerts, and policy. To confirm, you type the project ID.

## How events are scored

The server scores every event against the project policy. Each broken rule adds
risk:

| Rule | Risk |
| --- | ---: |
| Prompt token limit | 0.25 |
| Retrieval score floor | 0.35 |
| Context length limit | 0.20 |
| Response quality floor | 0.20 |

The total is capped at 1.0. Below 0.4 is **stable**, 0.4 up to 0.75 is
**warning**, and 0.75 or above is **critical**. A metric you didn't send never
breaks a rule. The recommended actions are:

- `compress_prompt_context` for prompt or context inflation
- `trim_retrieval_results` for retrieval degradation
- `fallback_to_lower_cost_model` for a quality drop

These are **recommendations** for your application. DriftGuard doesn't change
your prompts or providers.

## Metric definitions

- `prompt_tokens`: tokens in the model request's input.
- `context_length`: the total context supplied: conversation history, retrieved
  documents, and the system prompt.
- `retrieval_score`: 0–1 relevance from your RAG pipeline. Send `1.0`, or leave
  it out, if you don't use retrieval.
- `response_quality`: 0–1 from your evaluator, validation checks, or user
  feedback.
- `environment`: `prod`, `staging`, `dev`, or `test`.
