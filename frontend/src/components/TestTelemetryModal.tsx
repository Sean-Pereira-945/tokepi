import { Send } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { api, errorMessage } from '../api';
import { fmtScore, humanize } from '../lib/format';
import { parseNumber } from '../lib/validation';
import { useProject, useWorkspace } from '../state/workspace';
import { ENVIRONMENTS, type Environment, type EventIngestRequest, type EventIngestResponse } from '../types';
import { SeverityBadge } from './Badges';
import { Button } from './Button';
import { SelectField, TextField } from './Field';
import { Modal } from './Overlay';
import { Eyebrow } from './Panel';

type MetricKey = 'prompt_tokens' | 'context_length' | 'retrieval_score' | 'response_quality';

const METRICS: { key: MetricKey; label: string; help: string; score: boolean }[] = [
  { key: 'prompt_tokens', label: 'Prompt tokens', help: 'Tokens sent in the prompt (≥ 0).', score: false },
  { key: 'context_length', label: 'Context length', help: 'Size of the assembled context (≥ 0).', score: false },
  { key: 'retrieval_score', label: 'Retrieval score', help: 'Relevance of retrieved context, 0–1.', score: true },
  { key: 'response_quality', label: 'Response quality', help: 'Quality score of the response, 0–1.', score: true },
];

export function TestTelemetryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const project = useProject();
  const { refreshAll } = useWorkspace();
  const [values, setValues] = useState<Record<MetricKey, string>>({
    prompt_tokens: '',
    context_length: '',
    retrieval_score: '',
    response_quality: '',
  });
  const [environment, setEnvironment] = useState<Environment>(project.environment);
  const [errors, setErrors] = useState<Partial<Record<MetricKey | 'form', string>>>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<EventIngestResponse | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const body: EventIngestRequest = { environment };
    const next: typeof errors = {};
    for (const metric of METRICS) {
      const parsed = parseNumber(values[metric.key]);
      if (parsed === null) continue;
      if (Number.isNaN(parsed) || parsed < 0 || (metric.score && parsed > 1)) {
        next[metric.key] = metric.score ? 'Enter a number between 0 and 1.' : 'Enter a number ≥ 0.';
        continue;
      }
      body[metric.key] = parsed;
    }
    if (!Object.keys(next).length && METRICS.every((m) => body[m.key] === undefined)) {
      next.form = 'Enter at least one metric.';
    }
    setErrors(next);
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      const response = await api.sendTestEvent(project.project_id, body);
      setResult(response);
      refreshAll();
    } catch (error) {
      setErrors({ form: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Test Telemetry"
      description={
        <>
          Send one event to <span className="font-mono text-body">{project.project_id}</span>. It’s scored against the
          project policy and stored like SDK telemetry.
        </>
      }
      footer={
        <>
          <Button onClick={onClose}>{result ? 'Close' : 'Cancel'}</Button>
          <Button
            type="submit"
            form="test-telemetry-form"
            variant="primary"
            busy={busy}
            icon={<Send aria-hidden className="size-4" />}
          >
            {result ? 'Send another' : 'Send event'}
          </Button>
        </>
      }
    >
      <form id="test-telemetry-form" onSubmit={onSubmit} noValidate className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {METRICS.map((metric, index) => (
            <TextField
              key={metric.key}
              label={metric.label}
              type="number"
              inputMode="decimal"
              min={0}
              max={metric.score ? 1 : undefined}
              step={metric.score ? 0.01 : 1}
              value={values[metric.key]}
              onChange={(e) => setValues({ ...values, [metric.key]: e.target.value })}
              error={errors[metric.key]}
              help={metric.help}
              data-autofocus={index === 0 ? true : undefined}
            />
          ))}
        </div>
        <SelectField
          label="Environment"
          value={environment}
          onChange={(e) => setEnvironment(e.target.value as Environment)}
          options={ENVIRONMENTS.map((env) => ({ value: env, label: env }))}
        />
        {errors.form && (
          <p role="alert" className="rounded-md border border-coral/40 bg-coral/5 px-3 py-2 text-[13px] text-coral">
            {errors.form}
          </p>
        )}
      </form>

      <div aria-live="polite">
        {result && (
          <div className="mt-5 space-y-3 rounded-md border border-hairline-strong bg-raised p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Eyebrow>Scored result</Eyebrow>
              <span className="text-xs text-green">Ingested · dashboard refreshed</span>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-muted">Severity</dt>
                <dd className="mt-1">
                  <SeverityBadge severity={result.severity} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Risk score</dt>
                <dd className="tabular mt-1 font-mono text-lg text-ink">{fmtScore(result.risk_score, 3)}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-muted">Root cause</dt>
                <dd className="mt-1 text-body">{result.root_cause || 'No policy rule violated'}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-muted">Recommendation</dt>
                <dd className="mt-1 font-mono text-[13px] text-body">{humanize(result.recommendation)}</dd>
              </div>
              {result.actions.length > 0 && (
                <div className="col-span-2">
                  <dt className="text-xs text-muted">Suggested actions</dt>
                  <dd className="mt-1">
                    <ul className="list-inside list-disc text-[13px] text-body">
                      {result.actions.map((action) => (
                        <li key={action}>{humanize(action)}</li>
                      ))}
                    </ul>
                  </dd>
                </div>
              )}
            </dl>
            {result.severity === 'critical' && (
              <p className="text-xs text-muted">Critical events raise a drift alert unless a matching one is already open.</p>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
