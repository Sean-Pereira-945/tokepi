import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, ApiError, errorMessage, getToken, setToken, setUnauthorizedHandler } from '../api';
import type { Account, Session } from '../types';

type SessionState =
  | { status: 'checking' }
  | { status: 'signed-out'; notice?: string }
  | { status: 'error'; message: string }
  | { status: 'signed-in'; account: Account; token: string };

interface SessionContextValue {
  state: SessionState;
  signIn: (session: Session) => void;
  signOut: () => Promise<void>;
  /** Drop the local session without calling the server (e.g. after a 401). */
  expire: (notice?: string) => void;
  retry: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>(() => (getToken() ? { status: 'checking' } : { status: 'signed-out' }));
  const [attempt, setAttempt] = useState(0);

  const expire = useCallback((notice?: string) => {
    setToken(null);
    setState({ status: 'signed-out', notice });
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => expire('Your session has ended. Sign in again.'));
    return () => setUnauthorizedHandler(null);
  }, [expire]);

  // Validate a stored token on load.
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const controller = new AbortController();
    api.me(controller.signal).then(
      (account) => setState({ status: 'signed-in', account, token }),
      (error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 401) return; // handler already signed out
        setState({ status: 'error', message: errorMessage(error) });
      },
    );
    return () => controller.abort();
  }, [attempt]);

  const signIn = useCallback((session: Session) => {
    setToken(session.token);
    const account: Account = {
      account_id: session.account_id,
      name: session.name,
      email: session.email,
      created_at: session.created_at,
    };
    setState({ status: 'signed-in', account, token: session.token });
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // The local session is cleared regardless.
    }
    expire();
  }, [expire]);

  const retry = useCallback(() => {
    setState({ status: 'checking' });
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo(() => ({ state, signIn, signOut, expire, retry }), [state, signIn, signOut, expire, retry]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}

/** Account and token for components rendered only when signed in. */
export function useSignedIn(): { account: Account; token: string; signOut: () => Promise<void>; expire: (n?: string) => void } {
  const { state, signOut, expire } = useSession();
  if (state.status !== 'signed-in') throw new Error('useSignedIn requires a signed-in session');
  return { account: state.account, token: state.token, signOut, expire };
}
