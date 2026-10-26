import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
dayjs.extend(timezone);

/** The browser's IANA zone (fallback when the tenant zone is unknown). */
export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return 'UTC';
  }
}

/** Format a UTC ISO instant in the given IANA zone, e.g. `21 Oct 2026, 14:05:09`. */
export function formatInstantIn(
  value: string | null | undefined,
  tz: string,
  withSeconds = false,
): string {
  if (value === null || value === undefined || value === '') return '—';
  const d = dayjs.utc(value);
  if (!d.isValid()) return value;
  return d.tz(tz).format(withSeconds ? 'D MMM YYYY, HH:mm:ss' : 'D MMM YYYY, HH:mm');
}

/** The calendar day of a UTC ISO instant in the given IANA zone, e.g. `21 Oct 2026`. */
export function formatDateIn(value: string | null | undefined, tz: string): string {
  if (value === null || value === undefined || value === '') return '—';
  const d = dayjs.utc(value);
  return d.isValid() ? d.tz(tz).format('D MMM YYYY') : value;
}

/** Seconds elapsed between a UTC ISO instant and `nowMs` (never negative), or null. */
export function ageSecondsSince(value: string | null | undefined, nowMs: number): number | null {
  if (value === null || value === undefined || value === '') return null;
  const t = Date.parse(value);
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.floor((nowMs - t) / 1000));
}

/** Human age: `<1 min ago`, `12 min ago`, `3 h 5 min ago`, `4 d ago`. */
export function formatAge(seconds: number | null): string {
  if (seconds === null) return 'never';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 1) return '<1 min ago';
  if (minutes < 60) return `${String(minutes)} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    const rest = minutes % 60;
    return rest === 0 ? `${String(hours)} h ago` : `${String(hours)} h ${String(rest)} min ago`;
  }
  return `${String(Math.floor(hours / 24))} d ago`;
}

/** Duration in seconds as `2 h 05 min` / `45 min` / `30 s`. */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${String(Math.max(0, Math.round(seconds)))} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${String(minutes)} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h)} h ${String(m).padStart(2, '0')} min`;
}
