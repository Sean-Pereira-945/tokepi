import { KeyRound, Trash2 } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { api, errorMessage } from '../api';
import { Button } from '../components/Button';
import { OneTimeSecret } from '../components/Copy';
import { TextField } from '../components/Field';
import { Modal } from '../components/Overlay';
import { PageHeader, Panel } from '../components/Panel';
import { useToast } from '../components/Toasts';
import { fmtDateTime } from '../lib/format';
import { useProject, useWorkspace } from '../state/workspace';

function RotateKeyDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const project = useProject();
  const { upsertProject } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);

  const close = () => {
    setBusy(false);
    setError(null);
    setNewKey(null);
    onClose();
  };

  const rotate = async () => {
    setBusy(true);
    setError(null);
    try {
      const { api_key, ...rest } = await api.rotateApiKey(project.project_id);
      upsertProject(rest);
      setNewKey(api_key);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (newKey) {
    return (
      <Modal
        open={open}
        onClose={close}
        title="New API key"
        description="The previous key has stopped working. Update your SDK configuration with this one."
        footer={
          <Button variant="primary" onClick={close}>
            I’ve saved the key
          </Button>
        }
      >
        <OneTimeSecret value={newKey} />
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Rotate API key?"
      description={
        <>
          A new key is issued for <span className="font-mono text-body">{project.project_id}</span> and the current key (
          <span className="font-mono">{project.api_key_hint}…</span>) stops working immediately. Any application still
          using it will fail to send telemetry until updated.
        </>
      }
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button variant="danger" busy={busy} onClick={() => void rotate()} icon={<KeyRound aria-hidden className="size-4" />}>
            Rotate key
          </Button>
        </>
      }
    >
      {error ? (
        <p role="alert" className="rounded-md border border-coral/40 bg-coral/5 px-3 py-2 text-[13px] text-coral">
          {error}
        </p>
      ) : (
        <p className="text-[13px] text-muted">The new key is shown once, right after rotation.</p>
      )}
    </Modal>
  );
}

function DeleteProjectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const project = useProject();
  const { removeProject } = useWorkspace();
  const toast = useToast();
  const [confirmText, setConfirmText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    setConfirmText('');
    setError(null);
    onClose();
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (confirmText !== project.project_id) return;
    setBusy(true);
    setError(null);
    const id = project.project_id;
    try {
      await api.deleteProject(id);
      toast.push({ tone: 'success', title: 'Project deleted', message: `${id} and all of its data were removed.` });
      close();
      removeProject(id);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title="Delete project?"
      description="This permanently deletes the project and all of its events, agent events, alerts and policy. It can’t be undone."
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button
            type="submit"
            form="delete-project-form"
            variant="danger"
            busy={busy}
            disabled={confirmText !== project.project_id}
            icon={<Trash2 aria-hidden className="size-4" />}
          >
            Delete project
          </Button>
        </>
      }
    >
      <form id="delete-project-form" onSubmit={onSubmit} noValidate className="space-y-3">
        <TextField
          label={`Type ${project.project_id} to confirm`}
          mono
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          data-autofocus
        />
        {error && (
          <p role="alert" className="rounded-md border border-coral/40 bg-coral/5 px-3 py-2 text-[13px] text-coral">
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}

export function ProjectSettings() {
  const project = useProject();
  const [dialog, setDialog] = useState<'rotate' | 'delete' | null>(null);

  const details: [string, string][] = [
    ['Project ID', project.project_id],
    ['Name', project.name],
    ['Environment', project.environment],
    ['API key', `${project.api_key_hint}…`],
    ['Created', fmtDateTime(project.created_at)],
    ['Account ID', project.account_id],
  ];

  return (
    <>
      <PageHeader title="Project Settings" description="Project details, API key rotation and deletion." />
      <div className="max-w-3xl space-y-6">
        <Panel title="Details">
          <dl className="grid gap-x-6 gap-y-4 text-[13px] sm:grid-cols-2">
            {details.map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="mt-0.5 font-mono break-all text-body">{value}</dd>
              </div>
            ))}
          </dl>
        </Panel>

        <Panel title="API key" description="Used by the SDK to send telemetry and agent events for this project.">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="max-w-md text-[13px] text-muted">
              Keys are stored as hashes, so a lost key can’t be recovered. Rotating issues a new key and disables{' '}
              <span className="font-mono text-body">{project.api_key_hint}…</span> immediately.
            </p>
            <Button onClick={() => setDialog('rotate')} icon={<KeyRound aria-hidden className="size-4" />}>
              Rotate API key
            </Button>
          </div>
        </Panel>

        <Panel title="Danger zone" className="border-coral/30">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="max-w-md text-[13px] text-muted">
              Delete this project with all of its telemetry, agent events, alerts and policy.
            </p>
            <Button variant="danger" onClick={() => setDialog('delete')} icon={<Trash2 aria-hidden className="size-4" />}>
              Delete project
            </Button>
          </div>
        </Panel>
      </div>
      <RotateKeyDialog open={dialog === 'rotate'} onClose={() => setDialog(null)} />
      <DeleteProjectDialog open={dialog === 'delete'} onClose={() => setDialog(null)} />
    </>
  );
}
