import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fmtInt, fmtPercent } from '../lib/format';
import type { Summary } from '../types';
import { AXIS_PROPS, COLORS, GRID_PROPS, TooltipCard } from './common';

const ORDER = [
  { key: 'critical', label: 'Critical', color: COLORS.coral },
  { key: 'warning', label: 'Warning', color: COLORS.amber },
  { key: 'stable', label: 'Stable', color: COLORS.green },
  { key: 'unscored', label: 'Unscored', color: COLORS.unscored },
] as const;

interface Row {
  key: string;
  label: string;
  color: string;
  count: number;
  share: number;
}

export function severityRows(bySeverity: Summary['events_by_severity']): Row[] {
  const total = Object.values(bySeverity).reduce<number>((sum, n) => sum + (n ?? 0), 0);
  return ORDER.filter((item) => item.key !== 'unscored' || (bySeverity.unscored ?? 0) > 0).map((item) => {
    const count = bySeverity[item.key] ?? 0;
    return { ...item, count, share: total ? count / total : 0 };
  });
}

/** Event counts per severity. Bars are labelled with the count, so color is not the only cue. */
export function SeverityChart({ bySeverity }: { bySeverity: Summary['events_by_severity'] }) {
  const rows = severityRows(bySeverity);
  return (
    <div className="h-[240px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 20, right: 8, bottom: 0, left: 0 }} barCategoryGap="28%">
          <CartesianGrid {...GRID_PROPS} />
          <XAxis {...AXIS_PROPS} dataKey="label" tick={{ ...AXIS_PROPS.tick, fontFamily: 'Plus Jakarta Sans, sans-serif', fontSize: 12 }} />
          <YAxis {...AXIS_PROPS} width={40} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              const row = active ? (payload?.[0]?.payload as Row | undefined) : undefined;
              if (!row) return null;
              return (
                <TooltipCard
                  rows={[
                    { key: 'c', label: `${row.label} events`, value: fmtInt(row.count), color: row.color },
                    { key: 's', label: 'Share of events', value: fmtPercent(row.share, 1), color: row.color },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="count" name="Events" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
            {rows.map((row) => (
              <Cell key={row.key} fill={row.color} />
            ))}
            <LabelList dataKey="count" position="top" fill="#f4f4f5" fontSize={12} fontFamily="JetBrains Mono, monospace" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
