import { FlaskConical, Menu, Plus, RefreshCw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { TIME_RANGE_LABELS } from '../lib/format';
import { useWorkspace } from '../state/workspace';
import { ENVIRONMENTS, TIME_RANGES, type Environment, type TimeRange } from '../types';
import { Button, IconButton } from './Button';
import { ConnectionIndicator } from './ConnectionIndicator';
import { SelectField } from './Field';

const ENV_OPTIONS = [{ value: 'all', label: 'All environments' }, ...ENVIRONMENTS.map((env) => ({ value: env, label: env }))];
const RANGE_OPTIONS = TIME_RANGES.map((range) => ({ value: range, label: TIME_RANGE_LABELS[range] }));

interface HeaderProps {
  onOpenMenu: () => void;
  menuOpen: boolean;
  onNewProject: () => void;
  onTestTelemetry: () => void;
}

export function Header({ onOpenMenu, menuOpen, onNewProject, onTestTelemetry }: HeaderProps) {
  const { projects, project, selectProject, filters, setFilters, refreshAll, summary } = useWorkspace();
  const [refreshRequested, setRefreshRequested] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const wasLoading = useRef(false);

  // Announce when a refresh finishes, based on the shared summary request.
  useEffect(() => {
    if (wasLoading.current && !summary.loading) {
      setUpdatedAt(new Date());
      setRefreshRequested(false);
    }
    wasLoading.current = summary.loading;
  }, [summary.loading]);

  const refreshing = refreshRequested && summary.loading;

  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-black/90 backdrop-blur supports-[backdrop-filter]:bg-black/75">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-2 px-4 py-3 sm:px-6 lg:gap-3 lg:px-8">
        <IconButton
          label="Open navigation"
          onClick={onOpenMenu}
          aria-expanded={menuOpen}
          aria-controls="app-sidebar"
          className="lg:hidden"
        >
          <Menu aria-hidden className="size-4" />
        </IconButton>

        {project && (
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:flex-none">
            <SelectField
              label="Project"
              hideLabel
              value={project.project_id}
              onChange={(e) => selectProject(e.target.value)}
              options={projects.map((p) => ({ value: p.project_id, label: `${p.name} (${p.project_id})` }))}
              className="min-w-0 flex-1 sm:w-64 sm:flex-none"
            />
            <IconButton label="New project" onClick={onNewProject}>
              <Plus aria-hidden className="size-4" />
            </IconButton>
          </div>
        )}

        {project && (
          <div className="order-last flex w-full gap-2 sm:order-none sm:w-auto">
            <SelectField
              label="Environment"
              hideLabel
              value={filters.environment}
              onChange={(e) => setFilters({ ...filters, environment: e.target.value as Environment | 'all' })}
              options={ENV_OPTIONS}
              className="flex-1 sm:w-44 sm:flex-none"
            />
            <SelectField
              label="Time range"
              hideLabel
              value={filters.timeRange}
              onChange={(e) => setFilters({ ...filters, timeRange: e.target.value as TimeRange })}
              options={RANGE_OPTIONS}
              className="flex-1 sm:w-40 sm:flex-none"
            />
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          <span aria-live="polite" className="hidden text-xs text-muted xl:inline">
            {refreshing ? 'Refreshing…' : updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : ''}
          </span>
          <span className="hidden sm:inline-flex">
            <ConnectionIndicator />
          </span>
          {project && (
            <>
              <IconButton
                label="Refresh data"
                onClick={() => {
                  setRefreshRequested(true);
                  refreshAll();
                }}
                disabled={refreshing}
              >
                <RefreshCw aria-hidden className={`size-4 ${refreshing ? 'animate-spin text-cyan' : ''}`} />
              </IconButton>
              <Button variant="primary" onClick={onTestTelemetry} icon={<FlaskConical aria-hidden className="size-4" />}>
                <span className="hidden sm:inline">Test Telemetry</span>
                <span className="sm:hidden">Test</span>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
