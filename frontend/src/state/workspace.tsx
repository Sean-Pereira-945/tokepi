import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { api, errorMessage } from '../api';
import { readJson, readStorage, STORAGE_KEYS, writeStorage } from '../lib/storage';
import { useRealtime, type ConnectionState } from '../lib/useRealtime';
import { useResource, type Resource } from '../lib/useResource';
import { useToast } from '../components/Toasts';
import { ENVIRONMENTS, TIME_RANGES, type Alert, type AlertAction, type Filters, type Project, type Summary } from '../types';
import { useSignedIn } from './session';

const DEFAULT_FILTERS: Filters = { environment: 'all', timeRange: '24h' };

function isFilters(value: unknown): value is Filters {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  const envOk = v.environment === 'all' || (ENVIRONMENTS as readonly unknown[]).includes(v.environment);
  const rangeOk = (TIME_RANGES as readonly unknown[]).includes(v.timeRange);
  return envOk && rangeOk;
}

type ProjectsState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; projects: Project[] };

interface WorkspaceContextValue {
  projectsState: ProjectsState;
  reloadProjects: () => void;
  projects: Project[];
  project: Project | null;
  selectProject: (projectId: string) => void;
  upsertProject: (project: Project) => void;
  removeProject: (projectId: string) => void;

  filters: Filters;
  setFilters: (filters: Filters) => void;

  /** Bumped by Refresh, Test Telemetry, policy saves. Every view re-fetches. */
  refreshKey: number;
  /** Bumped when alerts change (realtime or local resolve/create). */
  alertsKey: number;
  refreshAll: () => void;
  alertsChanged: () => void;

  summary: Resource<Summary>;
  connection: ConnectionState;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { token, expire } = useSignedIn();
  const toast = useToast();

  const [projectsState, setProjectsState] = useState<ProjectsState>({ status: 'loading' });
  const [projectsTick, setProjectsTick] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(() => readStorage(STORAGE_KEYS.project));
  const [filters, setFiltersState] = useState<Filters>(() => readJson(STORAGE_KEYS.filters, isFilters) ?? DEFAULT_FILTERS);
  const [refreshKey, setRefreshKey] = useState(0);
  const [alertsKey, setAlertsKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setProjectsState((prev) => (prev.status === 'ready' ? prev : { status: 'loading' }));
    api.listProjects(controller.signal).then(
      (projects) => setProjectsState({ status: 'ready', projects }),
      (error: unknown) => {
        if (!controller.signal.aborted) setProjectsState({ status: 'error', message: errorMessage(error) });
      },
    );
    return () => controller.abort();
  }, [projectsTick]);

  const projects = useMemo(() => (projectsState.status === 'ready' ? projectsState.projects : []), [projectsState]);
  const project = useMemo(
    () => projects.find((p) => p.project_id === selectedId) ?? projects[0] ?? null,
    [projects, selectedId],
  );
  const projectId = project?.project_id ?? null;

  useEffect(() => {
    if (projectId) writeStorage(STORAGE_KEYS.project, projectId);
  }, [projectId]);

  const selectProject = useCallback((id: string) => setSelectedId(id), []);

  const upsertProject = useCallback((next: Project) => {
    setProjectsState((prev) => {
      const list = prev.status === 'ready' ? prev.projects : [];
      const exists = list.some((p) => p.project_id === next.project_id);
      return {
        status: 'ready',
        projects: exists ? list.map((p) => (p.project_id === next.project_id ? next : p)) : [...list, next],
      };
    });
  }, []);

  const removeProject = useCallback((id: string) => {
    setProjectsState((prev) =>
      prev.status === 'ready' ? { status: 'ready', projects: prev.projects.filter((p) => p.project_id !== id) } : prev,
    );
    setSelectedId((current) => (current === id ? null : current));
  }, []);

  const setFilters = useCallback((next: Filters) => {
    setFiltersState(next);
    writeStorage(STORAGE_KEYS.filters, JSON.stringify(next));
  }, []);

  const refreshAll = useCallback(() => setRefreshKey((n) => n + 1), []);
  const alertsChanged = useCallback(() => setAlertsKey((n) => n + 1), []);

  // Realtime: coalesce bursts of alert messages into one refresh.
  const debounce = useRef<number | undefined>(undefined);
  const toasted = useRef(new Set<number>());
  useEffect(() => {
    toasted.current.clear();
    return () => window.clearTimeout(debounce.current);
  }, [projectId]);

  const onAlert = useCallback(
    (alert: Alert, action: AlertAction) => {
      window.clearTimeout(debounce.current);
      debounce.current = window.setTimeout(() => setAlertsKey((n) => n + 1), 400);
      if (alert.severity === 'critical' && action === 'created' && !toasted.current.has(alert.id)) {
        toasted.current.add(alert.id);
        toast.push({
          tone: 'error',
          title: alert.source === 'agent' ? 'Agent task blocked' : 'Critical alert',
          message: alert.message,
        });
      }
    },
    [toast],
  );

  const onAuthFailure = useCallback(() => expire('Your session has ended. Sign in again.'), [expire]);
  // A socket that never opened (server down, proxy rejection) is retried with
  // backoff; also check the session over HTTP so a 401 there signs the user out.
  const onHandshakeFailure = useCallback(() => {
    api.me().catch(() => undefined);
  }, []);

  const connection = useRealtime(projectId, token, { onAlert, onAuthFailure, onHandshakeFailure });

  const summary = useResource<Summary>(
    projectId ? (signal) => api.summary(projectId, filters, signal) : null,
    `${projectId}|${filters.environment}|${filters.timeRange}`,
    refreshKey + alertsKey,
  );

  const reloadProjects = useCallback(() => setProjectsTick((n) => n + 1), []);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      projectsState,
      reloadProjects,
      projects,
      project,
      selectProject,
      upsertProject,
      removeProject,
      filters,
      setFilters,
      refreshKey,
      alertsKey,
      refreshAll,
      alertsChanged,
      summary,
      connection,
    }),
    [
      projectsState,
      reloadProjects,
      projects,
      project,
      selectProject,
      upsertProject,
      removeProject,
      filters,
      setFilters,
      refreshKey,
      alertsKey,
      refreshAll,
      alertsChanged,
      summary,
      connection,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider');
  return ctx;
}

/** The selected project for views that only render when one exists. */
export function useProject(): Project {
  const { project } = useWorkspace();
  if (!project) throw new Error('useProject requires a selected project');
  return project;
}
