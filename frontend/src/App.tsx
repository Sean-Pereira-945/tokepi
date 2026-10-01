import { useEffect, useState } from 'react';
import { CreateProjectModal } from './components/CreateProjectModal';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ErrorState, LoadingState } from './components/States';
import { TestTelemetryModal } from './components/TestTelemetryModal';
import { ToastProvider } from './components/Toasts';
import { useHashRoute, VIEWS, type ViewId } from './lib/route';
import { SessionProvider, useSession } from './state/session';
import { useWorkspace, WorkspaceProvider } from './state/workspace';
import { AgentDiagnosis } from './views/AgentDiagnosis';
import { Alerts } from './views/Alerts';
import { Analytics } from './views/Analytics';
import { Events } from './views/Events';
import { Logs } from './views/Logs';
import { NoProjects } from './views/NoProjects';
import { Overview } from './views/Overview';
import { Policy } from './views/Policy';
import { ProjectSettings } from './views/ProjectSettings';
import { SdkIntegration } from './views/SdkIntegration';
import { SignIn } from './views/SignIn';

function CurrentView({ view, onNavigate }: { view: ViewId; onNavigate: (view: ViewId) => void }) {
  switch (view) {
    case 'agents':
      return <AgentDiagnosis />;
    case 'logs':
      return <Logs onNavigate={onNavigate} />;
    case 'events':
      return <Events />;
    case 'alerts':
      return <Alerts />;
    case 'analytics':
      return <Analytics />;
    case 'policy':
      return <Policy />;
    case 'sdk':
      return <SdkIntegration onNavigate={onNavigate} />;
    case 'settings':
      return <ProjectSettings />;
    default:
      return <Overview onNavigate={onNavigate} />;
  }
}

function Shell() {
  const { projectsState, reloadProjects, project } = useWorkspace();
  const [view, navigate] = useHashRoute();
  const [menuOpen, setMenuOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    const label = VIEWS.find((v) => v.id === view)?.label ?? 'Overview';
    document.title = project ? `${label} · ${project.name} · DriftGuard` : 'DriftGuard';
  }, [view, project]);

  let main;
  if (projectsState.status === 'loading') main = <LoadingState label="Loading projects…" className="py-24" />;
  else if (projectsState.status === 'error') main = <ErrorState message={projectsState.message} onRetry={reloadProjects} className="py-24" />;
  else if (!project) main = <NoProjects onCreate={() => setCreating(true)} />;
  else main = <CurrentView key={project.project_id} view={view} onNavigate={navigate} />;

  return (
    <div className="min-h-dvh bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[80] focus:rounded-md focus:bg-cyan focus:px-3 focus:py-2 focus:text-black"
      >
        Skip to content
      </a>
      <Sidebar view={view} onNavigate={navigate} open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="workspace-grid min-h-dvh lg:pl-[248px]">
        <Header
          onOpenMenu={() => setMenuOpen(true)}
          menuOpen={menuOpen}
          onNewProject={() => setCreating(true)}
          onTestTelemetry={() => setTesting(true)}
        />
        <main id="main" tabIndex={-1} className="mx-auto max-w-[1600px] px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
          {main}
        </main>
      </div>
      <CreateProjectModal open={creating} onClose={() => setCreating(false)} />
      {project && testing && <TestTelemetryModal key={project.project_id} open onClose={() => setTesting(false)} />}
    </div>
  );
}

function Root() {
  const { state, retry } = useSession();
  if (state.status === 'checking') return <LoadingState label="Checking session…" className="min-h-dvh" />;
  if (state.status === 'error') {
    return (
      <main className="grid min-h-dvh place-items-center">
        <ErrorState message={state.message} onRetry={retry} />
      </main>
    );
  }
  if (state.status === 'signed-out') return <SignIn notice={state.notice} />;
  return (
    <WorkspaceProvider key={state.account.account_id}>
      <Shell />
    </WorkspaceProvider>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <SessionProvider>
        <Root />
      </SessionProvider>
    </ToastProvider>
  );
}
