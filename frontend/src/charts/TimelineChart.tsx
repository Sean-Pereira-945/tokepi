import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fmtAxisTime, fmtCompact, fmtInt, fmtScore } from '../lib/format';
import { AXIS_PROPS, ChartLegend, COLORS, GRID_PROPS, timeDomain, TooltipCard, tooltipTime } from './common';
import type { EventPoint } from './points';

interface Props {
  points: EventPoint[];
  promptTokenLimit?: number;
}

/**
 * Prompt tokens (left axis) with retrieval and quality scores (fixed 0–1, right axis).
 * The right axis is a fixed score domain, not a rescaled second measure.
 */
export function TimelineChart({ points, promptTokenLimit }: Props) {
  const [start, end] = timeDomain(points);
  const span = end - start;
  const showDots = points.length <= 40;

  return (
    <div>
      <ChartLegend
        items={[
          { label: 'Prompt tokens (left)', color: COLORS.cyan },
          { label: 'Retrieval score (right)', color: COLORS.green },
          { label: 'Response quality (right)', color: COLORS.violet, dashed: true },
          ...(promptTokenLimit ? [{ label: 'Prompt token limit', color: COLORS.amber, dashed: true }] : []),
        ]}
      />
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
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
              yAxisId="tokens"
              width={48}
              tickFormatter={(value: number) => fmtCompact(value)}
              label={{ value: 'tokens', angle: -90, position: 'insideLeft', fill: COLORS.axis, fontSize: 11, dy: 20 }}
            />
            <YAxis
              {...AXIS_PROPS}
              yAxisId="score"
              orientation="right"
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              width={40}
              tickFormatter={(value: number) => value.toFixed(2)}
            />
            {promptTokenLimit !== undefined && (
              <ReferenceLine yAxisId="tokens" y={promptTokenLimit} stroke={COLORS.amber} strokeDasharray="4 4" strokeOpacity={0.7} ifOverflow="extendDomain" />
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
                      { key: 'p', label: 'Prompt tokens', value: fmtInt(point.prompt_tokens), color: COLORS.cyan },
                      { key: 'r', label: 'Retrieval', value: fmtScore(point.retrieval_score), color: COLORS.green },
                      { key: 'q', label: 'Quality', value: fmtScore(point.response_quality), color: COLORS.violet, dashed: true },
                    ]}
                    footer={`Event #${point.id} · ${point.severity ?? 'unscored'}`}
                  />
                );
              }}
            />
            <Line
              yAxisId="tokens"
              type="monotone"
              dataKey="prompt_tokens"
              name="Prompt tokens"
              stroke={COLORS.cyan}
              strokeWidth={2}
              dot={showDots ? { r: 2.5, strokeWidth: 0, fill: COLORS.cyan } : false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: '#050505' }}
              isAnimationActive={false}
            />
            <Line
              yAxisId="score"
              type="monotone"
              dataKey="retrieval_score"
              name="Retrieval score"
              stroke={COLORS.green}
              strokeWidth={2}
              dot={showDots ? { r: 2.5, strokeWidth: 0, fill: COLORS.green } : false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: '#050505' }}
              isAnimationActive={false}
            />
            <Line
              yAxisId="score"
              type="monotone"
              dataKey="response_quality"
              name="Response quality"
              stroke={COLORS.violet}
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={showDots ? { r: 2.5, strokeWidth: 0, fill: COLORS.violet } : false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: '#050505' }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
