// localStorage can be unavailable (private mode, blocked site data), so every
// access is wrapped and failures fall back to "nothing stored".

export const STORAGE_KEYS = {
  session: 'driftguard.session',
  project: 'driftguard.project',
  filters: 'driftguard.filters',
} as const;

export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Storage is a convenience only.
  }
}

export function readJson<T>(key: string, isValid: (value: unknown) => value is T): T | null {
  const raw = readStorage(key);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return isValid(parsed) ? parsed : null;
  } catch {
    return null;
  }
}
