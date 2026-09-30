import type { ReactNode } from 'react';
import { fmtDateTime } from '../lib/format';

export const COLORS = {
  cyan: '#28C7D9',
  green: '#42D392',
  amber: '#F2B84B',
  coral: '#F06464',
  violet: '#A78BFA',
  muted: '#A1A1AA',
  grid: '#1c1c1f',
  axis: '#71717a',
  unscored: '#71717a',
} as const;

export const AXIS_PROPS = {
  stroke: COLORS.grid,
  tick: { fill: COLORS.axis, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
  tickLine: false,
  axisLine: { stroke: COLORS.grid },
} as const;

export const GRID_PROPS = { stroke: COLORS.grid, strokeDasharray: '0', vertical: false } as const;

export interface TooltipRow {
  key: string;
  label: string;
  value: string;
  color: string;
  dashed?: boolean;
}

/** Shared dark tooltip body. Values are pre-formatted by the chart. */
export function TooltipCard({ title, rows, footer }: { title?: string; rows: TooltipRow[]; footer?: ReactNode }) {
  return (
    <div className="min-w-44 rounded-md border border-hairline-strong bg-raised px-3 py-2 text-xs shadow-xl shadow-black/60">
      {title && <p className="mb-1.5 font-mono text-[11px] text-muted">{title}</p>}
      <ul className="space-y-1">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-0.5 w-3 shrink-0 rounded-full"
              style={{ background: row.dashed ? `repeating-linear-gradient(90deg, ${row.color} 0 3px, transparent 3px 5px)` : row.color }}
            />
            <span className="flex-1 text-muted">{row.label}</span>
            <span className="tabular font-mono font-semibold text-ink">{row.value}</span>
          </li>
        ))}
      </ul>
      {footer && <div className="mt-1.5 border-t border-hairline pt-1.5 text-muted">{footer}</div>}
    </div>
  );
}

export function tooltipTime(value: unknown): string {
  return typeof value === 'number' ? fmtDateTime(new Date(value).toISOString()) : '';
}

export interface LegendItem {
  label: string;
  color: string;
  dashed?: boolean;
  shape?: 'line' | 'dot' | 'square' | 'triangle' | 'diamond';
}

/** HTML legend so identity never depends on color alone (dashes and shapes differ). */
export function ChartLegend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted" aria-label="Legend">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <LegendSwatch item={item} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function LegendSwatch({ item }: { item: LegendItem }) {
  const shape = item.shape ?? 'line';
  if (shape === 'line') {
    return (
      <svg aria-hidden width="16" height="8" viewBox="0 0 16 8">
        <line x1="0" y1="4" x2="16" y2="4" stroke={item.color} strokeWidth="2" strokeDasharray={item.dashed ? '4 3' : undefined} />
      </svg>
    );
  }
  return (
    <svg aria-hidden width="10" height="10" viewBox="0 0 10 10">
      {shape === 'dot' && <circle cx="5" cy="5" r="4" fill={item.color} />}
      {shape === 'square' && <rect x="1" y="1" width="8" height="8" rx="1.5" fill={item.color} />}
      {shape === 'triangle' && <path d="M5 1 9 9H1Z" fill={item.color} />}
      {shape === 'diamond' && <path d="M5 0.5 9.5 5 5 9.5 0.5 5Z" fill={item.color} />}
    </svg>
  );
}

export function timeDomain(points: { t: number }[]): [number, number] {
  if (!points.length) return [0, 1];
  const min = points[0].t;
  const max = points[points.length - 1].t;
  if (min === max) return [min - 60_000, max + 60_000];
  return [min, max];
}
