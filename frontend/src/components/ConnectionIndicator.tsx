import { useWorkspace } from '../state/workspace';
import type { ConnectionState } from '../lib/useRealtime';

const META: Record<ConnectionState, { label: string; dot: string; title: string }> = {
  live: { label: 'Live', dot: 'bg-green pulse-live', title: 'Receiving alert updates in real time' },
  connecting: { label: 'Connecting', dot: 'bg-amber', title: 'Opening the realtime connection' },
  reconnecting: { label: 'Reconnecting', dot: 'bg-amber', title: 'Realtime connection lost; retrying' },
  offline: { label: 'Offline', dot: 'bg-coral', title: 'No realtime connection; use Refresh to update. Still retrying in the background.' },
  idle: { label: 'Offline', dot: 'bg-[#52525b]', title: 'No project selected' },
};

export function ConnectionIndicator() {
  const { connection } = useWorkspace();
  const meta = META[connection];
  return (
    <span
      role="status"
      title={meta.title}
      className="inline-flex h-8 items-center gap-2 rounded-md border border-hairline px-2.5 text-xs font-semibold text-body"
    >
      <span aria-hidden className={`size-2 rounded-full ${meta.dot}`} />
      <span>
        <span className="sr-only">Realtime connection: </span>
        {meta.label}
      </span>
    </span>
  );
}
