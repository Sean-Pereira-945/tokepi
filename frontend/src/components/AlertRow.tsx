import { CheckCircle2, RotateCcw } from 'lucide-react';
import type { ReactNode } from 'react';
import { fmtDateTime, fmtInt, fmtRelative } from '../lib/format';
import type { Alert } from '../types';
import { SeverityBadge, SourceBadge } from './Badges';
import { Button } from './Button';

const EDGE: Record<string, string> = {
  critical: 'border-l-coral',
  warning: 'border-l-amber',
  stable: 'border-l-green',
};

interface AlertRowProps {
  alert: Alert;
  onToggle?: (alert: Alert) => void;
  busy?: boolean;
  extra?: ReactNode;
}

export function AlertRow({ alert, onToggle, busy = false, extra }: AlertRowProps) {
  return (
    <li
      className={`flex flex-col gap-3 border-b border-l-2 border-b-hairline px-4 py-3 last:border-b-0 sm:flex-row sm:items-start ${EDGE[alert.severity] ?? 'border-l-hairline'} ${alert.resolved ? 'opacity-70' : ''}`}
    >
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={alert.severity} />
          <SourceBadge source={alert.source} />
          {alert.resolved && (
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-green">
              <CheckCircle2 aria-hidden className="size-3.5" /> Resolved
            </span>
          )}
          <time dateTime={alert.created_at} title={fmtDateTime(alert.created_at)} className="font-mono text-xs text-muted">
            {fmtRelative(alert.created_at)}
          </time>
        </div>
        <p className="text-[13px] leading-snug break-words text-body">{alert.message}</p>
        <dl className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
          <div className="flex gap-1.5">
            <dt>Tokens at stake</dt>
            <dd className="tabular font-mono text-body">{fmtInt(alert.saved_tokens)}</dd>
          </div>
          {alert.task_id && (
            <div className="flex gap-1.5">
              <dt>Task</dt>
              <dd className="font-mono text-body">{alert.task_id}</dd>
            </div>
          )}
          {alert.environment && (
            <div className="flex gap-1.5">
              <dt>Env</dt>
              <dd className="font-mono text-body">{alert.environment}</dd>
            </div>
          )}
          {alert.resolved_at && (
            <div className="flex gap-1.5">
              <dt>Resolved</dt>
              <dd className="font-mono text-body">{fmtDateTime(alert.resolved_at)}</dd>
            </div>
          )}
        </dl>
        {extra}
      </div>
      {onToggle && (
        <Button
          size="sm"
          busy={busy}
          onClick={() => onToggle(alert)}
          icon={alert.resolved ? <RotateCcw aria-hidden className="size-3.5" /> : <CheckCircle2 aria-hidden className="size-3.5" />}
          aria-label={`${alert.resolved ? 'Reopen' : 'Resolve'} alert ${alert.id}`}
        >
          {alert.resolved ? 'Reopen' : 'Resolve'}
        </Button>
      )}
    </li>
  );
}
