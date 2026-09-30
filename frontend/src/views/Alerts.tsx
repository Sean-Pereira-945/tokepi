import { Plus } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { api, errorMessage } from '../api';
import { AlertRow } from '../components/AlertRow';
import { Button } from '../components/Button';
import { SelectField, TextAreaField } from '../components/Field';
import { PageHeader, Panel } from '../components/Panel';
import { EmptyState, ResourceView } from '../components/States';
import { useToast } from '../components/Toasts';
import { useProjectQuery } from '../state/queries';
import { useProject, useWorkspace } from '../state/workspace';
import type { Alert, Severity } from '../types';

type Tab = 'open' | 'resolved' | 'all';

const TABS: { id: Tab; label: string }[] = [
  { id: 'open', label: 'Open' },
  { id: 'resolved', label: 'Resolved' },
  { id: 'all', label: 'All' },
];

const SEVERITY_OPTIONS = [
  { value: 'all', label: 'All severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'warning', label: 'Warning' },
  { value: 'stable', label: 'Stable' },
];

function NewAlertForm() {
  const project = useProject();
  const { alertsChanged } = useWorkspace();
  const toast = useToast();
  const [severity, setSeverity] = useState<Severity>('warning');
  const [message, setMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const text = message.trim();
    if (!text) {
      setError('Enter a message.');
      return;
    }
    if (text.length > 2000) {
      setError('Use 2,000 characters or fewer.');
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await api.createAlert(project.project_id, { severity, message: text });
      setMessage('');
      alertsChanged();
      toast.push({ tone: 'success', title: 'Alert created' });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="New alert" description="Record a manual alert for this project.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <SelectField
          label="Severity"
          value={severity}
          onChange={(e) => setSeverity(e.target.value as Severity)}
          options={SEVERITY_OPTIONS.slice(1)}
        />
        <TextAreaField
          label="Message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          error={error}
          maxLength={2000}
          rows={3}
          placeholder="What needs attention?"
        />
        <Button type="submit" variant="primary" busy={busy} icon={<Plus aria-hidden className="size-4" />}>
          Create alert
        </Button>
      </form>
    </Panel>
  );
}

export function Alerts() {
  const project = useProject();
  const { alertsChanged } = useWorkspace();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>('open');
  const [severity, setSeverity] = useState<Severity | 'all'>('all');
  const [pending, setPending] = useState<number | null>(null);

  const alerts = useProjectQuery(
    'alerts',
    (id, f, signal) =>
      api.listAlerts(
        id,
        f,
        { resolved: tab === 'all' ? undefined : tab === 'resolved', severity: severity === 'all' ? undefined : severity, limit: 500 },
        signal,
      ),
    { key: `${tab}|${severity}`, watchAlerts: true },
  );

  const toggle = async (alert: Alert) => {
    setPending(alert.id);
    try {
      await api.setAlertResolved(project.project_id, alert.id, !alert.resolved);
      alertsChanged();
    } catch (error) {
      toast.push({ tone: 'error', title: alert.resolved ? 'Couldn’t reopen alert' : 'Couldn’t resolve alert', message: errorMessage(error) });
    } finally {
      setPending(null);
    }
  };

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Raised by critical drift, blocked agent tasks, or created manually. Newest first."
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Panel
          bodyClassName=""
          title="Active Alerts"
          actions={
            <>
              <div role="tablist" aria-label="Alert status" className="flex rounded-md border border-hairline-strong bg-input p-0.5">
                {TABS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={tab === item.id}
                    onClick={() => setTab(item.id)}
                    className={`min-h-8 rounded px-3 text-[13px] font-semibold transition-colors duration-150 ${tab === item.id ? 'bg-raised text-ink shadow-[inset_0_-2px_0_#28C7D9]' : 'text-muted hover:text-body'}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <SelectField
                label="Severity"
                hideLabel
                value={severity}
                onChange={(e) => setSeverity(e.target.value as Severity | 'all')}
                options={SEVERITY_OPTIONS}
                className="w-40"
              />
            </>
          }
        >
          <div role="tabpanel" aria-label={`${TABS.find((t) => t.id === tab)?.label} alerts`}>
            <ResourceView
              resource={alerts}
              isEmpty={(data) => data.length === 0}
              empty={
                <EmptyState title={tab === 'open' ? 'No open alerts' : tab === 'resolved' ? 'No resolved alerts' : 'No alerts'}>
                  Alerts in the selected time range and environment appear here.
                </EmptyState>
              }
            >
              {(data) => (
                <>
                  <ul>
                    {data.map((alert) => (
                      <AlertRow key={alert.id} alert={alert} onToggle={toggle} busy={pending === alert.id} />
                    ))}
                  </ul>
                  {data.length >= 500 && <p className="border-t border-hairline px-4 py-2 text-xs text-muted">Showing the latest 500 alerts.</p>}
                </>
              )}
            </ResourceView>
          </div>
        </Panel>
        <div>
          <NewAlertForm />
        </div>
      </div>
    </>
  );
}
