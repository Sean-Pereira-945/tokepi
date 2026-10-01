import { useEffect, useRef, useState } from 'react';
import { REALTIME_PROTOCOL, realtimeUrl } from '../api';
import type { ActivityMessage, Alert, AlertAction, AlertMessage } from '../types';

export type ConnectionState = 'idle' | 'connecting' | 'live' | 'reconnecting' | 'offline';

interface Handlers {
  onAlert: (alert: Alert, action: AlertAction) => void;
  /** New agent events were ingested for the project. */
  onActivity: (count: number) => void;
  /** The server closed with 4401 (bad or expired credentials). */
  onAuthFailure: () => void;
  /** The socket closed before it ever opened (server unreachable); the caller may check the session. */
  onHandshakeFailure: () => void;
}

const MAX_DELAY_MS = 30_000;
const OFFLINE_AFTER_ATTEMPTS = 4;

function isAlertMessage(value: unknown): value is AlertMessage {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as { type?: unknown }).type === 'alert' &&
    typeof (value as { alert?: unknown }).alert === 'object'
  );
}

function isActivityMessage(value: unknown): value is ActivityMessage {
  return typeof value === 'object' && value !== null && (value as { type?: unknown }).type === 'activity';
}

/**
 * Keep one WebSocket open to `/ws/projects/{id}` and reconnect with exponential
 * backoff (capped at 30s). Closes when the project or token changes.
 */
export function useRealtime(projectId: string | null, token: string | null, handlers: Handlers): ConnectionState {
  const [state, setState] = useState<ConnectionState>('idle');
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!projectId || !token) {
      setState('idle');
      return;
    }
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let attempts = 0;
    let disposed = false;

    const connect = () => {
      window.clearTimeout(timer);
      if (disposed) return;
      if (!navigator.onLine) {
        setState('offline');
        return;
      }
      setState(attempts === 0 ? 'connecting' : attempts >= OFFLINE_AFTER_ATTEMPTS ? 'offline' : 'reconnecting');
      let opened = false;
      const ws = new WebSocket(realtimeUrl(projectId), [REALTIME_PROTOCOL, token]);
      socket = ws;
      ws.onopen = () => {
        opened = true;
        attempts = 0;
        setState('live');
      };
      ws.onmessage = (event: MessageEvent) => {
        if (typeof event.data !== 'string') return;
        try {
          const parsed: unknown = JSON.parse(event.data);
          if (isAlertMessage(parsed)) handlersRef.current.onAlert(parsed.alert, parsed.action);
          else if (isActivityMessage(parsed)) handlersRef.current.onActivity(parsed.count);
        } catch {
          // Ignore malformed frames.
        }
      };
      ws.onclose = (event: CloseEvent) => {
        if (disposed || socket !== ws) return;
        socket = null;
        if (event.code === 4401) {
          setState('offline');
          handlersRef.current.onAuthFailure();
          return;
        }
        if (!opened) handlersRef.current.onHandshakeFailure();
        attempts += 1;
        setState(attempts >= OFFLINE_AFTER_ATTEMPTS || !navigator.onLine ? 'offline' : 'reconnecting');
        const delay = Math.min(MAX_DELAY_MS, 1000 * 2 ** (attempts - 1)) * (0.8 + Math.random() * 0.4);
        timer = window.setTimeout(connect, delay);
      };
    };

    const handleOnline = () => {
      if (!socket) {
        attempts = Math.min(attempts, 1);
        connect();
      }
    };
    const handleOffline = () => setState('offline');

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    connect();

    return () => {
      disposed = true;
      window.clearTimeout(timer);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      if (socket) {
        socket.onclose = null;
        socket.close(1000, 'client closed');
      }
    };
  }, [projectId, token]);

  return state;
}
