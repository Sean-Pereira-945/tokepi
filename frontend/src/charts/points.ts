import { parseTime } from '../lib/format';
import type { Severity, TelemetryEvent } from '../types';

export interface EventPoint {
  id: number;
  t: number;
  prompt_tokens: number | null;
  context_length: number | null;
  retrieval_score: number | null;
  response_quality: number | null;
  risk_score: number | null;
  severity: Severity | null;
}

/** Events (newest first from the API) → chronological chart points. */
export function toPoints(events: TelemetryEvent[]): EventPoint[] {
  const points: EventPoint[] = [];
  for (const event of events) {
    const time = parseTime(event.created_at);
    if (!time) continue;
    points.push({
      id: event.id,
      t: time.getTime(),
      prompt_tokens: event.prompt_tokens,
      context_length: event.context_length,
      retrieval_score: event.retrieval_score,
      response_quality: event.response_quality,
      risk_score: event.risk_score,
      severity: event.severity,
    });
  }
  return points.sort((a, b) => a.t - b.t || a.id - b.id);
}
