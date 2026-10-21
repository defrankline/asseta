export const MAX_HISTORY_DAYS = 31;
const DAY_MS = 86_400_000;

export interface HistoryRange {
  from: string;
  to: string;
}

/** Default window: the last 24 hours (UTC instants). */
export function defaultHistoryRange(nowMs: number): HistoryRange {
  return {
    from: new Date(nowMs - DAY_MS).toISOString(),
    to: new Date(nowMs).toISOString(),
  };
}

/** Client-side guard mirroring the API: to > from and at most 31 days. Null when valid. */
export function validateHistoryRange(from: string | null, to: string | null): string | null {
  if (from === null || to === null) return 'Choose both a start and an end time.';
  const f = Date.parse(from);
  const t = Date.parse(to);
  if (Number.isNaN(f) || Number.isNaN(t)) return 'Enter valid date-times.';
  if (t <= f) return 'The end must be after the start.';
  if (t - f > MAX_HISTORY_DAYS * DAY_MS) {
    return `The range can be at most ${String(MAX_HISTORY_DAYS)} days.`;
  }
  return null;
}
