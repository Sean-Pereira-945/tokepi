import { FolderPlus } from 'lucide-react';
import { Button } from '../components/Button';
import { LogoMark } from '../components/Logo';

export function NoProjects({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="mx-auto flex max-w-lg animate-rise flex-col items-center py-20 text-center">
      <LogoMark className="mb-5 size-10" />
      <h1 className="text-2xl font-bold tracking-tight">Create your first project</h1>
      <p className="mt-2 text-sm text-muted">
        A project is one monitored application — an LLM service or an AI coding agent. Creating one gives you an API key
        for the SDK to send telemetry and agent events.
      </p>
      <Button variant="primary" className="mt-6" onClick={onCreate} icon={<FolderPlus aria-hidden className="size-4" />}>
        Create Project
      </Button>
    </div>
  );
}
