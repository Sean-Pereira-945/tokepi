import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';

export const inputClass =
  'block w-full min-h-10 rounded-md border border-hairline-strong bg-input px-3 text-sm text-ink placeholder:text-[#52525b] transition-colors duration-150 hover:border-[#3f3f46] focus:border-cyan focus-visible:outline-2 focus-visible:outline-cyan aria-[invalid=true]:border-coral/70 disabled:opacity-60';

interface FieldShellProps {
  label: string;
  help?: ReactNode;
  error?: string | null;
  children: (ids: { inputId: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
  className?: string;
  hideLabel?: boolean;
}

export function FieldShell({ label, help, error, children, className = '', hideLabel = false }: FieldShellProps) {
  const inputId = useId();
  const helpId = `${inputId}-help`;
  const errorId = `${inputId}-error`;
  const describedBy = [help ? helpId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined;
  return (
    <div className={className}>
      <label htmlFor={inputId} className={hideLabel ? 'sr-only' : 'mb-1.5 block text-[13px] font-semibold text-body'}>
        {label}
      </label>
      {children({ inputId, describedBy, invalid: Boolean(error) })}
      {help && (
        <p id={helpId} className="mt-1.5 text-xs text-muted">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1.5 text-xs font-medium text-coral">
          {error}
        </p>
      )}
    </div>
  );
}

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string;
  help?: ReactNode;
  error?: string | null;
  mono?: boolean;
};

export function TextField({ label, help, error, mono, className, ...input }: TextFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      {({ inputId, describedBy, invalid }) => (
        <input
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${inputClass} ${mono ? 'font-mono' : ''}`}
          {...input}
        />
      )}
    </FieldShell>
  );
}

type TextAreaFieldProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> & {
  label: string;
  help?: ReactNode;
  error?: string | null;
};

export function TextAreaField({ label, help, error, className, ...input }: TextAreaFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      {({ inputId, describedBy, invalid }) => (
        <textarea
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${inputClass} min-h-20 py-2`}
          {...input}
        />
      )}
    </FieldShell>
  );
}

type SelectFieldProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> & {
  label: string;
  help?: ReactNode;
  error?: string | null;
  options: readonly { value: string; label: string }[];
  hideLabel?: boolean;
};

export function SelectField({ label, help, error, options, className, hideLabel, ...select }: SelectFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error} className={className} hideLabel={hideLabel}>
      {({ inputId, describedBy, invalid }) => (
        <select
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${inputClass} select-chevron appearance-none pr-8`}
          {...select}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </FieldShell>
  );
}
