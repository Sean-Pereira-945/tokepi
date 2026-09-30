import { RotateCcw, Save } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { api, errorMessage } from '../api';
import { Button } from '../components/Button';
import { TextField } from '../components/Field';
import { PageHeader, Panel } from '../components/Panel';
import { ResourceView } from '../components/States';
import { useToast } from '../components/Toasts';
import { useResource } from '../lib/useResource';
import { parseNumber } from '../lib/validation';
import { useProject, useWorkspace } from '../state/workspace';
import type { Policy as PolicyType, PolicyField } from '../types';

interface FieldSpec {
  key: PolicyField;
  label: string;
  help: string;
  step: number;
  min?: number;
  max?: number;
  validate: (value: number) => string | null;
}

const FIELDS: { group: string; description: string; fields: FieldSpec[] }[] = [
  {
    group: 'Drift thresholds',
    description: 'Each telemetry event is scored against these rules. Changes apply to new events and to summary violation rates.',
    fields: [
      {
        key: 'prompt_token_limit',
        label: 'Prompt token limit',
        help: 'Events with more prompt tokens than this count as prompt context inflation. Must be greater than 0.',
        step: 100,
        min: 0,
        validate: (v) => (v > 0 ? null : 'Must be greater than 0.'),
      },
      {
        key: 'context_length_limit',
        label: 'Context length limit',
        help: 'Events whose assembled context is longer than this are flagged. Must be greater than 0.',
        step: 100,
        min: 0,
        validate: (v) => (v > 0 ? null : 'Must be greater than 0.'),
      },
      {
        key: 'retrieval_score_floor',
        label: 'Retrieval score floor',
        help: 'Retrieval scores below this count as retrieval degradation. Between 0 and 1.',
        step: 0.05,
        min: 0,
        max: 1,
        validate: (v) => (v >= 0 && v <= 1 ? null : 'Must be between 0 and 1.'),
      },
      {
        key: 'response_quality_floor',
        label: 'Response quality floor',
        help: 'Response quality below this counts as quality degradation. Between 0 and 1.',
        step: 0.05,
        min: 0,
        max: 1,
        validate: (v) => (v >= 0 && v <= 1 ? null : 'Must be between 0 and 1.'),
      },
    ],
  },
  {
    group: 'Agent diagnosis',
    description: 'How failed tool attempts turn into blocked tasks and agent alerts.',
    fields: [
      {
        key: 'blocked_after_failures',
        label: 'Blocked after failures',
        help: 'Consecutive failures of the same tool before a task is marked blocked and an alert is raised. Whole number, 1–100.',
        step: 1,
        min: 1,
        max: 100,
        validate: (v) => (Number.isInteger(v) && v >= 1 && v <= 100 ? null : 'Whole number between 1 and 100.'),
      },
      {
        key: 'retry_window_minutes',
        label: 'Retry window (minutes)',
        help: 'Failures further apart than this start a new run. 0–10080 (one week); 0 turns the window off.',
        step: 5,
        min: 0,
        max: 10080,
        validate: (v) => (v >= 0 && v <= 10080 ? null : 'Must be between 0 and 10080.'),
      },
    ],
  },
];

const ALL_FIELDS = FIELDS.flatMap((g) => g.fields);

type Draft = Record<PolicyField, string>;

function toDraft(policy: PolicyType): Draft {
  return Object.fromEntries(ALL_FIELDS.map((f) => [f.key, String(policy[f.key])])) as Draft;
}

function PolicyForm({ policy, onSaved }: { policy: PolicyType; onSaved: (policy: PolicyType) => void }) {
  const project = useProject();
  const { refreshAll } = useWorkspace();
  const toast = useToast();
  const [draft, setDraft] = useState<Draft>(() => toDraft(policy));
  const [errors, setErrors] = useState<Partial<Record<PolicyField, string>>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);

  // Reset the form only when the stored values change, so a background refresh keeps edits.
  const policyKey = JSON.stringify(policy);
  useEffect(() => {
    setDraft(toDraft(policy));
    setErrors({});
  }, [policyKey]);

  const dirty = ALL_FIELDS.some((f) => parseNumber(draft[f.key]) !== policy[f.key]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setStatus(null);
    const next: typeof errors = {};
    const body: Partial<PolicyType> = {};
    for (const field of ALL_FIELDS) {
      const value = parseNumber(draft[field.key]);
      if (value === null || Number.isNaN(value)) {
        next[field.key] = 'Enter a number.';
        continue;
      }
      const problem = field.validate(value);
      if (problem) next[field.key] = problem;
      else if (value !== policy[field.key]) body[field.key] = value;
    }
    setErrors(next);
    if (Object.keys(next).length) {
      setStatus({ tone: 'error', text: 'Fix the highlighted fields.' });
      return;
    }
    if (!Object.keys(body).length) {
      setStatus({ tone: 'success', text: 'No changes to save.' });
      return;
    }
    setBusy(true);
    try {
      const saved = await api.updatePolicy(project.project_id, body);
      onSaved(saved);
      refreshAll();
      setStatus({ tone: 'success', text: 'Policy saved.' });
      toast.push({ tone: 'success', title: 'Policy saved', message: 'New events are scored with the updated thresholds.' });
    } catch (error) {
      setStatus({ tone: 'error', text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      {FIELDS.map((group) => (
        <Panel key={group.group} title={group.group} description={group.description}>
          <div className="grid gap-5 md:grid-cols-2">
            {group.fields.map((field) => (
              <TextField
                key={field.key}
                label={field.label}
                type="number"
                inputMode="decimal"
                step={field.step}
                min={field.min}
                max={field.max}
                value={draft[field.key]}
                onChange={(e) => setDraft({ ...draft, [field.key]: e.target.value })}
                error={errors[field.key]}
                help={field.help}
              />
            ))}
          </div>
        </Panel>
      ))}
      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t border-hairline bg-black/90 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
        <Button type="submit" variant="primary" busy={busy} disabled={!dirty && !busy} icon={<Save aria-hidden className="size-4" />}>
          Save policy
        </Button>
        <Button
          onClick={() => {
            setDraft(toDraft(policy));
            setErrors({});
            setStatus(null);
          }}
          disabled={!dirty || busy}
          icon={<RotateCcw aria-hidden className="size-4" />}
        >
          Reset
        </Button>
        <span aria-live="polite" className={`text-[13px] ${status?.tone === 'error' ? 'text-coral' : 'text-green'}`}>
          {status?.text ?? (dirty ? <span className="text-amber">Unsaved changes</span> : '')}
        </span>
      </div>
    </form>
  );
}

export function Policy() {
  const project = useProject();
  const { refreshKey } = useWorkspace();
  const [saved, setSaved] = useState<PolicyType | null>(null);
  const policy = useResource<PolicyType>((signal) => api.getPolicy(project.project_id, signal), `policy|${project.project_id}`, refreshKey);

  useEffect(() => setSaved(null), [project.project_id, policy.data]);

  return (
    <>
      <PageHeader
        title="Policy"
        description="Thresholds that score telemetry and decide when an agent task is blocked. Reset discards unsaved edits."
      />
      <ResourceView resource={policy} loadingLabel="Loading policy…">
        {(data) => <PolicyForm policy={saved ?? data} onSaved={setSaved} />}
      </ResourceView>
    </>
  );
}
