import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { fmtCompact, fmtInt, fmtScore } from '../lib/format';
import { AXIS_PROPS, ChartLegend, COLORS, GRID_PROPS, TooltipCard, tooltipTime, type LegendItem } from './common';
import type { EventPoint } from './points';

interface Props {
  points: EventPoint[];
  promptTokenLimit?: number;
  qualityFloor?: number;
}

const GROUPS = [
  { key: 'critical', label: 'Critical', color: COLORS.coral, shape: 'triangle' as const },
  { key: 'warning', label: 'Warning', color: COLORS.amber, shape: 'diamond' as const },
  { key: 'stable', label: 'Stable', color: COLORS.green, shape: 'circle' as const },
  { key: 'unscored', label: 'Unscored', color: COLORS.unscored, shape: 'square' as const },
];

export function scatterable(points: EventPoint[]): number {
  return points.filter((p) => p.prompt_tokens !== null && p.response_quality !== null).length;
}

/** Prompt tokens vs response quality, one mark shape per severity. */
export function QualityScatter({ points, promptTokenLimit, qualityFloor }: Props) {
  const usable = points.filter((p) => p.prompt_tokens !== null && p.response_quality !== null);
  const groups = GROUPS.map((group) => ({
    ...group,
    data: usable.filter((p) => (p.severity ?? 'unscored') === group.key),
  })).filter((group) => group.data.length > 0);

  const legend: LegendItem[] = [
    ...groups.map((g) => ({
      label: `${g.label} (${g.data.length})`,
      color: g.color,
      shape: g.shape === 'circle' ? ('dot' as const) : g.shape,
    })),
    ...(promptTokenLimit !== undefined || qualityFloor !== undefined
      ? [{ label: 'Policy thresholds', color: COLORS.amber, dashed: true }]
      : []),
  ];

  return (
    <div>
      <ChartLegend items={legend} />
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
            <CartesianGrid {...GRID_PROPS} vertical />
            <XAxis
              {...AXIS_PROPS}
              type="number"
              dataKey="prompt_tokens"
              name="Prompt tokens"
              tickFormatter={(value: number) => fmtCompact(value)}
              label={{ value: 'prompt tokens', position: 'insideBottom', offset: -10, fill: COLORS.axis, fontSize: 11 }}
            />
            <YAxis
              {...AXIS_PROPS}
              type="number"
              dataKey="response_quality"
              name="Response quality"
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              width={44}
              tickFormatter={(value: number) => value.toFixed(2)}
            />
            <ZAxis range={[48, 48]} />
            {promptTokenLimit !== undefined && (
              <ReferenceLine x={promptTokenLimit} stroke={COLORS.amber} strokeDasharray="4 4" strokeOpacity={0.7} ifOverflow="extendDomain" />
            )}
            {qualityFloor !== undefined && (
              <ReferenceLine y={qualityFloor} stroke={COLORS.amber} strokeDasharray="4 4" strokeOpacity={0.7} />
            )}
            <Tooltip
              cursor={{ strokeDasharray: '3 3', stroke: '#3f3f46' }}
              isAnimationActive={false}
              content={({ active, payload }) => {
                const point = active ? (payload?.[0]?.payload as EventPoint | undefined) : undefined;
                if (!point) return null;
                const group = GROUPS.find((g) => g.key === (point.severity ?? 'unscored')) ?? GROUPS[3];
                return (
                  <TooltipCard
                    title={tooltipTime(point.t)}
                    rows={[
                      { key: 'p', label: 'Prompt tokens', value: fmtInt(point.prompt_tokens), color: group.color },
                      { key: 'q', label: 'Quality', value: fmtScore(point.response_quality), color: group.color },
                    ]}
                    footer={`Event #${point.id} · ${group.label}`}
                  />
                );
              }}
            />
            {groups.map((group) => (
              <Scatter
                key={group.key}
                name={group.label}
                data={group.data}
                fill={group.color}
                shape={group.shape}
                stroke="#050505"
                strokeWidth={1}
                isAnimationActive={false}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
