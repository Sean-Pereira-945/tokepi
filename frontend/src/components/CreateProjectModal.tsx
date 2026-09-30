import { FolderPlus } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { api, errorMessage } from '../api';
import { PROJECT_ID_PATTERN } from '../lib/validation';
import { useWorkspace } from '../state/workspace';
import { ENVIRONMENTS, type Environment, type ProjectWithKey } from '../types';
import { Button } from './Button';
import { OneTimeSecret } from './Copy';
import { SelectField, TextField } from './Field';
import { Modal } from './Overlay';

export function CreateProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { upsertProject, selectProject } = useWorkspace();
  const [projectId, setProjectId] = useState('');
  const [name, setName] = useState('');
  const [environment, setEnvironment] = useState<Environment>('prod');
  const [errors, setErrors] = useState<{ projectId?: string; name?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<ProjectWithKey | null>(null);

  const reset = () => {
    setProjectId('');
    setName('');
    setEnvironment('prod');
    setErrors({});
    setServerError(null);
    setBusy(false);
    setCreated(null);
  };

  const close = () => {
    if (created) selectProject(created.project_id);
    reset();
    onClose();
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const next: typeof errors = {};
    if (!PROJECT_ID_PATTERN.test(projectId)) {
      next.projectId = '1–64 characters: letters, digits, “-” and “_” only.';
    }
    if (!name.trim()) next.name = 'Enter a display name.';
    else if (name.trim().length > 128) next.name = 'Use 128 characters or fewer.';
    setErrors(next);
    setServerError(null);
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      const project = await api.createProject({ project_id: projectId, name: name.trim(), environment });
      const { api_key: _key, ...withoutKey } = project;
      upsertProject(withoutKey);
      setCreated(project);
    } catch (error) {
      setServerError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  if (created) {
    return (
      <Modal
        open={open}
        onClose={close}
        title="Project created"
        description={
          <>
            <span className="font-mono text-body">{created.project_id}</span> is ready. Use this key in the SDK to send
            telemetry.
          </>
        }
        footer={
          <Button variant="primary" onClick={close}>
            I’ve saved the key
          </Button>
        }
      >
        <OneTimeSecret value={created.api_key} />
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="New project"
      description="A project is one monitored application. Its ID appears in every API URL and can’t be changed."
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button
            type="submit"
            form="create-project-form"
            variant="primary"
            busy={busy}
            icon={<FolderPlus aria-hidden className="size-4" />}
          >
            Create project
          </Button>
        </>
      }
    >
      <form id="create-project-form" onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Project ID"
          mono
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          error={errors.projectId}
          help="Unique on this server. Letters, digits, “-” and “_”; up to 64 characters."
          placeholder="coding-agent"
          autoComplete="off"
          spellCheck={false}
          maxLength={64}
          data-autofocus
        />
        <TextField
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          placeholder="Coding Agent"
          maxLength={128}
        />
        <SelectField
          label="Default environment"
          value={environment}
          onChange={(e) => setEnvironment(e.target.value as Environment)}
          options={ENVIRONMENTS.map((env) => ({ value: env, label: env }))}
          help="Used as the project’s environment label."
        />
        {serverError && (
          <p role="alert" className="rounded-md border border-coral/40 bg-coral/5 px-3 py-2 text-[13px] text-coral">
            {serverError}
          </p>
        )}
      </form>
    </Modal>
  );
}
