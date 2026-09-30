import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { errorMessage } from '../api';

export interface Resource<T> {
  data: T | undefined;
  error: string | null;
  /** True while a request is in flight (including background refreshes). */
  loading: boolean;
  reload: () => void;
}

/**
 * Fetch data for a view.
 *
 * - `key` identifies *what* is loaded (project, filters, …). When it changes the
 *   previous data is dropped so one project's data never shows under another.
 * - `refresh` is a counter; bumping it re-fetches while keeping the current data
 *   on screen until the new response arrives.
 * - Pass `fetcher = null` to stay idle.
 */
export function useResource<T>(
  fetcher: ((signal: AbortSignal) => Promise<T>) | null,
  key: string,
  refresh = 0,
): Resource<T> {
  const [state, setState] = useState<{ key: string; data: T | undefined; error: string | null; loading: boolean }>({
    key,
    data: undefined,
    error: null,
    loading: fetcher !== null,
  });
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const enabled = fetcher !== null;

  useEffect(() => {
    const run = fetcherRef.current;
    if (!run) {
      setState({ key, data: undefined, error: null, loading: false });
      return;
    }
    const controller = new AbortController();
    setState((prev) =>
      prev.key === key
        ? { ...prev, loading: true }
        : { key, data: undefined, error: null, loading: true },
    );
    run(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ key, data, error: null, loading: false });
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setState((prev) => ({
          key,
          data: prev.key === key ? prev.data : undefined,
          error: errorMessage(error),
          loading: false,
        }));
      },
    );
    return () => controller.abort();
  }, [key, refresh, tick, enabled]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  const current = state.key === key;
  const data = current ? state.data : undefined;
  const error = current ? state.error : null;
  const loading = current ? state.loading : enabled;
  return useMemo(() => ({ data, error, loading, reload }), [data, error, loading, reload]);
}
