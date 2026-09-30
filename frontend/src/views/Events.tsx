import { Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api, errorMessage } from '../api';
import { SeverityBadge } from '../components/Badges';
import { Button } from '../components/Button';
import { CodeBlock } from '../components/Copy';
import { inputClass } from '../components/Field';
import { Drawer } from '../components/Overlay';
import { Eyebrow, PageHeader, Panel } from '../components/Panel';
import { EmptyState, ErrorState, LoadingState, StaleBanner } from '../components/States';
import { ClickableRow, TableScroll, Td, Th } from '../components/Table';
import { DASH, fmtDateTime, fmtInt, fmtScore, humanize } from '../lib/format';
import { useProject, useWorkspace } from '../state/workspace';
import type { TelemetryEvent } from '../types';

const PAGE_SIZE = 100;

interface EventsState {
  key: string;
  rows: TelemetryEvent[];
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
}

function useEventPages() {
  const project = useProject();
  const { filters, refreshKey } = useWorkspace();
  const key = `${project.project_id}|${filters.environment}|${filters.timeRange}`;
  const [state, setState] = useState<EventsState>({ key, rows: [], hasMore: false, loading: true, loadingMore: false, error: null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) =>
      prev.key === key ? { ...prev, loading: true, error: null } : { key, rows: [], hasMore: false, loading: true, loadingMore: false, error: null },
    );
    api.listEvents(project.project_id, filters, { limit: PAGE_SIZE }, controller.signal).then(
      (rows) => setState({ key, rows, hasMore: rows.length === PAGE_SIZE, loading: false, loadingMore: false, error: null }),
      (error: unknown) => {
        if (!controller.signal.aborted) setState((prev) => ({ ...prev, key, loading: false, error: errorMessage(error) }));
      },
    );
    return () => controller.abort();
  }, [key, refreshKey, tick]);

  const loadMore = async () => {
    const last = state.rows[state.rows.length - 1];
    if (!last) return;
    setState((prev) => ({ ...prev, loadingMore: true, error: null }));
    try {
      const rows = await api.listEvents(project.project_id, filters, { limit: PAGE_SIZE, beforeId: last.id });
      setState((prev) =>
        prev.key === key
          ? { ...prev, rows: [...prev.rows, ...rows], hasMore: rows.length === PAGE_SIZE, loadingMore: false }
          : prev,
      );
    } catch (error) {
      setState((prev) => ({ ...prev, loadingMore: false, error: errorMessage(error) }));
    }
  };

  const current = state.key === key ? state : { ...state, rows: [], loading: true };
  return { ...current, loadMore, retry: () => setTick((n) => n + 1) };
}

function matches(event: TelemetryEvent, query: string): boolean {
  if (!query) return true;
  const haystack = [
    event.id,
    event.environment,
    event.severity,
    event.root_cause,
    event.recommendation,
    event.metadata ? JSON.stringify(event.metadata) : '',
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(query);
}

function EventDrawer({ event, onClose }: { event: TelemetryEvent | null; onClose: () => void }) {
  return (
    <Drawer
      open={event !== null}
      onClose={onClose}
      title={event ? `Event #${event.id}` : ''}
      description={event && <span className="font-mono">{fmtDateTime(event.created_at)}</span>}
    >
      {event && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <SeverityBadge severity={event.severity} />
            <span className="text-[13px] text-muted">
              Risk <span className="tabular font-mono text-ink">{fmtScore(event.risk_score, 3)}</span>
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
            {(
              [
                ['Prompt tokens', fmtInt(event.prompt_tokens)],
                ['Context length', fmtInt(event.context_length)],
                ['Retrieval score', fmtScore(event.retrieval_score, 3)],
                ['Response quality', fmtScore(event.response_quality, 3)],
                ['Environment', event.environment ?? DASH],
                ['Time (UTC)', event.created_at],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="tabular mt-0.5 font-mono break-all text-body">{value}</dd>
              </div>
            ))}
          </dl>
          <div>
            <Eyebrow>Root cause</Eyebrow>
            <p className="mt-1 text-[13px] text-body">{event.root_cause || 'No policy rule violated'}</p>
          </div>
          <div>
            <Eyebrow>Recommendation</Eyebrow>
            <p className="mt-1 text-[13px] text-body">{humanize(event.recommendation)}</p>
          </div>
          <div>
            <Eyebrow className="mb-2 block">Metadata</Eyebrow>
            {event.metadata && Object.keys(event.metadata).length ? (
              <CodeBlock code={JSON.stringify(event.metadata, null, 2)} title="metadata.json" language="json" />
            ) : (
              <p className="text-[13px] text-muted">No metadata sent with this event.</p>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}

export function Events() {
  const pages = useEventPages();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<TelemetryEvent | null>(null);
  const q = query.trim().toLowerCase();
  const visible = useMemo(() => pages.rows.filter((row) => matches(row, q)), [pages.rows, q]);

  let body;
  if (pages.loading && pages.rows.length === 0) body = <LoadingState label="Loading events…" />;
  else if (pages.error && pages.rows.length === 0) body = <ErrorState message={pages.error} onRetry={pages.retry} />;
  else if (pages.rows.length === 0)
    body = (
      <EmptyState title="No telemetry yet">
        Send events with the SDK or use Test Telemetry. Try a wider time range if you expected events here.
      </EmptyState>
    );
  else
    body = (
      <>
        {pages.error && (
          <div className="px-4 pt-3">
            <StaleBanner message={pages.error} onRetry={pages.retry} />
          </div>
        )}
        <TableScroll label="Telemetry events">
          <thead>
            <tr>
              <Th>Time</Th>
              <Th>Env</Th>
              <Th>Severity</Th>
              <Th align="right">Risk</Th>
              <Th align="right">Prompt tokens</Th>
              <Th align="right">Context</Th>
              <Th align="right">Retrieval</Th>
              <Th align="right">Quality</Th>
              <Th>Root cause</Th>
            </tr>
          </thead>
          <tbody>
            {visible.map((event) => (
              <ClickableRow key={event.id} onOpen={() => setSelected(event)} selected={selected?.id === event.id}>
                <Td mono className="whitespace-nowrap text-muted">
                  {fmtDateTime(event.created_at)}
                </Td>
                <Td mono>{event.environment ?? DASH}</Td>
                <Td>
                  <SeverityBadge severity={event.severity} />
                </Td>
                <Td mono align="right">{fmtScore(event.risk_score)}</Td>
                <Td mono align="right">{fmtInt(event.prompt_tokens)}</Td>
                <Td mono align="right">{fmtInt(event.context_length)}</Td>
                <Td mono align="right">{fmtScore(event.retrieval_score)}</Td>
                <Td mono align="right">{fmtScore(event.response_quality)}</Td>
                <Td className="max-w-[320px] truncate text-muted">
                  <span title={event.root_cause ?? undefined}>{event.root_cause || DASH}</span>
                </Td>
              </ClickableRow>
            ))}
          </tbody>
        </TableScroll>
        {visible.length === 0 && (
          <EmptyState title="No loaded events match your filter" className="py-8">
            The text filter only searches rows loaded so far.
          </EmptyState>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-hairline px-4 py-3 text-xs text-muted">
          <span aria-live="polite">
            Showing {fmtInt(visible.length)} of {fmtInt(pages.rows.length)} loaded events
          </span>
          {pages.hasMore ? (
            <Button size="sm" onClick={() => void pages.loadMore()} busy={pages.loadingMore}>
              Load more
            </Button>
          ) : (
            <span>End of results</span>
          )}
        </div>
      </>
    );

  return (
    <>
      <PageHeader title="Events" description="Scored LLM telemetry, newest first. Select a row for all fields." />
      <Panel
        bodyClassName=""
        title="Event Explorer"
        actions={
          <label className="relative block w-full sm:w-72">
            <span className="sr-only">Filter loaded events</span>
            <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter loaded rows…"
              className={`${inputClass} pl-9`}
            />
          </label>
        }
      >
        {body}
      </Panel>
      <EventDrawer event={selected} onClose={() => setSelected(null)} />
    </>
  );
}
