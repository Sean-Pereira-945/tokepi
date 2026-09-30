import { X } from 'lucide-react';
import { useId, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useDialog } from '../lib/useDialog';

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button
      type="button"
      onClick={onClose}
      aria-label="Close"
      title="Close"
      className="grid size-9 shrink-0 place-items-center rounded-md text-muted transition-colors hover:bg-white/5 hover:text-ink"
    >
      <X aria-hidden className="size-4" />
    </button>
  );
}

/** Centered modal for focused actions (create project, confirmations). */
export function Modal({ open, onClose, title, description, children, footer, size = 'md' }: OverlayProps & { size?: 'md' | 'lg' }) {
  const ref = useDialog<HTMLDivElement>(open, onClose);
  const titleId = useId();
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div aria-hidden className="absolute inset-0 animate-fade bg-black/80" onClick={onClose} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`relative flex max-h-[92vh] w-full animate-rise flex-col rounded-t-lg border border-hairline-strong bg-panel shadow-2xl shadow-black sm:rounded-lg ${size === 'lg' ? 'sm:max-w-2xl' : 'sm:max-w-lg'}`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-hairline px-5 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description && <p className="mt-1 text-[13px] text-muted">{description}</p>}
          </div>
          <CloseButton onClose={onClose} />
        </header>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-hairline px-5 py-3">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}

/** Right-side drawer for inspecting a record without losing table context. */
export function Drawer({ open, onClose, title, description, children, footer }: OverlayProps) {
  const ref = useDialog<HTMLDivElement>(open, onClose);
  const titleId = useId();
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50">
      <div aria-hidden className="absolute inset-0 animate-fade bg-black/70" onClick={onClose} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="absolute inset-y-0 right-0 flex w-full max-w-xl animate-slide-in flex-col border-l border-hairline-strong bg-panel shadow-2xl shadow-black"
      >
        <header className="flex items-start justify-between gap-4 border-b border-hairline px-5 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="truncate text-lg font-semibold">
              {title}
            </h2>
            {description && <div className="mt-1 text-[13px] text-muted">{description}</div>}
          </div>
          <CloseButton onClose={onClose} />
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-hairline px-5 py-3">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
