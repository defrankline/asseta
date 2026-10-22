interface LogoProps {
  height?: number;
  /** Mark only (no wordmark), for narrow headers. */
  compact?: boolean;
}

/** Inline Asseta lockup so the wordmark follows `currentColor` (img tags cannot). */
export function Logo({ height = 32, compact = false }: LogoProps) {
  const viewWidth = compact ? 64 : 248;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${String(viewWidth)} 64`}
      height={height}
      width={(height * viewWidth) / 64}
      role="img"
      aria-label="Asseta"
    >
      <rect width="64" height="64" rx="14" fill="#0F2A3D" />
      <g fill="none" stroke="#F5A300" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 53 L26 27" />
        <path d="M38 27 L51 53" />
        <rect x="18" y="40" width="28" height="9" rx="4.5" strokeWidth="3.5" />
      </g>
      <circle cx="25" cy="44.5" r="1.8" fill="#F5A300" />
      <circle cx="32" cy="44.5" r="1.8" fill="#F5A300" />
      <circle cx="39" cy="44.5" r="1.8" fill="#F5A300" />
      <path
        d="M32 33 C29 29.5 21.5 24.5 21.5 18.5 a10.5 10.5 0 0 1 21 0 C42.5 24.5 35 29.5 32 33 Z"
        fill="#F5A300"
        stroke="#0F2A3D"
        strokeWidth="3.5"
        paintOrder="stroke"
      />
      <circle cx="32" cy="18.5" r="3.8" fill="#0F2A3D" />
      {!compact && (
        <text
          x="78"
          y="45"
          fontFamily="Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
          fontSize="36"
          fontWeight="800"
          letterSpacing="-0.5"
          fill="currentColor"
        >
          asseta
        </text>
      )}
    </svg>
  );
}
