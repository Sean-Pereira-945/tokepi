import { KeyRound } from 'lucide-react';
import { Button } from '../components/Button';
import { CodeBlock } from '../components/Copy';
import { PageHeader, Panel } from '../components/Panel';
import type { ViewId } from '../lib/route';
import { useProject } from '../state/workspace';

function pyString(value: string): string {
  return JSON.stringify(value);
}

export function SdkIntegration({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const project = useProject();
  const baseUrl = window.location.origin;
  const keyHint = `${project.api_key_hint}…`;

  const client = `import os
from driftguard import DriftGuardClient

client = DriftGuardClient(
    api_key=os.environ["DRIFTGUARD_API_KEY"],  # ${keyHint}
    project_id=${pyString(project.project_id)},
    environment=${pyString(project.environment)},
    base_url=${pyString(baseUrl)},
)`;

  const metrics = `# After each LLM request, record normalized telemetry.
client.capture_metrics(
    prompt_tokens=5200,
    context_length=6100,
    retrieval_score=0.31,
    response_quality=0.62,
)

# Optional: pull this project's policy, then score locally (works offline).
client.fetch_policy()
result = client.check_drift()
print(result["severity"], result["risk_score"], result["root_cause"])

# Send queued telemetry to DriftGuard.
client.sync_metrics()`;

  const agent = `# Record one event per tool attempt.
client.capture_agent_event(
    task_id="fix-tests",
    tool_name="terminal",
    status="failed",
    attempt=2,
    error_type="command_failed",
    error_message="pytest exited with code 1",
    total_tokens=2200,
    duration_ms=5120,
)
client.sync_agent_events()

diagnosis = client.fetch_agent_diagnosis()
print(diagnosis["diagnosis"])
print("Blocking tool:", diagnosis["blocking_tool"], "| wasted tokens:", diagnosis["wasted_tokens"])`;

  const adapter = `from driftguard.adapters import AgentContext, driftguard_tool

@driftguard_tool()
def run_tests(path: str) -> str:
    ...  # exceptions are recorded as failures and re-raised

with AgentContext(client, task_id="fix-tests") as run:
    response = llm.messages.create(...)   # your model call
    run.record_llm_usage(response)        # tokens attach to the next tool event
    run_tests("tests/")

client.sync_agent_events()`;

  const mcp = `from driftguard.adapters import MCPMiddleware

# session is an MCP ClientSession
middleware = MCPMiddleware(client, task_id="fix-tests")
session = middleware.instrument_session(session)

result = await session.call_tool("terminal", {"command": "pytest"})
client.sync_agent_events()`;

  return (
    <>
      <PageHeader
        title="SDK Integration"
        description={
          <>
            Python examples for <span className="font-mono text-body">{project.project_id}</span>. Your application sends
            telemetry and agent events; DriftGuard doesn’t intercept model or agent traffic.
          </>
        }
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <Panel title="1. Install and configure">
            <div className="space-y-4">
              <CodeBlock code="pip install driftguard" title="shell" language="shell" />
              <CodeBlock code={client} title="client.py" />
            </div>
          </Panel>
          <Panel title="2. LLM telemetry" description="capture_metrics, check_drift and sync_metrics.">
            <CodeBlock code={metrics} title="telemetry.py" />
          </Panel>
          <Panel title="3. Agent events" description="capture_agent_event, sync_agent_events and fetch_agent_diagnosis.">
            <CodeBlock code={agent} title="agent_events.py" />
          </Panel>
          <Panel title="4. Python agent adapter" description="Attribute decorated tool calls to a task automatically.">
            <CodeBlock code={adapter} title="adapter.py" />
          </Panel>
          <Panel title="5. MCP adapter" description="Record every tools/call made through an MCP client session.">
            <CodeBlock code={mcp} title="mcp_client.py" />
          </Panel>
        </div>
        <aside className="space-y-4">
          <Panel title="Project API key">
            <div className="space-y-3 text-[13px] text-muted">
              <p>
                Current key: <code className="font-mono text-cyan">{keyHint}</code>
              </p>
              <p>
                Use the full key you saved when the project was created. Keys are stored as hashes and can’t be shown again.
                If you lost it, rotate a new one in Project Settings.
              </p>
              <p>Keep it in an environment variable such as <code className="font-mono text-body">DRIFTGUARD_API_KEY</code>, not in source code.</p>
              <Button size="sm" onClick={() => onNavigate('settings')} icon={<KeyRound aria-hidden className="size-3.5" />}>
                Project Settings
              </Button>
            </div>
          </Panel>
          <Panel title="Endpoint">
            <dl className="space-y-2 text-[13px]">
              <div>
                <dt className="text-xs text-muted">Base URL</dt>
                <dd className="font-mono break-all text-body">{baseUrl}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Project ID</dt>
                <dd className="font-mono break-all text-body">{project.project_id}</dd>
              </div>
            </dl>
          </Panel>
        </aside>
      </div>
    </>
  );
}
