import { useMemo } from 'react';
import { api } from '../api';
import { COLORS } from '../charts/common';
import { MetricLineChart } from '../charts/MetricLineChart';
import { toPoints, type EventPoint } from '../charts/points';
import { QualityScatter, scatterable } from '../charts/QualityScatter';
import { SeverityChart } from '../charts/SeverityChart';
import { PageHeader, Panel } from '../components/Panel';
import { EmptyState, ErrorState, LoadingState, ResourceView } from '../components/States';
import { fmtInt, fmtScore } from '../lib/format';
import { useProjectQuery } from '../state/queries';
import { useWorkspace } from '../state/workspace';
import type { Policy } from '../types';

const NO_TELEMETRY = (
  <EmptyState title="No telemetry in this window">Send events with the SDK or use Test Telemetry, then refresh.</EmptyState>
);

function hasValues(points: EventPoint[], key: keyof EventPoint): boolean {
  return points.some((p) => p[key] !== null);
}

function EventCharts({ points, policy }: { points: EventPoint[]; policy: Policy | undefined }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Panel title="Context length over time" description="Per event, with the policy limit.">
        {hasValues(points, 'context_length') ? (
          <MetricLineChart
            points={points}
            dataKey="context_length"
            label="Context length"
            color={COLORS.cyan}
            format={fmtInt}
            threshold={policy ? { value: policy.context_length_limit, label: 'Context length limit' } : undefined}
          />
        ) : (
          <EmptyState title="No context length values">Loaded events don’t include context_length.</EmptyState>
        )}
      </Panel>
      <Panel title="Prompt tokens vs response quality" description="Each mark is one event; shape and color show severity.">
        {scatterable(points) > 0 ? (
          <QualityScatter
            points={points}
            promptTokenLimit={policy?.prompt_token_limit}
            qualityFloor={policy?.response_quality_floor}
          />
        ) : (
          <EmptyState title="No events with both values">Events need prompt_tokens and response_quality to plot here.</EmptyState>
        )}
      </Panel>
      <Panel title="Retrieval score over time" description="Per event, with the policy floor.">
        {hasValues(points, 'retrieval_score') ? (
          <MetricLineChart
            points={points}
            dataKey="retrieval_score"
            label="Retrieval score"
            color={COLORS.green}
            format={(v) => fmtScore(v)}
            scoreDomain
            threshold={policy ? { value: policy.retrieval_score_floor, label: 'Retrieval floor' } : undefined}
          />
        ) : (
          <EmptyState title="No retrieval scores">Loaded events don’t include retrieval_score.</EmptyState>
        )}
      </Panel>
      <SeverityPanel />
    </div>
  );
}

function SeverityPanel() {
  const { summary } = useWorkspace();
  return (
    <Panel title="Severity distribution" description="All events in the window, by scored severity.">
      <ResourceView resource={summary} isEmpty={(data) => data.total_events === 0} empty={NO_TELEMETRY}>
        {(data) => <SeverityChart bySeverity={data.events_by_severity} />}
      </ResourceView>
    </Panel>
  );
}

export function Analytics() {
  const { summary } = useWorkspace();
  const events = useProjectQuery('events-500', (id, f, signal) => api.listEvents(id, f, { limit: 500 }, signal));
  const points = useMemo(() => (events.data ? toPoints(events.data) : []), [events.data]);

  let content;
  if (events.data === undefined) {
    content = events.error ? (
      <Panel>
        <ErrorState message={events.error} onRetry={events.reload} />
      </Panel>
    ) : (
      <LoadingState label="Loading telemetry…" />
    );
  } else if (events.data.length === 0) {
    content = (
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Telemetry charts">{NO_TELEMETRY}</Panel>
        <SeverityPanel />
      </div>
    );
  } else {
    content = <EventCharts points={points} policy={summary.data?.policy} />;
  }

  return (
    <>
      <PageHeader
        title="Analytics"
        description={
          events.data && events.data.length >= 500
            ? 'Charts use the latest 500 events in the window; severity distribution covers every event.'
            : 'Charts use the events in the selected window.'
        }
      />
      {content}
    </>
  );
}
