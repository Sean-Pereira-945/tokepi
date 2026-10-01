"""Fill a DriftGuard project with a week of varied, realistic sample data.

    python examples/seed_showcase.py --api-key dg_live_... --project-id showcase

Every dashboard view gets something to show:

* **Overview, Events, Analytics:** about 450 LLM requests over 7 days in
  prod, staging and dev, from four models. Most are healthy. There are three
  drift episodes, each building from warnings to a peak: prompt bloat in prod
  about a day ago, a retrieval regression in staging this morning, and
  retrieval and answer quality slipping in prod in the last hour.
* **Alerts:** drift alerts with different root causes, plus agent alerts that
  are open (blocked tasks) and resolved (a task that recovered).
* **Agent Diagnosis:** five agents, with tasks that are blocked, failing,
  recovered, healthy and redundant.
* **Logs:** tool calls with their command, output or error, duration and
  tokens, and one ``response`` per finished task with the prompt, the answer,
  the task's duration and its tokens. Inputs and outputs appear if the project
  has content storage on.

It uses only the project API key, so it works on any project. Run it on an
empty project; running it twice doubles the data.
"""

from __future__ import annotations

# ruff: noqa: S311  (random numbers only generate sample data)
import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

NOW = datetime.now(timezone.utc)
MODELS = ["gpt-4o", "claude-opus", "gemini-2.5-pro", "kimi-k2"]
ROUTES = ["/chat", "/search", "/summarize", "/support"]


def ts(delta: timedelta) -> str:
    return (NOW - delta).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# LLM telemetry
# ---------------------------------------------------------------------------


def healthy(rng: random.Random) -> dict[str, Any]:
    return {
        "prompt_tokens": rng.randint(700, 2200),
        "context_length": rng.randint(1500, 3200),
        "retrieval_score": round(rng.uniform(0.72, 0.95), 3),
        "response_quality": round(rng.uniform(0.83, 0.97), 3),
    }


def _request(rng: random.Random, env: str, age: timedelta, **overrides: Any) -> dict[str, Any]:
    return {
        **healthy(rng),
        **overrides,
        "environment": env,
        "occurred_at": ts(age),
        "metadata": {"model": rng.choice(MODELS), "route": rng.choice(ROUTES), "request_id": uuid.uuid4().hex[:12]},
    }


def _episode(
    rng: random.Random, env: str, start_h: float, end_h: float, peak: tuple[float, float], warn: Any, crit: Any
) -> list[dict[str, Any]]:
    """Dense traffic for one drift episode: warnings throughout, critical requests at the peak."""
    events = []
    minutes = start_h * 60
    while minutes > end_h * 60:
        minutes -= rng.randint(5, 9)
        hours = minutes / 60
        broken = crit(rng) if peak[1] <= hours <= peak[0] else warn(rng)
        events.append(_request(rng, env, timedelta(minutes=minutes), **broken))
    return events


def telemetry(rng: random.Random) -> list[dict[str, Any]]:
    events = []
    # Background traffic for 7 days, mostly healthy, with occasional one-off warnings.
    minutes = 7 * 24 * 60
    while minutes > 0:
        minutes -= rng.randint(20, 40)
        env = rng.choices(["prod", "staging", "dev"], weights=[6, 3, 1])[0]
        overrides: dict[str, Any] = {}
        if rng.random() < 0.05:
            overrides = {"prompt_tokens": rng.randint(3100, 3900), "context_length": rng.randint(4100, 4800)}
        events.append(_request(rng, env, timedelta(minutes=minutes), **overrides))

    def bloat(r: random.Random) -> dict[str, Any]:
        return {"prompt_tokens": r.randint(3300, 4800), "context_length": r.randint(4200, 6500)}

    def retrieval(r: random.Random) -> dict[str, Any]:
        return {"retrieval_score": round(r.uniform(0.25, 0.47), 3), "response_quality": round(r.uniform(0.6, 0.78), 3)}

    # Episode 1, prod, about a day ago: prompts and context grow (warning), then
    # retrieval also collapses (critical: inflation + retrieval).
    events += _episode(
        rng, "prod", 27, 22, (25, 24), bloat, lambda r: {**bloat(r), "retrieval_score": round(r.uniform(0.2, 0.4), 3)}
    )
    # Episode 2, staging, this morning: a retrieval regression (warning) that also
    # bloats prompts at its worst (critical: inflation + retrieval + quality).
    events += _episode(
        rng, "staging", 9, 5, (7, 6), retrieval, lambda r: {**retrieval(r), "prompt_tokens": r.randint(3300, 4400)}
    )
    # Episode 3, prod, the last hour: answer quality and retrieval slipping (warning).
    events += _episode(rng, "prod", 1, 0.1, (0, 0), retrieval, retrieval)
    events.sort(key=lambda e: e["occurred_at"])
    return events


# ---------------------------------------------------------------------------
# Agent activity
# ---------------------------------------------------------------------------


class Session:
    """Builds the events of one agent run the way the Claude Code hook reports them.

    Every tool call carries its duration, the tokens of the model call that
    issued it, and its output (or error). A finished run ends with one
    ``response`` event: the prompt, the answer, the run's duration and its tokens.
    """

    def __init__(self, agent: str, model: str, env: str, task_id: str, start: timedelta) -> None:
        self.agent, self.model, self.env, self.task_id = agent, model, env, task_id
        self.trace_id = f"run-{uuid.uuid4().hex[:8]}"
        self.started = self.age = start
        self.attempts: dict[str, int] = {}
        self.pending = (0, 0)
        self.tokens = [0, 0]
        self.prompt = ""
        self.events: list[dict[str, Any]] = []

    def _emit(self, step_seconds: float, **fields: Any) -> None:
        self.age -= timedelta(seconds=step_seconds)
        self.events.append(
            {
                "task_id": self.task_id,
                "trace_id": self.trace_id,
                "agent_name": self.agent,
                "model": self.model,
                "environment": self.env,
                "occurred_at": ts(self.age),
                **fields,
            }
        )

    def start(self, prompt: str) -> Session:
        self.prompt = prompt
        return self

    def think(self, prompt_tokens: int, completion_tokens: int) -> Session:
        """A model turn; its tokens are attributed to the next tool call."""
        self.pending = (self.pending[0] + prompt_tokens, self.pending[1] + completion_tokens)
        self.age -= timedelta(seconds=random.uniform(2, 9))
        return self

    def tool(
        self,
        name: str,
        status: str,
        args: Any,
        *,
        output: str | None = None,
        error: tuple[str, str] | None = None,
        tokens: int = 0,
        seconds: int = 20,
    ) -> Session:
        self.attempts[name] = self.attempts.get(name, 0) + 1
        prompt_tokens, completion_tokens = self.pending
        if tokens:
            prompt_tokens, completion_tokens = prompt_tokens + int(tokens * 0.8), completion_tokens + int(tokens * 0.2)
        if not prompt_tokens and not completion_tokens:
            prompt_tokens, completion_tokens = random.randint(350, 1400), random.randint(60, 320)
        self.pending = (0, 0)
        self.tokens[0] += prompt_tokens
        self.tokens[1] += completion_tokens
        duration = random.randint(400, 9000) if status == "success" else random.randint(1500, 30000)
        fields: dict[str, Any] = {
            "tool_name": name,
            "status": status,
            "attempt": self.attempts[name],
            "input": args if isinstance(args, str) else json.dumps(args),
            "input_hash": uuid.uuid5(uuid.NAMESPACE_OID, f"{name}{args}").hex[:16],
            "duration_ms": duration,
            "tool_call_id": f"toolu_{uuid.uuid4().hex[:20]}",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        if error:
            fields["error_type"], fields["error_message"] = error
            fields["output"] = error[1]
        else:
            fields["output"] = output or "ok"
        self._emit(seconds + duration / 1000, **fields)
        return self

    def finish(self, answer: str) -> Session:
        prompt_tokens = self.tokens[0] + self.pending[0] + random.randint(300, 900)
        completion_tokens = self.tokens[1] + self.pending[1] + random.randint(120, 400)
        self._emit(
            random.uniform(3, 8),
            kind="response",
            status="success",
            input=self.prompt,
            output=answer,
            duration_ms=round((self.started - self.age).total_seconds() * 1000),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return self


def finished_sessions() -> list[dict[str, Any]]:
    """Healthy, recovered and redundant runs from earlier today."""
    runs = [
        Session("claude-code", "claude-opus", "dev", "refactor-auth-module", timedelta(hours=9))
        .start("Split auth.py into a token module and a session module")
        .think(4200, 900)
        .tool("Read", "success", "app/auth.py", output="412 lines")
        .tool("Edit", "failed", "app/auth.py", error=("patch_rejected", "old_string not found in file"), tokens=1300)
        .think(1500, 300)
        .tool("Edit", "success", "app/auth.py", output="1 replacement", tokens=900)
        .tool("Bash", "success", "pytest tests/test_auth.py -q", output="18 passed in 2.1s")
        .finish("Moved token handling to app/tokens.py; all auth tests pass."),
        Session("research-agent", "gpt-4o", "prod", "summarize-q3-report", timedelta(hours=7))
        .start("Summarise the Q3 report and list the three biggest risks")
        .think(6100, 700)
        .tool("search_docs", "success", "q3 risks", output="5 documents")
        .tool("search_docs", "success", "q3 risks", output="5 documents", tokens=1100)
        .tool("search_docs", "success", "q3 risks", output="5 documents", tokens=1100)
        .think(8800, 1400)
        .finish("Summary drafted: supply costs, churn in EU, delayed launch."),
        Session("support-bot", "gemini-2.5-pro", "prod", "ticket-48213", timedelta(hours=5))
        .start("Customer cannot reset their password")
        .think(1800, 250)
        .tool("crm_lookup", "success", {"ticket": 48213}, output="plan=pro, region=EU")
        .tool("send_reset_email", "success", {"user": "u_9921"}, output="queued")
        .finish("Sent a password reset link and closed the ticket."),
        Session("kimi-coder", "kimi-k2", "staging", "add-rate-limit-tests", timedelta(hours=4, minutes=40))
        .start("Add tests for the login rate limiter")
        .think(3900, 1200)
        .tool("Write", "success", "tests/test_rate_limit.py", output="created, 64 lines")
        .tool("Bash", "success", "pytest tests/test_rate_limit.py", output="4 passed")
        .finish("Added 4 tests covering the per-IP login limit."),
    ]
    return [event for run in runs for event in run.events]


def live_problems() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recent runs: two blocked, one failing, and one blocked task that recovers later.

    Returns ``(now, later)``; ``later`` is sent separately so its alert is first
    raised and then resolved.
    """
    timeout = ("timeout", "Navigation timeout of 30000 ms exceeded")
    deploy = (
        Session("ops-agent", "gpt-4o", "staging", "deploy-staging", timedelta(minutes=50))
        .start("Deploy release 2.4.1 to staging")
        .think(2600, 400)
    )
    for _ in range(4):
        deploy.tool(
            "kubectl",
            "failed",
            "kubectl apply -f k8s/staging.yaml",
            error=("forbidden", 'deployments.apps "api" is forbidden: User "ci-bot" cannot patch resource'),
            tokens=2100,
            seconds=45,
        )
    flaky = (
        Session("claude-code", "claude-opus", "dev", "fix-flaky-test", timedelta(minutes=35))
        .start("test_checkout_total fails on CI but not locally, fix it")
        .think(5200, 800)
    )
    for _ in range(3):
        flaky.tool(
            "Bash",
            "failed",
            "pytest tests/test_checkout.py::test_checkout_total",
            error=("exit_1", "AssertionError: assert 99.99000000000001 == 99.99"),
            tokens=2400,
            seconds=60,
        )
    scraper = (
        Session("research-agent", "gemini-2.5-pro", "prod", "scrape-competitor-pricing", timedelta(minutes=25))
        .start("Collect current pricing from the three competitor sites")
        .think(2100, 300)
        .tool("browser", "success", "https://example.com/pricing", output="3 plans found")
        .tool("browser", "failed", "https://example.org/pricing", error=timeout, tokens=900)
        .tool("browser", "failed", "https://example.org/pricing", error=timeout, tokens=900)
    )
    migrate = (
        Session("kimi-coder", "kimi-k2", "staging", "migrate-orders-table", timedelta(minutes=70))
        .start("Add a currency column to orders and backfill it")
        .think(3300, 600)
    )
    for _ in range(3):
        migrate.tool(
            "psql",
            "failed",
            "ALTER TABLE orders ADD COLUMN currency text NOT NULL",
            error=("not_null_violation", 'column "currency" of relation "orders" contains null values'),
            tokens=1500,
            seconds=50,
        )
    now = deploy.events + flaky.events + scraper.events + migrate.events
    before = len(migrate.events)
    migrate.think(2400, 500).tool(
        "psql", "success", "ALTER TABLE orders ADD COLUMN currency text DEFAULT 'USD'", output="ALTER TABLE"
    )
    migrate.finish("Added orders.currency with a USD default; backfill complete.")
    return now, migrate.events[before:]


# ---------------------------------------------------------------------------


def post(http: httpx.Client, path: str, events: list[dict[str, Any]]) -> int:
    total = 0
    for start in range(0, len(events), 500):
        response = http.post(path, json={"events": events[start : start + 500]})
        response.raise_for_status()
        total += response.json()["ingested"]
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True, help="the project's dg_live_ API key")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--seed", type=int, default=7, help="random seed, for repeatable data")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    random.seed(args.seed)

    with httpx.Client(base_url=args.base_url, headers={"X-API-Key": args.api_key}, timeout=30) as http:
        pid = args.project_id
        n_events = post(http, f"/events/{pid}/batch", telemetry(rng))
        n_finished = post(http, f"/agent-events/{pid}/batch", finished_sessions())
        now, later = live_problems()
        n_live = post(http, f"/agent-events/{pid}/batch", now)
        n_later = post(http, f"/agent-events/{pid}/batch", later)
        alerts = http.get(f"/projects/{pid}/alerts").json()
        diagnosis = http.get(f"/projects/{pid}/agent-diagnosis", params={"time_range": "24h"}).json()

    print(f"Telemetry events: {n_events}")
    print(f"Agent events:     {n_finished + n_live + n_later}")
    statuses: dict[str, int] = {}
    for task in diagnosis["tasks"]:
        statuses[task["status"]] = statuses.get(task["status"], 0) + 1
    print(f"Agent tasks:      {dict(sorted(statuses.items()))}")
    open_alerts = sum(1 for a in alerts if not a["resolved"])
    print(f"Alerts:           {len(alerts)} ({open_alerts} open, {len(alerts) - open_alerts} resolved)")


if __name__ == "__main__":
    main()
