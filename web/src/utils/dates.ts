import dayjs from 'dayjs';

/** ISO calendar date (YYYY-MM-DD) for today in the browser's zone. */
export function todayIsoDate(): string {
  return dayjs().format('YYYY-MM-DD');
}

/** Display a calendar date (YYYY-MM-DD) or an em dash for null. Dates are shown as-is (no zone shift). */
export function formatDate(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const d = dayjs(value.slice(0, 10));
  return d.isValid() ? d.format('D MMM YYYY') : value;
}

/** Display a UTC instant in the browser's zone. */
export function formatInstant(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const d = dayjs(value);
  return d.isValid() ? d.format('D MMM YYYY, HH:mm') : value;
}

export function isIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && dayjs(value).isValid();
}
