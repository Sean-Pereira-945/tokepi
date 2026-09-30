import { AlertOctagon, Inbox, Loader2, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Resource } from '../lib/useResource';
import { Button } from './Button';

export function LoadingState({ label = 'Loading…', className = 'py-12' }: { label?: string; className?: string }) {
  return (
    <div role="status" className={`flex items-center justify-center gap-2 text-sm text-muted ${className}`}>
      <Loader2 aria-hidden className="size-4 animate-spin text-cyan" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry, className = 'py-10' }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={`flex flex-col items-center justify-center gap-3 px-4 text-center ${className}`}>
      <div className="flex items-center gap-2 text-sm font-semibold text-coral">
        <AlertOctagon aria-hidden className="size-4" />
        Couldn’t load this data
      </div>
      <p className="max-w-md text-sm text-muted">{message}</p>
      {onRetry && (
        <Button size="sm" onClick={onRetry} icon={<RefreshCw aria-hidden className="size-3.5" />}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
  icon,
  className = 'py-10',
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 px-4 text-center ${className}`}>
      <div className="mb-1 text-muted">{icon ?? <Inbox aria-hidden className="size-5" />}</div>
      <p className="text-sm font-semibold text-body">{title}</p>
      {children && <div className="max-w-md text-[13px] text-muted">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/** Banner shown above stale data when a background refresh fails. */
export function StaleBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-coral/40 bg-coral/5 px-3 py-2 text-[13px]">
      <AlertOctagon aria-hidden className="size-4 text-coral" />
      <span className="text-body">Refresh failed: {message}</span>
      <button type="button" onClick={onRetry} className="ml-auto font-semibold text-cyan hover:underline">
        Retry
      </button>
    </div>
  );
}

interface ResourceViewProps<T> {
  resource: Resource<T>;
  children: (data: T) => ReactNode;
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  loadingLabel?: string;
  className?: string;
}

/** Loading → error (with Retry) → empty → data, keeping stale data visible on refresh errors. */
export function ResourceView<T>({ resource, children, isEmpty, empty, loadingLabel, className }: ResourceViewProps<T>) {
  const { data, error, loading, reload } = resource;
  if (data === undefined) {
    if (error) return <ErrorState message={error} onRetry={reload} className={className} />;
    if (loading) return <LoadingState label={loadingLabel} className={className} />;
    return null;
  }
  return (
    <>
      {error && <StaleBanner message={error} onRetry={reload} />}
      {isEmpty?.(data) && empty ? empty : children(data)}
    </>
  );
}
