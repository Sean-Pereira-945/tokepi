"""Live DriftGuard demo: drive a running server step by step while the dashboard is open.

    python examples/live_demo.py --email you@example.com --password '...'

Each step waits for Enter so you can narrate what appears on the dashboard.
It recreates a project (``live-demo`` unless ``--project`` says otherwise) each
run, so it starts clean. Pass ``--no-pause`` to run straight through.
"""

# ruff: noqa: S311  (random numbers only fake demo traffic)
from __future__ import annotations

import argparse
import random
import time

import httpx

from driftguard import DriftGuardClient
from driftguard.adapters import AgentContext, driftguard_tool


def pause(message: str, view: str, enabled: bool) -> None:
    print(f"\n==> Next: {message}")
    print(f"    Watch: {view}")
    if enabled:
        input("    Press Enter to run this step...")


def setup_project(base_url: str, email: str, password: str, project_id: str) -> str:
    """Log in, recreate the demo project, and return its API key."""
    with httpx.Client(base_url=base_url, timeout=10) as http:
        login = http.post("/auth/login", json={"email": email, "password": password})
        if login.status_code == 401:
            # First run against a fresh database: create the account.
            login = http.post("/auth/register", json={"name": "Demo", "email": email, "password": password})
        login.raise_for_status()
        auth = {"Authorization": f"Bearer {login.json()['token']}"}
        http.delete(f"/projects/{project_id}", headers=auth)  # 404 on the first run is fine
        created = http.post(
            "/projects",
            json={"project_id": project_id, "name": "Live Demo", "environment": "prod"},
            headers=auth,
        )
        if created.status_code == 409:
            raise SystemExit(f"Project ID '{project_id}' belongs to another account. Pass --project <other-id>.")
        created.raise_for_status()
        return created.json()["api_key"]


def send_telemetry(client: DriftGuardClient, count: int, drifting: bool) -> None:
    for _ in range(count):
        if drifting:
            client.capture_metrics(
                prompt_tokens=random.randint(5000, 6000),
                context_length=random.randint(6000, 7000),
                retrieval_score=round(random.uniform(0.25, 0.35), 2),
                response_quality=round(random.uniform(0.55, 0.65), 2),
            )
        else:
            client.capture_metrics(
                prompt_tokens=random.randint(1000, 1600),
                context_length=random.randint(2000, 3000),
                retrieval_score=round(random.uniform(0.8, 0.95), 2),
                response_quality=round(random.uniform(0.85, 0.95), 2),
            )
    client.sync_metrics()


class FlakyTests:
    """A pretend test runner that fails until it is 'fixed'."""

    fixed = False


@driftguard_tool("search_code")
def search_code(query: str) -> list[str]:
    return ["app/auth.py", "tests/test_auth.py"]


@driftguard_tool("run_tests")
def run_tests(path: str) -> str:
    if not FlakyTests.fixed:
        raise RuntimeError("pytest exited with code 1: test_login_redirect failed")
    return "12 passed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--project", default="live-demo", help="project ID to (re)create")
    parser.add_argument("--no-pause", action="store_true")
    args = parser.parse_args()
    pausing = not args.no_pause

    api_key = setup_project(args.base_url, args.email, args.password, args.project)
    client = DriftGuardClient(api_key=api_key, project_id=args.project, base_url=args.base_url)
    print(f"Project '{args.project}' is ready. Select it in the dashboard.")

    pause("Step 1 of 4, normal traffic (20 healthy LLM calls)", "Overview", pausing)
    send_telemetry(client, 20, drifting=False)
    print("    Sent. The Overview shows healthy scores and no alerts.")

    pause("Step 2 of 4, drift (prompts balloon, retrieval and quality drop)", "Overview and Alerts", pausing)
    send_telemetry(client, 6, drifting=True)
    print("    Sent. A critical drift alert appears live, with its root cause and a recommendation.")

    pause("Step 3 of 4, a coding agent gets stuck retrying the same failing tool", "Agent Diagnosis", pausing)
    with AgentContext(client, task_id="fix-login-bug", auto_sync=True) as ctx:
        search_code("login redirect")
        for _ in range(3):
            ctx.record_llm_usage(prompt_tokens=1800, completion_tokens=400)
            try:
                run_tests("tests/test_auth.py")
            except RuntimeError:
                time.sleep(0.3)
    print("    Sent. Agent Diagnosis marks 'fix-login-bug' BLOCKED and an agent alert fires,")
    print("    showing the tokens wasted on retries.")

    pause("Step 4 of 4, the agent fixes the bug and the tests pass", "Agent Diagnosis and Alerts", pausing)
    FlakyTests.fixed = True
    with AgentContext(client, task_id="fix-login-bug", auto_sync=True):
        run_tests("tests/test_auth.py")
    print("    Sent. The task shows RECOVERED and its alert resolves itself.")

    print("\nDemo complete.")


if __name__ == "__main__":
    main()
