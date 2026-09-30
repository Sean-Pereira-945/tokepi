// Formatting helpers. Missing values always render as an em dash; nothing is defaulted.

export const DASH = '—';

type Maybe = number | null | undefined;

function isNum(value: Maybe): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

const intFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const compactFormat = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });

export function fmtInt(value: Maybe): string {
  return isNum(value) ? intFormat.format(value) : DASH;
}

export function fmtCompact(value: Maybe): string {
  return isNum(value) ? compactFormat.format(value) : DASH;
}

/** A 0–1 score shown with two decimals. */
export function fmtScore(value: Maybe, digits = 2): string {
  return isNum(value) ? value.toFixed(digits) : DASH;
}

export function fmtPercent(value: Maybe, digits = 0): string {
  return isNum(value) ? `${(value * 100).toFixed(digits)}%` : DASH;
}

export function fmtNumber(value: Maybe, digits = 1): string {
  return isNum(value) ? Number(value.toFixed(digits)).toLocaleString('en-US') : DASH;
}

export function fmtDuration(ms: Maybe): string {
  if (!isNum(ms)) return DASH;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${(ms / 60_000).toFixed(1)} min`;
}

export function parseTime(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

const shortTimeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' });
const shortDateFormat = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' });

export function fmtDateTime(iso: string | null | undefined): string {
  const date = parseTime(iso);
  return date ? dateTimeFormat.format(date) : DASH;
}

/** Axis tick label: time of day, or date when the span covers several days. */
export function fmtAxisTime(ms: number, spanMs: number): string {
  const date = new Date(ms);
  return spanMs > 36 * 3600_000 ? shortDateFormat.format(date) : shortTimeFormat.format(date);
}

export function fmtRelative(iso: string | null | undefined, now = Date.now()): string {
  const date = parseTime(iso);
  if (!date) return DASH;
  const seconds = Math.round((now - date.getTime()) / 1000);
  if (seconds < 0) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** `compress_prompt_context` → `Compress prompt context`. */
export function humanize(value: string | null | undefined): string {
  if (!value) return DASH;
  const text = value.replace(/_/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const TIME_RANGE_LABELS: Record<string, string> = {
  '15m': 'Last 15 minutes',
  '1h': 'Last hour',
  '24h': 'Last 24 hours',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  all: 'All time',
};
