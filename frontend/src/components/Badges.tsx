import { AlertOctagon, CheckCircle2, CircleDashed, RotateCcw, TriangleAlert, type LucideIcon } from 'lucide-react';
import type { AlertSource, Severity, TaskStatus } from '../types';

type Tone = 'green' | 'amber' | 'coral' | 'cyan' | 'violet' | 'neutral';

const TONES: Record<Tone, string> = {
  green: 'text-green border-green/30 bg-green/10',
  amber: 'text-amber border-amber/30 bg-amber/10',
  coral: 'text-coral border-coral/40 bg-coral/10',
  cyan: 'text-cyan border-cyan/30 bg-cyan/10',
  violet: 'text-violet border-violet/30 bg-violet/10',
  neutral: 'text-muted border-hairline-strong bg-white/[0.03]',
};

export function Badge({ tone, icon: Icon, children, title }: { tone: Tone; icon?: LucideIcon; children: string; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex h-6 items-center gap-1 rounded-md border px-2 text-xs font-semibold whitespace-nowrap ${TONES[tone]}`}
    >
      {Icon && <Icon aria-hidden className="size-3.5" />}
      {children}
    </span>
  );
}

export const SEVERITY_META: Record<Severity, { tone: Tone; icon: LucideIcon; label: string }> = {
  critical: { tone: 'coral', icon: AlertOctagon, label: 'Critical' },
  warning: { tone: 'amber', icon: TriangleAlert, label: 'Warning' },
  stable: { tone: 'green', icon: CheckCircle2, label: 'Stable' },
};

export function SeverityBadge({ severity }: { severity: Severity | null | undefined }) {
  if (!severity || !(severity in SEVERITY_META)) {
    return <Badge tone="neutral" icon={CircleDashed}>Unscored</Badge>;
  }
  const meta = SEVERITY_META[severity];
  return (
    <Badge tone={meta.tone} icon={meta.icon}>
      {meta.label}
    </Badge>
  );
}

const TASK_META: Record<TaskStatus, { tone: Tone; icon: LucideIcon; label: string }> = {
  blocked: { tone: 'coral', icon: AlertOctagon, label: 'Blocked' },
  failing: { tone: 'amber', icon: TriangleAlert, label: 'Failing' },
  recovered: { tone: 'cyan', icon: RotateCcw, label: 'Recovered' },
  healthy: { tone: 'green', icon: CheckCircle2, label: 'Healthy' },
};

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const meta = TASK_META[status] ?? { tone: 'neutral' as Tone, icon: CircleDashed, label: status };
  return (
    <Badge tone={meta.tone} icon={meta.icon}>
      {meta.label}
    </Badge>
  );
}

const SOURCE_LABEL: Record<AlertSource, string> = { manual: 'Manual', drift: 'Drift', agent: 'Agent' };

export function SourceBadge({ source }: { source: AlertSource }) {
  return (
    <span className="inline-flex h-6 items-center rounded-md border border-hairline-strong px-2 font-mono text-[11px] font-medium tracking-wide text-muted uppercase">
      {SOURCE_LABEL[source] ?? source}
    </span>
  );
}

/** Tool attempt status as reported by the agent (lowercased by the server). */
export function attemptTone(status: string): Tone {
  if (['failed', 'failure', 'error', 'timeout'].includes(status)) return 'coral';
  if (['success', 'succeeded', 'ok', 'completed'].includes(status)) return 'green';
  return 'neutral';
}
