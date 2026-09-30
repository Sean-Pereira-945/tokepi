import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fmtAxisTime, fmtCompact } from '../lib/format';
import { AXIS_PROPS, ChartLegend, COLORS, GRID_PROPS, timeDomain, TooltipCard, tooltipTime } from './common';
import type { EventPoint } from './points';

type NumericKey = 'context_length' | 'prompt_tokens' | 'retrieval_score' | 'response_quality' | 'risk_score';

interface Props {
  points: EventPoint[];
  dataKey: NumericKey;
  label: string;
  color: string;
  format: (value: number | null) => string;
  threshold?: { value: number; label: string };
  scoreDomain?: boolean;
}

/** Single-series time chart with an optional policy threshold line. */
export function MetricLineChart({ points, dataKey, label, color, format, threshold, scoreDomain = false }: Props) {
  const [start, end] = timeDomain(points);
  const span = end - start;
  return (
    <div>
      <ChartLegend
        items={[
          { label, color },
          ...(threshold ? [{ label: threshold.label, color: COLORS.amber, dashed: true }] : []),
        ]}
      />
      <div className="h-[240px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis
              {...AXIS_PROPS}
              dataKey="t"
              type="number"
              scale="time"
              domain={[start, end]}
              tickFormatter={(value: number) => fmtAxisTime(value, span)}
              minTickGap={48}
            />
            <YAxis
              {...AXIS_PROPS}
              width={48}
              domain={scoreDomain ? [0, 1] : ['auto', 'auto']}
              tickFormatter={(value: number) => (scoreDomain ? value.toFixed(2) : fmtCompact(value))}
            />
            {threshold && (
              <ReferenceLine y={threshold.value} stroke={COLORS.amber} strokeDasharray="4 4" strokeOpacity={0.7} ifOverflow="extendDomain" />
            )}
            <Tooltip
              cursor={{ stroke: '#3f3f46', strokeWidth: 1 }}
              isAnimationActive={false}
              content={({ active, payload }) => {
                const point = active ? (payload?.[0]?.payload as EventPoint | undefined) : undefined;
                if (!point) return null;
                return (
                  <TooltipCard
                    title={tooltipTime(point.t)}
                    rows={[
                      { key: 'v', label, value: format(point[dataKey]), color },
                      ...(threshold ? [{ key: 't', label: threshold.label, value: format(threshold.value), color: COLORS.amber, dashed: true }] : []),
                    ]}
                    footer={`Event #${point.id}`}
                  />
                );
              }}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              name={label}
              stroke={color}
              strokeWidth={2}
              dot={points.length <= 40 ? { r: 2.5, strokeWidth: 0, fill: color } : false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: '#050505' }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
