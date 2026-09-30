// Types mirroring docs/api.md (DriftGuard 0.4). Keep these in sync with the API.

export type Environment = 'prod' | 'staging' | 'dev' | 'test';
export type Severity = 'stable' | 'warning' | 'critical';
export type TimeRange = '15m' | '1h' | '24h' | '7d' | '30d' | 'all';
export type AlertSource = 'manual' | 'drift' | 'agent';
export type TaskStatus = 'blocked' | 'failing' | 'recovered' | 'healthy';

export const ENVIRONMENTS: readonly Environment[] = ['prod', 'staging', 'dev', 'test'];
export const SEVERITIES: readonly Severity[] = ['stable', 'warning', 'critical'];
export const TIME_RANGES: readonly TimeRange[] = ['15m', '1h', '24h', '7d', '30d', 'all'];

// ---- Meta -------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  database: string;
  version: string;
}

export interface AuthConfig {
  allow_signup: boolean;
  version: string;
}

// ---- Auth -------------------------------------------------------------------

/** `GET /auth/me` */
export interface Account {
  account_id: string;
  name: string;
  email: string;
  created_at: string;
}

/** `POST /auth/register` and `POST /auth/login` */
export interface Session extends Account {
  token: string;
  expires_at: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ---- Projects ---------------------------------------------------------------

export interface Project {
  project_id: string;
  account_id: string;
  name: string;
  environment: Environment;
  api_key_hint: string;
  created_at: string;
}

/** `POST /projects` and `POST /projects/{id}/api-key`: the key is shown only here. */
export interface ProjectWithKey extends Project {
  api_key: string;
}

export interface ProjectCreateRequest {
  project_id: string;
  name: string;
  environment: Environment;
}

// ---- Policy -----------------------------------------------------------------

export interface Policy {
  prompt_token_limit: number;
  retrieval_score_floor: number;
  context_length_limit: number;
  response_quality_floor: number;
  blocked_after_failures: number;
  retry_window_minutes: number;
}

export type PolicyField = keyof Policy;
export type PolicyUpdate = Partial<Policy>;

// ---- Telemetry ----------------------------------------------------------------

export type MetadataValue = string | number | boolean | null;

/** Body of `POST /events/{id}` and `POST /projects/{id}/events`. Every field is optional. */
export interface EventIngestRequest {
  prompt_tokens?: number;
  context_length?: number;
  retrieval_score?: number;
  response_quality?: number;
  environment?: Environment;
  occurred_at?: string;
  metadata?: Record<string, MetadataValue>;
}

/** Response of `POST /events/{id}` and `POST /projects/{id}/events`. */
export interface EventIngestResponse {
  project_id: string;
  status: 'ingested';
  severity: Severity;
  risk_score: number;
  recommendation: string;
  actions: string[];
  root_cause: string;
}

/** Item of `GET /projects/{id}/events`. `created_at` is the event time (`occurred_at` when sent). */
export interface TelemetryEvent {
  id: number;
  prompt_tokens: number | null;
  retrieval_score: number | null;
  context_length: number | null;
  response_quality: number | null;
  environment: Environment | null;
  risk_score: number | null;
  severity: Severity | null;
  root_cause: string | null;
  recommendation: string | null;
  metadata: Record<string, MetadataValue> | null;
  created_at: string;
}

// ---- Summary ----------------------------------------------------------------

export interface SummaryAverages {
  prompt_tokens: number | null;
  context_length: number | null;
  retrieval_score: number | null;
  response_quality: number | null;
  risk_score: number | null;
}

export interface ViolationRates {
  prompt_token_limit: number;
  context_length_limit: number;
  retrieval_score_floor: number;
  response_quality_floor: number;
}

export interface RootCauseCount {
  root_cause: string;
  count: number;
}

export interface SummaryFilters {
  environment: Environment | 'all';
  severity: Severity | 'all';
  time_range: TimeRange;
}

export interface Summary {
  project_id: string;
  status: Severity;
  total_events: number;
  /** Keys are severities; unscored events appear as `unscored`. */
  events_by_severity: Partial<Record<Severity | 'unscored', number>>;
  averages: SummaryAverages;
  violation_rates: ViolationRates;
  top_root_causes: RootCauseCount[];
  open_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  saved_tokens: number;
  last_updated: string | null;
  policy: Policy;
  filters: SummaryFilters;
}

// ---- Alerts -----------------------------------------------------------------

export interface Alert {
  id: number;
  project_id: string;
  severity: Severity;
  message: string;
  saved_tokens: number;
  environment: Environment | null;
  source: AlertSource;
  task_id: string | null;
  root_cause: string | null;
  resolved: boolean;
  resolved_at: string | null;
  created_at: string;
}

export interface AlertCreateRequest {
  severity: Severity;
  message: string;
  saved_tokens?: number;
  environment?: Environment;
}

// ---- Agents -----------------------------------------------------------------

/** Item of `GET /projects/{id}/agent-events`. */
export interface AgentEvent {
  id: number;
  task_id: string;
  trace_id: string | null;
  agent_name: string | null;
  model: string | null;
  tool_name: string;
  tool_call_id: string | null;
  attempt: number;
  status: string;
  error_type: string | null;
  error_message: string | null;
  input_hash: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  duration_ms: number | null;
  environment: Environment | null;
  created_at: string;
}

export interface AgentTask {
  task_id: string;
  trace_id: string | null;
  agent_name: string | null;
  environment: Environment | null;
  status: TaskStatus;
  severity: Severity;
  blocking_tool: string | null;
  consecutive_failures: number;
  failed_attempts: number;
  repeated_attempts: number;
  redundant_attempts: number;
  attempts: number;
  wasted_tokens: number;
  total_tokens: number;
  tools: string[];
  last_error_type: string | null;
  last_error: string | null;
  first_seen: string | null;
  last_seen: string | null;
  diagnosis: string;
  recommendation: string;
}

export interface AgentDiagnosis {
  status: Severity;
  task_blocked: boolean;
  blocked_tasks: number;
  failing_tasks: number;
  task_count: number;
  failure_count: number;
  repeated_attempts: number;
  redundant_attempts: number;
  wasted_tokens: number;
  blocking_tool: string | null;
  diagnosis: string;
  recommendation: string;
  tasks: AgentTask[];
}

// ---- Realtime ---------------------------------------------------------------

export type AlertAction = 'created' | 'resolved' | 'reopened';

export interface AlertMessage {
  type: 'alert';
  action: AlertAction;
  alert: Alert;
}

// ---- Dashboard filters (client-side) ----------------------------------------

export interface Filters {
  environment: Environment | 'all';
  timeRange: TimeRange;
}
