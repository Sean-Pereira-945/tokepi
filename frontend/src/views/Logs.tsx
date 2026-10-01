import { Download, Pause, Play, ScrollText, Search, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api, downloadActivity, errorMessage } from '../api';
import { Badge, attemptTone } from '../components/Badges';
import { Button } from '../components/Button';
import { CodeBlock } from '../components/Copy';
import { SelectField, inputClass } from '../components/Field';
import { Drawer } from '../components/Overlay';
import { Eyebrow, PageHeader, Panel } from '../components/Panel';
import { EmptyState, ErrorState, LoadingState, StaleBanner } from '../components/States';
import { ClickableRow, TableScroll, Td, Th } from '../components/Table';
import { useToast } from '../components/Toasts';
import type { ViewId } from '../lib/route';
import { DASH, fmtDateTime, fmtDuration, fmtInt } from '../lib/format';
import { useProject, useWorkspace } from '../state/workspace';
import { AGENT_EVENT_KINDS, type ActivityQuery, type AgentEvent, type AgentEventKind, type Outcome } from '../types';

const PAGE_SIZE = 100;
const SEARCH_DELAY_MS = 300;

const KIND_META: Record<AgentEventKind, { label: string; tone: 'neutral' | 'cyan' | 'violet' }> = {
  tool_call: { label: 'Tool call', tone: 'neutral' },
  llm_call: { label: 'Model call', tone: 'violet' },
  prompt: { label: 'Prompt', tone: 'cyan' },
  response: { label: 'Response', tone: 'cyan' },
  session_start: { label: 'Session start', tone: 'neutral' },
  session_end: { label: 'Session end', tone: 'neutral' },
};

const KIND_OPTIONS = [
  { value: '', label: 'All activity' },
  ...AGENT_EVENT_KINDS.map((kind) => ({ value: kind, label: KIND_META[kind].label })),
];

const OUTCOME_OPTIONS = [
  { value: '', label: 'Any outcome' },
  { value: 'failed', label: 'Failures' },
  { value: 'success', label: 'Successes' },
];

function kindLabel(kind: AgentEventKind): string {
  return KIND_META[kind]?.label ?? kind;
}

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

interface PagesState {
  key: string;
  rows: AgentEvent[];
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
}

/** Newest-first activity with "load more" paging. With `live` on, new events are merged in as they arrive. */
function useActivityPages(query: ActivityQuery, live: boolean) {
  const project = useProject();
  const { filters, refreshKey, activityKey } = useWorkspace();
  const key = `${project.project_id}|${filters.environment}|${filters.timeRange}|${JSON.stringify(query)}`;
  const [state, setState] = useState<PagesState>({ key, rows: [], hasMore: false, loading: true, loadingMore: false, error: null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) =>
      prev.key === key
        ? { ...prev, loading: true, error: null }
        : { key, rows: [], hasMore: false, loading: true, loadingMore: false, error: null },
    );
    api.listAgentEvents(project.project_id, filters, { ...query, limit: PAGE_SIZE }, controller.signal).then(
      (rows) => setState({ key, rows, hasMore: rows.length === PAGE_SIZE, loading: false, loadingMore: false, error: null }),
      (error: unknown) => {
        if (!controller.signal.aborted) setState((prev) => ({ ...prev, key, loading: false, error: errorMessage(error) }));
      },
    );
    return () => controller.abort();
    // `query` is captured through `key`.
  }, [key, refreshKey, tick]);

  // Live tail: fetch the newest page and prepend rows we don't have yet, keeping any older pages loaded.
  const firstActivity = useRef(activityKey);
  useEffect(() => {
    if (!live || activityKey === firstActivity.current) return;
    const controller = new AbortController();
    api.listAgentEvents(project.project_id, filters, { ...query, limit: PAGE_SIZE }, controller.signal).then(
      (fresh) =>
        setState((prev) => {
          if (prev.key !== key) return prev;
          const newestId = prev.rows[0]?.id ?? 0;
          const newer = fresh.filter((row) => row.id > newestId);
          if (newer.length === 0) return prev;
          // More new rows than one page: there may be a gap, so start over from the newest page.
          if (newer.length === PAGE_SIZE) return { ...prev, rows: fresh, hasMore: true, error: null };
          return { ...prev, rows: [...newer, ...prev.rows], error: null };
        }),
      () => undefined, // A failed live refresh keeps the current rows; the next event retries.
    );
    return () => controller.abort();
  }, [activityKey, live]);

  const loadMore = async () => {
    const last = state.rows[state.rows.length - 1];
    if (!last) return;
    setState((prev) => ({ ...prev, loadingMore: true, error: null }));
    try {
      const rows = await api.listAgentEvents(project.project_id, filters, { ...query, limit: PAGE_SIZE, beforeId: last.id });
      setState((prev) =>
        prev.key === key ? { ...prev, rows: [...prev.rows, ...rows], hasMore: rows.length === PAGE_SIZE, loadingMore: false } : prev,
      );
    } catch (error) {
      setState((prev) => ({ ...prev, loadingMore: false, error: errorMessage(error) }));
    }
  };

  const current = state.key === key ? state : { ...state, rows: [], loading: true };
  return { ...current, loadMore, retry: () => setTick((n) => n + 1) };
}

function StatusCell({ event }: { event: AgentEvent }) {
  if (event.status === 'info') return <span className="text-muted">{DASH}</span>;
  return <Badge tone={attemptTone(event.status)}>{event.status}</Badge>;
}

function detailText(event: AgentEvent): { text: string; tone: 'error' | 'content' | 'none' } {
  if (event.error_message) return { text: event.error_message, tone: 'error' };
  const content = event.output ?? event.input;
  if (content) return { text: content, tone: 'content' };
  return { text: DASH, tone: 'none' };
}

function ActivityDrawer({
  event,
  captureContent,
  onClose,
  onFilterTask,
}: {
  event: AgentEvent | null;
  captureContent: boolean;
  onClose: () => void;
  onFilterTask: (taskId: string) => void;
}) {
  return (
    <Drawer
      open={event !== null}
      onClose={onClose}
      title={event ? `${kindLabel(event.kind)} #${event.id}` : ''}
      description={event && <span className="font-mono">{fmtDateTime(event.created_at)}</span>}
      footer={
        event && (
          <Button
            onClick={() => {
              onFilterTask(event.task_id);
              onClose();
            }}
          >
            Show only this task
          </Button>
        )
      }
    >
      {event && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={KIND_META[event.kind]?.tone ?? 'neutral'}>{kindLabel(event.kind)}</Badge>
            <StatusCell event={event} />
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
            {(
              [
                ['Task', event.task_id],
                ['Agent', event.agent_name ?? DASH],
                ['Tool', event.tool_name || DASH],
                ['Model', event.model ?? DASH],
                ['Attempt', event.kind === 'tool_call' ? fmtInt(event.attempt) : DASH],
                ['Duration', fmtDuration(event.duration_ms)],
                ['Prompt tokens', fmtInt(event.prompt_tokens)],
                ['Completion tokens', fmtInt(event.completion_tokens)],
                ['Total tokens', fmtInt(event.total_tokens)],
                ['Environment', event.environment ?? DASH],
                ['Trace ID', event.trace_id ?? DASH],
                ['Tool call ID', event.tool_call_id ?? DASH],
                ['Input hash', event.input_hash ?? DASH],
                ['Time (UTC)', event.created_at],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="tabular mt-0.5 font-mono break-all text-body">{value}</dd>
              </div>
            ))}
          </dl>
          {(event.error_type || event.error_message) && (
            <div>
              <Eyebrow>Error</Eyebrow>
              {event.error_type && <p className="mt-1 font-mono text-[13px] text-coral">{event.error_type}</p>}
              {event.error_message && <p className="mt-1 text-[13px] break-words whitespace-pre-wrap text-body">{event.error_message}</p>}
            </div>
          )}
          {event.input && <CodeBlock code={event.input} title="input" language="text" />}
          {event.output && <CodeBlock code={event.output} title="output" language="text" />}
          {!event.input && !event.output && (
            <p className="text-[13px] text-muted">
              {captureContent
                ? 'No input or output was sent with this event.'
                : 'Inputs and outputs are not stored for this project. Turn on content storage in Project Settings.'}
            </p>
          )}
        </div>
      )}
    </Drawer>
  );
}

export function Logs({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const project = useProject();
  const { filters } = useWorkspace();
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState<AgentEventKind | ''>('');
  const [outcome, setOutcome] = useState<Outcome | ''>('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [live, setLive] = useState(true);
  const [exporting, setExporting] = useState<'csv' | 'json' | null>(null);
  const [selected, setSelected] = useState<AgentEvent | null>(null);

  const q = useDebounced(search.trim(), SEARCH_DELAY_MS);
  const query = useMemo<ActivityQuery>(
    () => ({ q: q || undefined, kind: kind || undefined, outcome: outcome || undefined, taskId: taskId ?? undefined }),
    [q, kind, outcome, taskId],
  );
  const pages = useActivityPages(query, live);
  const filtered = Boolean(query.q || query.kind || query.outcome || query.taskId);

  const exportAs = async (format: 'csv' | 'json') => {
    setExporting(format);
    try {
      await downloadActivity(project.project_id, filters, query, format);
    } catch (error) {
      toast.push({ tone: 'error', title: 'Export failed', message: errorMessage(error) });
    } finally {
      setExporting(null);
    }
  };

  let body;
  if (pages.loading && pages.rows.length === 0) body = <LoadingState label="Loading activity…" />;
  else if (pages.error && pages.rows.length === 0) body = <ErrorState message={pages.error} onRetry={pages.retry} />;
  else if (pages.rows.length === 0)
    body = filtered ? (
      <EmptyState title="No activity matches these filters">Clear a filter or widen the time range.</EmptyState>
    ) : (
      <EmptyState title="No agent activity in this window" icon={<ScrollText aria-hidden className="size-5" />}>
        Everything an instrumented agent does appears here: tool calls, model calls, prompts and sessions. See SDK
        Integration to connect an agent, or widen the time range.
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
        <TableScroll label="Agent activity">
          <thead>
            <tr>
              <Th>Time</Th>
              <Th>Kind</Th>
              <Th>Status</Th>
              <Th>Task</Th>
              <Th>Tool / model</Th>
              <Th>Details</Th>
              <Th>Agent</Th>
              <Th align="right">Attempt</Th>
              <Th align="right">Duration</Th>
              <Th align="right">Tokens</Th>
            </tr>
          </thead>
          <tbody>
            {pages.rows.map((event) => {
              const detail = detailText(event);
              return (
                <ClickableRow key={event.id} onOpen={() => setSelected(event)} selected={selected?.id === event.id}>
                  <Td mono className="whitespace-nowrap text-muted">
                    {fmtDateTime(event.created_at)}
                  </Td>
                  <Td>
                    <Badge tone={KIND_META[event.kind]?.tone ?? 'neutral'}>{kindLabel(event.kind)}</Badge>
                  </Td>
                  <Td>
                    <StatusCell event={event} />
                  </Td>
                  <Td mono className="max-w-[180px] truncate text-ink">
                    <span title={event.task_id}>{event.task_id}</span>
                  </Td>
                  <Td mono className="max-w-[160px] truncate">
                    {event.tool_name || event.model || DASH}
                  </Td>
                  <Td
                    className={`max-w-[320px] truncate ${detail.tone === 'error' ? 'text-coral' : detail.tone === 'content' ? 'font-mono text-body' : 'text-muted'}`}
                  >
                    <span title={detail.tone === 'none' ? undefined : detail.text}>{detail.text}</span>
                  </Td>
                  <Td mono className="max-w-[140px] truncate text-muted">
                    {event.agent_name ?? DASH}
                  </Td>
                  <Td mono align="right">
                    {event.kind === 'tool_call' ? fmtInt(event.attempt) : DASH}
                  </Td>
                  <Td mono align="right">{fmtDuration(event.duration_ms)}</Td>
                  <Td mono align="right">{fmtInt(event.total_tokens)}</Td>
                </ClickableRow>
              );
            })}
          </tbody>
        </TableScroll>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-hairline px-4 py-3 text-xs text-muted">
          <span aria-live="polite">Showing {fmtInt(pages.rows.length)} events, newest first</span>
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
      <PageHeader
        title="Logs"
        description="Everything your agents did, newest first: tool calls, model calls, prompts and sessions. Select a row for details."
        actions={
          <>
            <Button
              variant={live ? 'secondary' : 'ghost'}
              aria-pressed={live}
              onClick={() => setLive((v) => !v)}
              icon={live ? <Pause aria-hidden className="size-4" /> : <Play aria-hidden className="size-4" />}
            >
              {live ? 'Pause live updates' : 'Resume live updates'}
            </Button>
            <Button onClick={() => void exportAs('csv')} busy={exporting === 'csv'} icon={<Download aria-hidden className="size-4" />}>
              CSV
            </Button>
            <Button onClick={() => void exportAs('json')} busy={exporting === 'json'} icon={<Download aria-hidden className="size-4" />}>
              JSON
            </Button>
          </>
        }
      />

      {!project.capture_content && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-hairline bg-panel px-4 py-3 text-[13px] text-muted">
          <span className="min-w-[16rem] flex-1">
            Only activity metadata is stored for this project: tool names, statuses, errors and timings. Inputs, outputs and
            prompt text are not stored.
          </span>
          <Button size="sm" onClick={() => onNavigate('settings')}>
            Change in Project Settings
          </Button>
        </div>
      )}

      <Panel
        bodyClassName=""
        title="Activity"
        actions={
          <div className="flex w-full flex-wrap items-end gap-2 sm:w-auto">
            <label className="relative block w-full sm:w-64">
              <span className="sr-only">Search activity</span>
              <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search tasks, tools, errors, content…"
                className={`${inputClass} pl-9`}
              />
            </label>
            <SelectField
              label="Kind"
              hideLabel
              className="w-full sm:w-40"
              value={kind}
              onChange={(e) => setKind(e.target.value as AgentEventKind | '')}
              options={KIND_OPTIONS}
            />
            <SelectField
              label="Outcome"
              hideLabel
              className="w-full sm:w-36"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value as Outcome | '')}
              options={OUTCOME_OPTIONS}
            />
          </div>
        }
      >
        {taskId && (
          <div className="flex items-center gap-2 border-b border-hairline px-4 py-2 text-[13px] text-muted">
            Task
            <span className="inline-flex items-center gap-1 rounded-md border border-cyan/30 bg-cyan/10 py-0.5 pr-1 pl-2 font-mono text-cyan">
              {taskId}
              <button
                type="button"
                onClick={() => setTaskId(null)}
                aria-label="Clear task filter"
                className="rounded p-0.5 hover:bg-cyan/20"
              >
                <X aria-hidden className="size-3.5" />
              </button>
            </span>
          </div>
        )}
        {body}
      </Panel>

      <ActivityDrawer
        event={selected}
        captureContent={project.capture_content}
        onClose={() => setSelected(null)}
        onFilterTask={setTaskId}
      />
    </>
  );
}
