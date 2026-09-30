export const PROJECT_ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

export function isEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim());
}

/** Parse a numeric input. Empty → null; invalid → NaN. */
export function parseNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === '') return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}
