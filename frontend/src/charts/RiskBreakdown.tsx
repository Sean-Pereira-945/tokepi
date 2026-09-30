import { fmtInt, fmtPercent, fmtScore } from '../lib/format';
import type { Policy, ViolationRates } from '../types';

const RULES: { key: keyof ViolationRates; label: string; describe: (policy: Policy) => string }[] = [
  { key: 'prompt_token_limit', label: 'Prompt tokens over limit', describe: (p) => `> ${fmtInt(p.prompt_token_limit)} tokens` },
  { key: 'context_length_limit', label: 'Context length over limit', describe: (p) => `> ${fmtInt(p.context_length_limit)}` },
  { key: 'retrieval_score_floor', label: 'Retrieval below floor', describe: (p) => `< ${fmtScore(p.retrieval_score_floor)}` },
  { key: 'response_quality_floor', label: 'Quality below floor', describe: (p) => `< ${fmtScore(p.response_quality_floor)}` },
];

function tone(rate: number): { bar: string; text: string } {
  if (rate >= 0.5) return { bar: 'bg-coral', text: 'text-coral' };
  if (rate > 0) return { bar: 'bg-amber', text: 'text-amber' };
  return { bar: 'bg-green', text: 'text-green' };
}

/** Share of events in the window that broke each policy rule (`summary.violation_rates`). */
export function RiskBreakdown({ rates, policy }: { rates: ViolationRates; policy: Policy }) {
  return (
    <ul className="space-y-4">
      {RULES.map((rule) => {
        const rate = rates[rule.key];
        const t = tone(rate);
        return (
          <li key={rule.key}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-[13px]">
              <span className="text-body">
                {rule.label}
                <span className="ml-2 font-mono text-[11px] text-muted">{rule.describe(policy)}</span>
              </span>
              <span className={`tabular font-mono font-semibold ${t.text}`}>{fmtPercent(rate, rate > 0 && rate < 0.1 ? 1 : 0)}</span>
            </div>
            <div
              className="h-2 overflow-hidden rounded-full bg-white/[0.04]"
              role="meter"
              aria-label={`${rule.label}: share of events`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(rate * 100)}
            >
              <div className={`h-full rounded-full ${t.bar} transition-[width] duration-200`} style={{ width: `${Math.max(rate * 100, rate > 0 ? 1.5 : 0)}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
