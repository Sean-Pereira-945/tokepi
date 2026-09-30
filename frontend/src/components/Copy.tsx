import { Check, Copy, TriangleAlert } from 'lucide-react';
import { useEffect, useState } from 'react';

async function writeClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for non-secure contexts (plain http on a LAN host).
    try {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(area);
      return ok;
    } catch {
      return false;
    }
  }
}

export function CopyButton({ text, label = 'Copy', compact = false }: { text: string; label?: string; compact?: boolean }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    if (state === 'idle') return;
    const timer = window.setTimeout(() => setState('idle'), 2000);
    return () => window.clearTimeout(timer);
  }, [state]);

  const onClick = async () => setState((await writeClipboard(text)) ? 'copied' : 'failed');
  const Icon = state === 'copied' ? Check : state === 'failed' ? TriangleAlert : Copy;
  const text_ = state === 'copied' ? 'Copied' : state === 'failed' ? 'Copy failed' : label;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={compact ? label : undefined}
      title={compact ? label : undefined}
      className={`inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-md border border-hairline-strong bg-raised px-2.5 text-xs font-semibold transition-colors hover:border-[#3f3f46] ${state === 'copied' ? 'text-green' : state === 'failed' ? 'text-coral' : 'text-body'}`}
    >
      <Icon aria-hidden className="size-3.5" />
      <span className={compact && state === 'idle' ? 'sr-only' : ''}>{text_}</span>
      <span aria-live="polite" className="sr-only">
        {state === 'copied' ? 'Copied to clipboard' : state === 'failed' ? 'Copy failed' : ''}
      </span>
    </button>
  );
}

export function CodeBlock({ code, title, language = 'python' }: { code: string; title?: string; language?: string }) {
  return (
    <figure className="overflow-hidden rounded-md border border-hairline bg-input">
      <figcaption className="flex items-center justify-between gap-2 border-b border-hairline px-3 py-1.5">
        <span className="font-mono text-[11px] tracking-wide text-muted uppercase">{title ?? language}</span>
        <CopyButton text={code} label={title ? `Copy ${title}` : 'Copy code'} compact />
      </figcaption>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed text-body">
        <code>{code}</code>
      </pre>
    </figure>
  );
}

/** A secret shown exactly once (new or rotated API key). */
export function OneTimeSecret({ value, label = 'API key' }: { value: string; label?: string }) {
  return (
    <div className="space-y-3">
      <div
        role="alert"
        className="flex gap-2 rounded-md border border-amber/40 bg-amber/5 px-3 py-2.5 text-[13px] text-body"
      >
        <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-amber" />
        <p>
          <strong className="text-amber">Copy this {label.toLowerCase()} now.</strong> It won’t be shown again. DriftGuard
          stores only a hash, so a lost key can’t be recovered — only rotated.
        </p>
      </div>
      <div className="flex items-center gap-2 rounded-md border border-hairline-strong bg-input p-2 pl-3">
        <code aria-label={label} className="min-w-0 flex-1 font-mono text-[13px] break-all text-cyan select-all">
          {value}
        </code>
        <CopyButton text={value} label={`Copy ${label.toLowerCase()}`} />
      </div>
    </div>
  );
}
