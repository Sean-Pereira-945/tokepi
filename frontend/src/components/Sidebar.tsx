import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  Code2,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings,
  SlidersHorizontal,
  X,
  type LucideIcon,
} from 'lucide-react';
import { VIEWS, type ViewId } from '../lib/route';
import { useSignedIn } from '../state/session';
import { useWorkspace } from '../state/workspace';
import { ConnectionIndicator } from './ConnectionIndicator';
import { Logo } from './Logo';

const ICONS: Record<ViewId, LucideIcon> = {
  overview: LayoutDashboard,
  agents: Bot,
  logs: ScrollText,
  events: Activity,
  alerts: Bell,
  analytics: BarChart3,
  policy: SlidersHorizontal,
  sdk: Code2,
  settings: Settings,
};

interface SidebarProps {
  view: ViewId;
  onNavigate: (view: ViewId) => void;
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ view, onNavigate, open, onClose }: SidebarProps) {
  const { account, signOut } = useSignedIn();
  const { summary, project } = useWorkspace();
  const openAlerts = summary.data?.open_alerts;
  const critical = (summary.data?.critical_alerts ?? 0) > 0;

  return (
    <>
      {open && <div aria-hidden className="fixed inset-0 z-30 animate-fade bg-black/70 lg:hidden" onClick={onClose} />}
      <aside
        id="app-sidebar"
        aria-label="Primary"
        className={`fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col border-r border-hairline bg-sidebar transition-transform duration-200 ease-out lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex h-16 items-center justify-between border-b border-hairline px-5">
          <Logo />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="grid size-9 place-items-center rounded-md text-muted hover:bg-white/5 hover:text-ink lg:hidden"
          >
            <X aria-hidden className="size-4" />
          </button>
        </div>

        <div className="border-b border-hairline px-5 py-3 lg:hidden">
          <ConnectionIndicator />
        </div>

        <nav aria-label="Dashboard sections" className="flex-1 overflow-y-auto px-3 py-4">
          <ul className="space-y-1">
            {VIEWS.map((item) => {
              const Icon = ICONS[item.id];
              const active = item.id === view;
              const disabled = !project && item.id !== 'overview';
              return (
                <li key={item.id}>
                  <a
                    href={`#/${item.id}`}
                    aria-current={active ? 'page' : undefined}
                    aria-disabled={disabled || undefined}
                    onClick={(event) => {
                      event.preventDefault();
                      if (disabled) return;
                      onNavigate(item.id);
                      onClose();
                    }}
                    className={`relative flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors duration-150 ${
                      active
                        ? 'bg-raised text-ink before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-cyan'
                        : disabled
                          ? 'cursor-not-allowed text-[#52525b]'
                          : 'text-muted hover:bg-white/[0.03] hover:text-body'
                    }`}
                  >
                    <Icon aria-hidden className={`size-4 ${active ? 'text-cyan' : ''}`} />
                    <span className="flex-1">{item.label}</span>
                    {item.id === 'alerts' && typeof openAlerts === 'number' && openAlerts > 0 && (
                      <span
                        className={`tabular min-w-6 rounded-md border px-1.5 text-center font-mono text-[11px] leading-5 font-semibold ${critical ? 'border-coral/40 bg-coral/10 text-coral' : 'border-amber/40 bg-amber/10 text-amber'}`}
                      >
                        {openAlerts > 99 ? '99+' : openAlerts}
                        <span className="sr-only"> open alerts</span>
                      </span>
                    )}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-hairline p-3">
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <div
              aria-hidden
              className="grid size-8 shrink-0 place-items-center rounded-md border border-hairline-strong bg-raised font-display text-sm font-bold text-cyan"
            >
              {account.name.trim().charAt(0).toUpperCase() || '?'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-semibold text-ink">{account.name}</p>
              <p className="truncate text-xs text-muted">{account.email}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="mt-1 flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-sm font-medium text-muted transition-colors hover:bg-white/[0.03] hover:text-ink"
          >
            <LogOut aria-hidden className="size-4" />
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
