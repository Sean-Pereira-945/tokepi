import { Bot } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api';
import { Badge, SeverityBadge, TaskStatusBadge, attemptTone } from '../components/Badges';
import { CodeBlock } from '../components/Copy';
import { MetricCard } from '../components/MetricCard';
import { Drawer } from '../components/Overlay';
import { Eyebrow, PageHeader, Panel } from '../components/Panel';
import { EmptyState, ResourceView } from '../components/States';
import { ClickableRow, TableScroll, Td, Th } from '../components/Table';
import { DASH, fmtDateTime, fmtDuration, fmtInt, fmtRelative } from '../lib/format';
import { useProjectQuery } from '../state/queries';
import type { AgentDiagnosis as Diagnosis, AgentEvent, AgentTask } from '../types';

const EMIT_SNIPPET = `client.capture_agent_event(
    task_id="fix-tests",
    tool_name="terminal",
    status="failed",            # or "success"
    attempt=1,
    error_type="command_failed",
    error_message="pytest exited with code 1",
    total_tokens=2200,
)
client.sync_agent_events()`;

function DiagnosisStats({ data }: { data: Diagnosis }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
      <MetricCard label="Blocked tasks" value={fmtInt(data.blocked_tasks)} emphasis={data.blocked_tasks ? 'critical' : 'default'} detail={`of ${fmtInt(data.task_count)} tasks`} />
      <MetricCard label="Failing tasks" value={fmtInt(data.failing_tasks)} emphasis={data.failing_tasks ? 'warning' : 'default'} detail="Below the block threshold" />
      <MetricCard label="Failures" value={fmtInt(data.failure_count)} detail="Failed tool attempts" />
      <MetricCard label="Repeated attempts" value={fmtInt(data.repeated_attempts)} detail="Failures retrying a failed tool" />
      <MetricCard label="Redundant attempts" value={fmtInt(data.redundant_attempts)} detail="Repeats of input that succeeded" />
      <MetricCard label="Wasted tokens" value={fmtInt(data.wasted_tokens)} emphasis={data.wasted_tokens > 0 ? 'critical' : 'default'} detail="Failed or redundant attempts" />
    </div>
  );
}

function AttemptTimeline({ task }: { task: AgentTask }) {
  const attempts = useProjectQuery(
    'task-attempts',
    (id, f, signal) => api.listAgentEvents(id, f, { taskId: task.task_id, limit: 1000 }, signal),
    { key: task.task_id, watchAlerts: true },
  );
  return (
    <ResourceView
      resource={attempts}
      isEmpty={(data) => data.length === 0}
      empty={<EmptyState title="No attempts in this window">Widen the time range to see older attempts.</EmptyState>}
    >
      {(data) => {
        const ordered = [...data].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id);
        return (
          <>
            {data.length >= 1000 && <p className="mb-3 text-xs text-muted">Showing the latest 1,000 attempts.</p>}
            <ol className="relative space-y-4 border-l border-hairline-strong pl-5">
              {ordered.map((event) => (
                <AttemptItem key={event.id} event={event} />
              ))}
            </ol>
          </>
        );
      }}
    </ResourceView>
  );
}

function AttemptItem({ event }: { event: AgentEvent }) {
  const tone = attemptTone(event.status);
  const dot = tone === 'coral' ? 'bg-coral' : tone === 'green' ? 'bg-green' : 'bg-muted';
  return (
    <li className="relative">
      <span aria-hidden className={`absolute top-1.5 -left-[25px] size-2.5 rounded-full ring-4 ring-panel ${dot}`} />
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[13px] font-semibold text-ink">{event.tool_name}</span>
        <Badge tone={tone}>{event.status}</Badge>
        <span className="font-mono text-xs text-muted">attempt {event.attempt}</span>
        <time dateTime={event.created_at} className="ml-auto font-mono text-xs text-muted">
          {fmtDateTime(event.created_at)}
        </time>
      </div>
      {(event.error_type || event.error_message) && (
        <p className="mt-1.5 rounded-md border border-coral/20 bg-coral/5 px-2.5 py-1.5 font-mono text-xs break-words whitespace-pre-wrap text-body">
          {event.error_type && <span className="text-coral">{event.error_type}: </span>}
          {event.error_message ?? ''}
        </p>
      )}
      <dl className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted">
        <div className="flex gap-1">
          <dt>Tokens</dt>
          <dd className="tabular font-mono text-body">{fmtInt(event.total_tokens)}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Duration</dt>
          <dd className="font-mono text-body">{fmtDuration(event.duration_ms)}</dd>
        </div>
        {event.model && (
          <div className="flex gap-1">
            <dt>Model</dt>
            <dd className="font-mono text-body">{event.model}</dd>
          </div>
        )}
        {event.tool_call_id && (
          <div className="flex gap-1">
            <dt>Call</dt>
            <dd className="font-mono text-body">{event.tool_call_id}</dd>
          </div>
        )}
      </dl>
    </li>
  );
}

function TaskDrawer({ task, onClose }: { task: AgentTask | null; onClose: () => void }) {
  return (
    <Drawer
      open={task !== null}
      onClose={onClose}
      title={task ? task.task_id : ''}
      description={task && <span className="flex flex-wrap items-center gap-2"><TaskStatusBadge status={task.status} /><SeverityBadge severity={task.severity} /></span>}
    >
      {task && (
        <div className="space-y-6">
          <section aria-labelledby="task-diagnosis" className="space-y-2">
            <h3 id="task-diagnosis" className="sr-only">Diagnosis</h3>
            <p className="text-[15px] leading-snug text-ink">{task.diagnosis}</p>
            <div className="rounded-md border border-hairline-strong bg-raised px-3 py-2.5">
              <Eyebrow>Mitigation Recommendation</Eyebrow>
              <p className="mt-1 text-[13px] text-body">{task.recommendation}</p>
            </div>
          </section>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
            {(
              [
                ['Blocking tool', task.blocking_tool],
                ['Trace ID', task.trace_id],
                ['Agent', task.agent_name],
                ['Environment', task.environment],
                ['Consecutive failures', fmtInt(task.consecutive_failures)],
                ['Failed attempts', fmtInt(task.failed_attempts)],
                ['Repeated attempts', fmtInt(task.repeated_attempts)],
                ['Redundant attempts', fmtInt(task.redundant_attempts)],
                ['Total attempts', fmtInt(task.attempts)],
                ['Wasted tokens', fmtInt(task.wasted_tokens)],
                ['Total tokens', fmtInt(task.total_tokens)],
                ['Last error type', task.last_error_type],
                ['First seen', fmtDateTime(task.first_seen)],
                ['Last seen', fmtDateTime(task.last_seen)],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="mt-0.5 truncate font-mono text-body" title={value ?? undefined}>
                  {value ?? DASH}
                </dd>
              </div>
            ))}
            <div className="col-span-2">
              <dt className="text-xs text-muted">Tools</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {task.tools.length ? task.tools.map((tool) => <Badge key={tool} tone="neutral">{tool}</Badge>) : DASH}
              </dd>
            </div>
          </dl>

          <section aria-labelledby="task-attempts">
            <h3 id="task-attempts" className="mb-3 text-sm font-semibold">
              Attempts <span className="font-normal text-muted">(oldest first)</span>
            </h3>
            <AttemptTimeline task={task} />
          </section>
        </div>
      )}
    </Drawer>
  );
}

export function AgentDiagnosis() {
  const diagnosis = useProjectQuery('diagnosis', (id, f, signal) => api.agentDiagnosis(id, f, signal), { watchAlerts: true });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = diagnosis.data?.tasks.find((t) => t.task_id === selectedId) ?? null;

  return (
    <>
      <PageHeader
        title="Agent Diagnosis"
        description="Failed and repeated tool attempts per agent task, from the agent events your SDK sends."
      />
      <ResourceView
        resource={diagnosis}
        isEmpty={(data) => data.task_count === 0}
        empty={
          <Panel>
            <EmptyState title="No agent events in this window" icon={<Bot aria-hidden className="size-5" />}>
              <div className="space-y-3 text-left">
                <p>
                  Emit one agent event per tool attempt. Use <span className="font-mono text-body">capture_agent_event</span> then{' '}
                  <span className="font-mono text-body">sync_agent_events</span>, decorate tools with{' '}
                  <span className="font-mono text-body">@driftguard_tool()</span> inside an{' '}
                  <span className="font-mono text-body">AgentContext</span>, or wrap an MCP session with{' '}
                  <span className="font-mono text-body">MCPMiddleware</span>. See SDK Integration for full examples.
                </p>
                <CodeBlock code={EMIT_SNIPPET} title="agent event" />
              </div>
            </EmptyState>
          </Panel>
        }
      >
        {(data) => (
          <div className="space-y-6">
            <DiagnosisStats data={data} />
            <section
              aria-labelledby="diag-headline"
              className={`rounded-lg border bg-panel p-4 sm:p-5 ${data.status === 'critical' ? 'border-coral/50' : data.status === 'warning' ? 'border-amber/40' : 'border-hairline'}`}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h2 id="diag-headline" className="text-base font-semibold">
                  Most urgent
                </h2>
                <SeverityBadge severity={data.status} />
                {data.blocking_tool && (
                  <span className="text-xs text-muted">
                    Blocking tool <span className="font-mono text-body">{data.blocking_tool}</span>
                  </span>
                )}
              </div>
              <p className="text-[15px] leading-snug text-ink">{data.diagnosis}</p>
              <p className="mt-2 text-[13px] text-muted">
                <span className="font-semibold text-body">Recommendation: </span>
                {data.recommendation}
              </p>
            </section>

            <Panel title="Tasks" description="Most urgent first. Select a task to see its attempts." bodyClassName="">
              <TableScroll label="Agent tasks">
                <thead>
                  <tr>
                    <Th>Status</Th>
                    <Th>Task</Th>
                    <Th>Blocking tool</Th>
                    <Th align="right">Consecutive</Th>
                    <Th align="right">Failed</Th>
                    <Th align="right">Wasted tokens</Th>
                    <Th>Last error</Th>
                    <Th>Last seen</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.tasks.map((task) => (
                    <ClickableRow key={task.task_id} onOpen={() => setSelectedId(task.task_id)} selected={task.task_id === selectedId}>
                      <Td>
                        <TaskStatusBadge status={task.status} />
                      </Td>
                      <Td mono className="max-w-[220px] truncate text-ink">
                        {task.task_id}
                      </Td>
                      <Td mono>{task.blocking_tool ?? DASH}</Td>
                      <Td mono align="right">{fmtInt(task.consecutive_failures)}</Td>
                      <Td mono align="right">{fmtInt(task.failed_attempts)}</Td>
                      <Td mono align="right" className={task.wasted_tokens > 0 ? 'text-coral' : ''}>
                        {fmtInt(task.wasted_tokens)}
                      </Td>
                      <Td className="max-w-[280px] truncate text-muted">
                        <span title={task.last_error ?? undefined}>{task.last_error ?? DASH}</span>
                      </Td>
                      <Td mono className="whitespace-nowrap text-muted">
                        <span title={fmtDateTime(task.last_seen)}>{fmtRelative(task.last_seen)}</span>
                      </Td>
                    </ClickableRow>
                  ))}
                </tbody>
              </TableScroll>
            </Panel>
          </div>
        )}
      </ResourceView>
      <TaskDrawer task={selected} onClose={() => setSelectedId(null)} />
    </>
  );
}
