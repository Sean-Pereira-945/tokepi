import { useCallback, useEffect, useState } from 'react';

export const VIEWS = [
  { id: 'overview', label: 'Overview' },
  { id: 'agents', label: 'Agent Diagnosis' },
  { id: 'events', label: 'Events' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'policy', label: 'Policy' },
  { id: 'sdk', label: 'SDK Integration' },
  { id: 'settings', label: 'Project Settings' },
] as const;

export type ViewId = (typeof VIEWS)[number]['id'];

function parseHash(): ViewId {
  const id = window.location.hash.replace(/^#\/?/, '');
  return (VIEWS.find((view) => view.id === id)?.id ?? 'overview') as ViewId;
}

/** Hash-based routing (`#/alerts`) so reloads keep the current view without server routes. */
export function useHashRoute(): [ViewId, (view: ViewId) => void] {
  const [view, setView] = useState<ViewId>(parseHash);

  useEffect(() => {
    const onChange = () => setView(parseHash());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  const navigate = useCallback((next: ViewId) => {
    if (parseHash() !== next) window.location.hash = `/${next}`;
    setView(next);
  }, []);

  return [view, navigate];
}
