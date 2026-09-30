import { Loader2 } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';
type Size = 'md' | 'sm';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-cyan text-black border-cyan hover:bg-[#4dd6e5] hover:border-[#4dd6e5] font-semibold',
  secondary: 'bg-panel text-body border-hairline-strong hover:border-[#3f3f46] hover:bg-raised',
  danger: 'bg-coral/10 text-coral border-coral/50 hover:bg-coral/20 hover:border-coral',
  ghost: 'bg-transparent text-muted border-transparent hover:text-ink hover:bg-white/5',
};

const SIZES: Record<Size, string> = {
  md: 'min-h-10 px-3.5 text-sm gap-2',
  sm: 'min-h-8 px-2.5 text-[13px] gap-1.5',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  busy?: boolean;
}

export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  busy = false,
  disabled,
  className = '',
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={`inline-flex shrink-0 items-center justify-center rounded-md border font-medium whitespace-nowrap transition-colors duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {busy ? <Loader2 aria-hidden className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
}

/** Icon-only button: the label is both the accessible name and the tooltip. */
export function IconButton({ label, children, className = '', type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={`grid size-10 shrink-0 place-items-center rounded-md border border-hairline-strong bg-panel text-muted transition-colors duration-150 hover:border-[#3f3f46] hover:text-ink disabled:opacity-50 ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
