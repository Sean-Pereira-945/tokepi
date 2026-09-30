import { LogIn, UserPlus } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { api, errorMessage } from '../api';
import { Button } from '../components/Button';
import { TextField } from '../components/Field';
import { LogoMark } from '../components/Logo';
import { ErrorState, LoadingState } from '../components/States';
import { isEmail } from '../lib/validation';
import { useSession } from '../state/session';
import type { AuthConfig } from '../types';

type Mode = 'login' | 'register';

export function SignIn({ notice }: { notice?: string }) {
  const { signIn } = useSession();
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configTick, setConfigTick] = useState(0);
  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Partial<Record<'name' | 'email' | 'password', string>>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setConfigError(null);
    api.authConfig(controller.signal).then(
      (value) => setConfig(value),
      (error: unknown) => {
        if (!controller.signal.aborted) setConfigError(errorMessage(error));
      },
    );
    return () => controller.abort();
  }, [configTick]);

  const canRegister = config?.allow_signup === true;
  const activeMode: Mode = canRegister ? mode : 'login';

  const validate = () => {
    const next: typeof errors = {};
    if (activeMode === 'register' && !name.trim()) next.name = 'Enter your name.';
    if (!isEmail(email)) next.email = 'Enter a valid email address.';
    if (activeMode === 'register' ? password.length < 8 : !password) {
      next.password = activeMode === 'register' ? 'Use at least 8 characters.' : 'Enter your password.';
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setServerError(null);
    if (!validate()) return;
    setBusy(true);
    try {
      const session =
        activeMode === 'register'
          ? await api.register({ name: name.trim(), email: email.trim(), password })
          : await api.login({ email: email.trim(), password });
      signIn(session);
    } catch (error) {
      setServerError(errorMessage(error));
      setBusy(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setErrors({});
    setServerError(null);
  };

  return (
    <main className="workspace-grid flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-[400px] animate-rise">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <LogoMark className="size-10" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">DriftGuard</h1>
            <p className="mt-1 text-sm text-muted">
              {activeMode === 'register' ? 'Create an account to monitor your projects.' : 'Sign in to your workspace.'}
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-hairline-strong bg-panel p-5 sm:p-6">
          {config === null && !configError && <LoadingState label="Connecting to server…" className="py-8" />}
          {configError && config === null && (
            <ErrorState message={configError} onRetry={() => setConfigTick((n) => n + 1)} className="py-6" />
          )}
          {config !== null && (
            <form onSubmit={onSubmit} noValidate className="space-y-4">
              {notice && !serverError && (
                <p role="status" className="rounded-md border border-amber/40 bg-amber/5 px-3 py-2 text-[13px] text-body">
                  {notice}
                </p>
              )}
              {activeMode === 'register' && (
                <TextField
                  label="Name"
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  error={errors.name}
                  maxLength={128}
                />
              )}
              <TextField
                label="Email"
                type="email"
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={errors.email}
                autoFocus
              />
              <TextField
                label="Password"
                type="password"
                autoComplete={activeMode === 'register' ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                error={errors.password}
                help={activeMode === 'register' ? 'At least 8 characters.' : undefined}
                maxLength={256}
              />
              {serverError && (
                <p role="alert" className="rounded-md border border-coral/40 bg-coral/5 px-3 py-2 text-[13px] text-coral">
                  {serverError}
                </p>
              )}
              <Button
                type="submit"
                variant="primary"
                busy={busy}
                className="w-full"
                icon={activeMode === 'register' ? <UserPlus aria-hidden className="size-4" /> : <LogIn aria-hidden className="size-4" />}
              >
                {activeMode === 'register' ? 'Create account' : 'Sign in'}
              </Button>
            </form>
          )}
        </div>

        {canRegister && (
          <p className="mt-4 text-center text-[13px] text-muted">
            {activeMode === 'login' ? 'No account yet? ' : 'Already have an account? '}
            <button
              type="button"
              className="font-semibold text-cyan hover:underline"
              onClick={() => switchMode(activeMode === 'login' ? 'register' : 'login')}
            >
              {activeMode === 'login' ? 'Create one' : 'Sign in'}
            </button>
          </p>
        )}
        {config && !canRegister && (
          <p className="mt-4 text-center text-[13px] text-muted">Account creation is disabled on this server.</p>
        )}
        {config && <p className="mt-6 text-center font-mono text-[11px] text-[#52525b]">Server v{config.version}</p>}
      </div>
    </main>
  );
}
