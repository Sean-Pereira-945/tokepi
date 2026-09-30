/** DriftGuard mark (same geometry as public/driftguard.svg) with the wordmark. */
export function LogoMark({ className = 'size-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden className={className}>
      <path
        d="M16 2.75 27 6.75v8.1c0 6.6-4.5 11.8-11 14.4C9.5 26.65 5 21.45 5 14.85v-8.1L16 2.75Z"
        fill="#28C7D9"
        fillOpacity="0.12"
        stroke="#28C7D9"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M9.5 16.5h3.5l2-4.5 2.75 8 2-3.5h2.75"
        stroke="#28C7D9"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark />
      <span className="font-display text-lg font-bold tracking-tight text-ink">DriftGuard</span>
    </span>
  );
}
