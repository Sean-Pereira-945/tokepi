import { ArrowRight, Bot } from 'lucide-react';
import { api } from '../api';
import { TimelineChart } from '../charts/TimelineChart';
import { RiskBreakdown } from '../charts/RiskBreakdown';
import { toPoints } from '../charts/points';
import { AlertRow } from '../components/AlertRow';
import { SeverityBadge } from '../components/Badges';
import { Button } from '../components/Button';
import { MetricCard } from '../components/MetricCard';
import { PageHeader, Panel } from '../components/Panel';
import { EmptyState, ErrorState, ResourceView } from '../components/States';
import { fmtCompact, fmtDateTime, fmtDuration, fmtInt, fmtPercent, fmtRelative, fmtScore, TIME_RANGE_LABELS } from '../lib/format';
import type { ViewId } from '../lib/route';
import { useProjectQuery } from '../state/queries';
import { useProject, useWorkspace } from '../state/workspace';
import type { AgentDiagnosis, Summary } from '../types';

// Server-side risk thresholds (driftguard/policy.py): warning ≥ 0.4, critical ≥ 0.75.
const WARNING_RISK = 0.4;
const CRITICAL_RISK = 0.75;

function MetricRow({ summary, loading }: { summary: Summary | undefined; loading: boolean }) {
  const s = summary;
  const avg = s?.averages;
  const floor = s?.policy;
  const bySev = s?.events_by_severity;
  const below = (value: number | null | undefined, limit: number | undefined) =>
    value !== null && value !== undefined && limit !== undefined && value < limit;
  // Telemetry exists but this metric was never sent (e.g. Claude Code has no retrieval step).
  const notReported = (value: number | null | undefined) =>
    s && s.total_events > 0 && (value === null || value === undefined) ? 'Not reported by this source' : null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      <MetricCard
        label="Total events"
        loading={loading}
        value={fmtInt(s?.total_events)}
        detail={
          s && s.total_events > 0
            ? `${fmtInt(bySev?.critical ?? 0)} critical · ${fmtInt(bySev?.warning ?? 0)} warning`
            : 'No telemetry in this window'
        }
      />
      <MetricCard
        label="Open alerts"
        loading={loading}
        value={fmtInt(s?.open_alerts)}
        emphasis={s && s.critical_alerts > 0 ? 'critical' : s && s.warning_alerts > 0 ? 'warning' : 'default'}
        detail={s ? `${fmtInt(s.critical_alerts)} critical · ${fmtInt(s.warning_alerts)} warning` : undefined}
      />
      <MetricCard
        label="Tokens at stake"
        loading={loading}
        value={fmtInt(s?.saved_tokens)}
        unit="tokens"
        detail="Across open alerts"
      />
      <MetricCard
        label="Mean retrieval score"
        loading={loading}
        value={fmtScore(avg?.retrieval_score)}
        emphasis={below(avg?.retrieval_score, floor?.retrieval_score_floor) ? 'warning' : 'default'}
        detail={notReported(avg?.retrieval_score) ?? (floor ? `Floor ${fmtScore(floor.retrieval_score_floor)}` : undefined)}
      />
      <MetricCard
        label="Mean response quality"
        loading={loading}
        value={fmtScore(avg?.response_quality)}
        emphasis={below(avg?.response_quality, floor?.response_quality_floor) ? 'warning' : 'default'}
        detail={notReported(avg?.response_quality) ?? (floor ? `Floor ${fmtScore(floor.response_quality_floor)}` : undefined)}
      />
      <MetricCard
        label="Mean risk score"
        loading={loading}
        value={fmtScore(avg?.risk_score)}
        emphasis={
          avg?.risk_score == null
            ? 'default'
            : avg.risk_score >= CRITICAL_RISK
              ? 'critical'
              : avg.risk_score >= WARNING_RISK
                ? 'warning'
                : 'default'
        }
        detail="Warning ≥ 0.40 · critical ≥ 0.75"
      />
    </div>
  );
}

/** Agent activity from the same events the Logs view lists. Shown once a project has any. */
function AgentActivityRow({ summary }: { summary: Summary }) {
  const a = summary.agent_activity;
  if (!a || a.events === 0) return null;
  const rate = a.failure_rate;
  return (
    <section aria-labelledby="overview-activity" className="space-y-3">
      <h2 id="overview-activity" className="text-sm font-semibold text-body">
        Agent activity
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        <MetricCard label="Tool calls" value={fmtInt(a.tool_calls)} detail={`${fmtInt(a.failed_tool_calls)} failed`} />
        <MetricCard
          label="Tool failure rate"
          value={rate === null ? '—' : fmtPercent(rate, 1)}
          emphasis={rate !== null && rate >= 0.25 ? 'critical' : rate !== null && rate >= 0.1 ? 'warning' : 'default'}
          detail="Failed ÷ all tool calls"
        />
        <MetricCard label="Tasks" value={fmtInt(a.tasks)} detail={`${fmtInt(a.turns)} completed`} />
        <MetricCard
          label="Tokens used"
          value={fmtCompact(a.total_tokens)}
          unit="tokens"
          detail="New input + output, by agent tasks"
        />
        <MetricCard label="Avg tool duration" value={fmtDuration(a.avg_tool_duration_ms)} detail="Call to result" />
        <MetricCard
          label="Agent events"
          value={fmtInt(a.events)}
          detail={a.last_activity ? `Last ${fmtRelative(a.last_activity)}` : 'In this window'}
        />
      </div>
    </section>
  );
}

function DiagnosisCallout({ diagnosis, onOpen }: { diagnosis: AgentDiagnosis; onOpen: () => void }) {
  const urgent = diagnosis.status !== 'stable';
  const border = diagnosis.status === 'critical' ? 'border-coral/50' : diagnosis.status === 'warning' ? 'border-amber/40' : 'border-hairline';
  if (diagnosis.task_count === 0) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-panel px-4 py-3 text-[13px] text-muted">
        <Bot aria-hidden className="size-4" />
        No agent events in this window. Agent Diagnosis activates once your agent sends tool attempts.
        <button type="button" onClick={onOpen} className="font-semibold text-cyan hover:underline">
          How to send agent events
        </button>
      </div>
    );
  }
  return (
    <section aria-labelledby="overview-diagnosis" className={`animate-rise rounded-lg border bg-panel p-4 sm:p-5 ${border}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="overview-diagnosis" className="text-base font-semibold">
              Agent Task Diagnosis
            </h2>
            <SeverityBadge severity={diagnosis.status} />
          </div>
          <p className={`text-[15px] leading-snug ${urgent ? 'text-ink' : 'text-body'}`}>{diagnosis.diagnosis}</p>
          <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted">
            <div className="flex gap-1.5">
              <dt>Blocking tool</dt>
              <dd className="font-mono text-body">{diagnosis.blocking_tool ?? '—'}</dd>
            </div>
            <div className="flex gap-1.5">
              <dt>Wasted tokens (all tasks)</dt>
              <dd className={`tabular font-mono ${diagnosis.wasted_tokens > 0 ? 'text-coral' : 'text-body'}`}>
                {fmtInt(diagnosis.wasted_tokens)}
              </dd>
            </div>
            <div className="flex gap-1.5">
              <dt>Blocked / failing tasks</dt>
              <dd className="tabular font-mono text-body">
                {diagnosis.blocked_tasks} / {diagnosis.failing_tasks}
              </dd>
            </div>
          </dl>
          {urgent && (
            <p className="text-[13px] text-muted">
              <span className="font-semibold text-body">Recommendation: </span>
              {diagnosis.recommendation}
            </p>
          )}
        </div>
        <Button onClick={onOpen} icon={<ArrowRight aria-hidden className="size-4" />}>
          Agent Diagnosis
        </Button>
      </div>
    </section>
  );
}

export function Overview({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const project = useProject();
  const { summary, filters } = useWorkspace();
  const diagnosis = useProjectQuery('diagnosis', (id, f, signal) => api.agentDiagnosis(id, f, signal), { watchAlerts: true });
  const events = useProjectQuery('events-500', (id, f, signal) => api.listEvents(id, f, { limit: 500 }, signal));
  const alerts = useProjectQuery('open-alerts-5', (id, f, signal) => api.listAlerts(id, f, { resolved: false, limit: 5 }, signal), {
    watchAlerts: true,
  });

  const s = summary.data;

  return (
    <>
      <PageHeader
        title="Operational Overview"
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>
              {project.name} · <span className="font-mono">{project.project_id}</span> · {TIME_RANGE_LABELS[filters.timeRange]}
              {filters.environment !== 'all' && ` · ${filters.environment}`}
            </span>
            {s && (
              <span className="flex items-center gap-2">
                <span className="text-xs">Status</span> <SeverityBadge severity={s.status} />
              </span>
            )}
            {s?.last_updated && (
              <span className="font-mono text-xs" title={fmtDateTime(s.last_updated)}>
                Last activity {fmtRelative(s.last_updated)}
              </span>
            )}
          </span>
        }
      />

      <div className="space-y-6">
        {summary.error && !s ? (
          <Panel>
            <ErrorState message={summary.error} onRetry={summary.reload} />
          </Panel>
        ) : (
          <MetricRow summary={s} loading={!s && summary.loading} />
        )}

        {s && <AgentActivityRow summary={s} />}

        <ResourceView resource={diagnosis} className="py-6">
          {(data) => <DiagnosisCallout diagnosis={data} onOpen={() => onNavigate('agents')} />}
        </ResourceView>

        <div className="grid gap-6 xl:grid-cols-3">
          <Panel
            title="Telemetry & Drift Timeline"
            description="Latest 500 events in the window, oldest to newest."
            className="xl:col-span-2"
          >
            <ResourceView
              resource={events}
              isEmpty={(data) => data.length === 0}
              empty={
                <EmptyState title="No telemetry yet">
                  Send events with the SDK (<span className="font-mono">capture_metrics</span> +{' '}
                  <span className="font-mono">sync_metrics</span>) or use Test Telemetry in the header.
                </EmptyState>
              }
            >
              {(data) => <TimelineChart points={toPoints(data)} promptTokenLimit={s?.policy.prompt_token_limit} />}
            </ResourceView>
          </Panel>

          <Panel title="Drift Risk Breakdown" description="Share of events violating each policy rule.">
            <ResourceView
              resource={summary}
              isEmpty={(data) => data.total_events === 0}
              empty={<EmptyState title="No telemetry in this window">Rates appear once events are scored.</EmptyState>}
            >
              {(data) => <RiskBreakdown rates={data.violation_rates} policy={data.policy} />}
            </ResourceView>
          </Panel>
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          <Panel title="Top Root Causes" description="Most frequent causes among warning and critical events.">
            <ResourceView
              resource={summary}
              isEmpty={(data) => data.top_root_causes.length === 0}
              empty={<EmptyState title="No drift detected">No warning or critical events in this window.</EmptyState>}
            >
              {(data) => {
                const max = Math.max(...data.top_root_causes.map((c) => c.count));
                return (
                  <ol className="space-y-3">
                    {data.top_root_causes.map((cause) => (
                      <li key={cause.root_cause}>
                        <div className="mb-1 flex items-start justify-between gap-3 text-[13px]">
                          <span className="text-body">{cause.root_cause}</span>
                          <span className="tabular shrink-0 font-mono text-muted">{fmtInt(cause.count)}</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-white/[0.04]" aria-hidden>
                          <div className="h-full rounded-full bg-cyan/70" style={{ width: `${(cause.count / max) * 100}%` }} />
                        </div>
                      </li>
                    ))}
                  </ol>
                );
              }}
            </ResourceView>
          </Panel>

          <Panel
            title="Active Alerts"
            description="Latest open alerts."
            className="xl:col-span-2"
            bodyClassName=""
            actions={
              <Button size="sm" variant="ghost" onClick={() => onNavigate('alerts')} icon={<ArrowRight aria-hidden className="size-3.5" />}>
                All alerts
              </Button>
            }
          >
            <ResourceView
              resource={alerts}
              isEmpty={(data) => data.length === 0}
              empty={<EmptyState title="No open alerts">Critical drift and blocked agent tasks raise alerts here.</EmptyState>}
            >
              {(data) => (
                <ul>
                  {data.map((alert) => (
                    <AlertRow key={alert.id} alert={alert} />
                  ))}
                </ul>
              )}
            </ResourceView>
          </Panel>
        </div>
      </div>
    </>
  );
}
