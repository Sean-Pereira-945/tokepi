// Typed client for the DriftGuard HTTP API (see docs/api.md).
// Requests are same-origin: in production the server hosts this bundle, and in
// development Vite proxies the API paths to the backend.

import { readStorage, STORAGE_KEYS, writeStorage } from './lib/storage';
import type {
  Account,
  ActivityQuery,
  AgentDiagnosis,
  AgentEvent,
  Alert,
  AlertCreateRequest,
  AuthConfig,
  EventIngestRequest,
  EventIngestResponse,
  Filters,
  LoginRequest,
  Policy,
  PolicyUpdate,
  Project,
  ProjectCreateRequest,
  ProjectUpdate,
  ProjectWithKey,
  RegisterRequest,
  Session,
  Severity,
  Summary,
  TelemetryEvent,
} from './types';

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// ---- Session token -------------------------------------------------------------

export function getToken(): string | null {
  return readStorage(STORAGE_KEYS.session);
}

export function setToken(token: string | null): void {
  writeStorage(STORAGE_KEYS.session, token);
}

let unauthorizedHandler: (() => void) | null = null;

/** Called when an authenticated request returns 401 (expired or revoked session). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function handleUnauthorized(): void {
  setToken(null);
  unauthorizedHandler?.();
}

// ---- Error parsing -------------------------------------------------------------

interface ValidationIssue {
  loc?: unknown[];
  msg?: string;
}

function describeIssue(issue: ValidationIssue): string {
  const loc = Array.isArray(issue.loc) ? issue.loc.filter((part) => part !== 'body' && part !== 'query') : [];
  const field = loc.length ? `${loc.join('.')}: ` : '';
  return `${field}${issue.msg ?? 'invalid value'}`;
}

function messageFromDetail(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => describeIssue(item as ValidationIssue)).join('; ');
  }
  return null;
}

function fallbackMessage(status: number): string {
  if (status === 401) return 'Your session has ended. Sign in again.';
  if (status === 403) return 'You do not have permission to do that.';
  if (status === 404) return 'Not found.';
  if (status === 429) return 'Too many requests. Wait a minute and try again.';
  if (status >= 500) return `The DriftGuard server returned an error (${status}).`;
  return `Request failed (${status}).`;
}

// ---- Core request --------------------------------------------------------------

type QueryValue = string | number | boolean | null | undefined;

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, QueryValue>;
  /** Send the session token. Default true. */
  auth?: boolean;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, auth = true, signal } = options;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = auth ? getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'Cannot reach the DriftGuard server. Check your connection and try again.');
  }

  if (response.status === 204) return undefined as T;

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const detail = payload && typeof payload === 'object' ? (payload as { detail?: unknown }).detail : undefined;
    const message = messageFromDetail(detail) ?? fallbackMessage(response.status);
    if (response.status === 401 && auth && token) handleUnauthorized();
    throw new ApiError(response.status, message);
  }
  return payload as T;
}

function enc(value: string): string {
  return encodeURIComponent(value);
}

/** Dashboard filters as documented query params (`environment` omitted for "all"). */
export function filterQuery(filters: Filters): Record<string, QueryValue> {
  return {
    environment: filters.environment === 'all' ? undefined : filters.environment,
    time_range: filters.timeRange,
  };
}

// ---- Endpoints -----------------------------------------------------------------

export const api = {
  authConfig: (signal?: AbortSignal) => request<AuthConfig>('/auth/config', { auth: false, signal }),
  register: (body: RegisterRequest) => request<Session>('/auth/register', { method: 'POST', body, auth: false }),
  login: (body: LoginRequest) => request<Session>('/auth/login', { method: 'POST', body, auth: false }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  me: (signal?: AbortSignal) => request<Account>('/auth/me', { signal }),

  listProjects: (signal?: AbortSignal) => request<Project[]>('/projects', { signal }),
  createProject: (body: ProjectCreateRequest) => request<ProjectWithKey>('/projects', { method: 'POST', body }),
  updateProject: (id: string, body: ProjectUpdate) =>
    request<Project>(`/projects/${enc(id)}`, { method: 'PATCH', body }),
  deleteProject: (id: string) => request<void>(`/projects/${enc(id)}`, { method: 'DELETE' }),
  rotateApiKey: (id: string) => request<ProjectWithKey>(`/projects/${enc(id)}/api-key`, { method: 'POST' }),

  getPolicy: (id: string, signal?: AbortSignal) => request<Policy>(`/projects/${enc(id)}/policy`, { signal }),
  updatePolicy: (id: string, body: PolicyUpdate) =>
    request<Policy>(`/projects/${enc(id)}/policy`, { method: 'PUT', body }),

  summary: (id: string, filters: Filters, signal?: AbortSignal) =>
    request<Summary>(`/projects/${enc(id)}/summary`, { query: filterQuery(filters), signal }),

  listEvents: (id: string, filters: Filters, opts: { limit?: number; beforeId?: number } = {}, signal?: AbortSignal) =>
    request<TelemetryEvent[]>(`/projects/${enc(id)}/events`, {
      query: { ...filterQuery(filters), limit: opts.limit, before_id: opts.beforeId },
      signal,
    }),
  sendTestEvent: (id: string, body: EventIngestRequest) =>
    request<EventIngestResponse>(`/projects/${enc(id)}/events`, { method: 'POST', body }),

  listAlerts: (
    id: string,
    filters: Filters,
    opts: { resolved?: boolean; severity?: Severity; limit?: number } = {},
    signal?: AbortSignal,
  ) =>
    request<Alert[]>(`/projects/${enc(id)}/alerts`, {
      query: { ...filterQuery(filters), resolved: opts.resolved, severity: opts.severity, limit: opts.limit },
      signal,
    }),
  createAlert: (id: string, body: AlertCreateRequest) =>
    request<Alert>(`/projects/${enc(id)}/alerts`, { method: 'POST', body }),
  setAlertResolved: (id: string, alertId: number, resolved: boolean) =>
    request<Alert>(`/projects/${enc(id)}/alerts/${alertId}`, { method: 'PATCH', body: { resolved } }),

  listAgentEvents: (
    id: string,
    filters: Filters,
    opts: ActivityQuery & { limit?: number; beforeId?: number } = {},
    signal?: AbortSignal,
  ) =>
    request<AgentEvent[]>(`/projects/${enc(id)}/agent-events`, {
      query: { ...filterQuery(filters), ...activityQuery(opts), limit: opts.limit, before_id: opts.beforeId },
      signal,
    }),
  agentDiagnosis: (id: string, filters: Filters, signal?: AbortSignal) =>
    request<AgentDiagnosis>(`/projects/${enc(id)}/agent-diagnosis`, { query: filterQuery(filters), signal }),
};

function activityQuery(opts: ActivityQuery): Record<string, QueryValue> {
  return {
    task_id: opts.taskId,
    kind: opts.kind,
    tool_name: opts.toolName,
    agent_name: opts.agentName,
    outcome: opts.outcome,
    q: opts.q,
  };
}

/** Download the filtered activity log (up to 10,000 rows) as a file. */
export async function downloadActivity(
  projectId: string,
  filters: Filters,
  opts: ActivityQuery,
  format: 'csv' | 'json',
): Promise<void> {
  const url = buildUrl(`/projects/${enc(projectId)}/agent-events/export`, {
    ...filterQuery(filters),
    ...activityQuery(opts),
    format,
  });
  const token = getToken();
  let response: Response;
  try {
    response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError(0, 'Cannot reach the DriftGuard server. Check your connection and try again.');
  }
  if (!response.ok) {
    if (response.status === 401 && token) handleUnauthorized();
    throw new ApiError(response.status, fallbackMessage(response.status));
  }
  const blob = await response.blob();
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `driftguard-${projectId}-activity.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return 'Something went wrong.';
}

/** Realtime URL. The session token is sent as a subprotocol (see `REALTIME_PROTOCOL`), never in the URL. */
export function realtimeUrl(projectId: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${window.location.host}/ws/projects/${enc(projectId)}`;
}

export const REALTIME_PROTOCOL = 'driftguard';
