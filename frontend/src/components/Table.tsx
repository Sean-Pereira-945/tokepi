import type { KeyboardEvent, ReactNode } from 'react';

/** Horizontally scrollable table wrapper (tables scroll on narrow screens). */
export function TableScroll({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="overflow-x-auto" role="region" aria-label={label} tabIndex={0}>
      <table className="w-full min-w-[860px] border-collapse text-left text-[13px]">{children}</table>
    </div>
  );
}

export function Th({ children, align = 'left', className = '' }: { children?: ReactNode; align?: 'left' | 'right'; className?: string }) {
  return (
    <th
      scope="col"
      className={`sticky top-0 h-10 border-b border-hairline bg-panel px-4 text-[11px] font-semibold tracking-[0.08em] whitespace-nowrap text-muted uppercase ${align === 'right' ? 'text-right' : ''} ${className}`}
    >
      {children}
    </th>
  );
}

export function Td({ children, align = 'left', mono = false, className = '' }: { children?: ReactNode; align?: 'left' | 'right'; mono?: boolean; className?: string }) {
  return (
    <td className={`h-12 border-b border-hairline px-4 align-middle ${align === 'right' ? 'text-right' : ''} ${mono ? 'tabular font-mono' : ''} ${className}`}>
      {children}
    </td>
  );
}

/** A table row that opens a detail view on click or Enter/Space. */
export function ClickableRow({ children, onOpen, selected = false }: { children: ReactNode; onOpen: () => void; selected?: boolean }) {
  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onOpen();
    }
  };
  return (
    <tr
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={onKeyDown}
      className={`cursor-pointer transition-colors duration-150 hover:bg-raised focus-visible:bg-raised focus-visible:outline-offset-[-2px] ${selected ? 'bg-raised' : ''}`}
    >
      {children}
    </tr>
  );
}
