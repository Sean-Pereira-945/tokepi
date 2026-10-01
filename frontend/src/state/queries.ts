import { useResource, type Resource } from '../lib/useResource';
import type { Filters } from '../types';
import { useWorkspace } from './workspace';

interface Options {
  /** Extra identity for the request (e.g. a tab or task ID). */
  key?: string;
  /** Also re-fetch when alerts change (realtime messages, resolve/create). */
  watchAlerts?: boolean;
  /** Also re-fetch when new agent events arrive. */
  watchActivity?: boolean;
  enabled?: boolean;
}

/** Fetch data for the selected project with the header filters applied. */
export function useProjectQuery<T>(
  name: string,
  fetcher: (projectId: string, filters: Filters, signal: AbortSignal) => Promise<T>,
  { key = '', watchAlerts = false, watchActivity = false, enabled = true }: Options = {},
): Resource<T> {
  const { project, filters, refreshKey, alertsKey, activityKey } = useWorkspace();
  const projectId = project?.project_id ?? null;
  return useResource<T>(
    projectId && enabled ? (signal) => fetcher(projectId, filters, signal) : null,
    `${name}|${projectId}|${filters.environment}|${filters.timeRange}|${key}`,
    refreshKey + (watchAlerts ? alertsKey : 0) + (watchActivity ? activityKey : 0),
  );
}
