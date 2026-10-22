import dayjs from 'dayjs';
import { isIsoDate } from '../../utils/dates';
import '../../utils/time';

/** Readable before/after rows for an audit event (no raw JSON dumps for flat records). */

export interface DiffRow {
  key: string;
  label: string;
  before: string;
  after: string;
  changed: boolean;
  /** Present on only one side (added / removed field). */
  kind: 'changed' | 'unchanged' | 'added' | 'removed';
}

/** `machine_id` → `Machine id`. */
export function fieldLabel(key: string): string {
  const words = key.replace(/[_.]+/g, ' ').trim();
  return words === '' ? key : words.charAt(0).toUpperCase() + words.slice(1);
}

export function displayValue(value: unknown): string {
  if (value === undefined || value === null || value === '') return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'bigint') return String(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.length === 0 ? '—' : value.map(displayValue).join(', ');
  return JSON.stringify(value);
}

export function diffRows(
  before: Readonly<Record<string, unknown>> | null,
  after: Readonly<Record<string, unknown>> | null,
): DiffRow[] {
  const keys = [...new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])].sort();
  return keys.map((key) => {
    const hasBefore = before !== null && key in before;
    const hasAfter = after !== null && key in after;
    const b = hasBefore ? before[key] : undefined;
    const a = hasAfter ? after[key] : undefined;
    const changed = JSON.stringify(b ?? null) !== JSON.stringify(a ?? null);
    const kind: DiffRow['kind'] =
      before === null || after === null
        ? 'unchanged'
        : !hasBefore
          ? 'added'
          : !hasAfter
            ? 'removed'
            : changed
              ? 'changed'
              : 'unchanged';
    return {
      key,
      label: fieldLabel(key),
      before: displayValue(b),
      after: displayValue(a),
      changed: before !== null && after !== null && changed,
      kind,
    };
  });
}

/** "Asseta staff under MSM-2026-0007" — actions taken by platform staff for the tenant. */
export function mandateLabel(reference: string): string {
  return `By Asseta staff under ${reference}`;
}

/** Tenant-local day boundaries as UTC instants (`to` is exclusive: the day after). */
export function periodParams(
  from: string,
  to: string,
  tz: string,
): { occurred_from?: string; occurred_to?: string } {
  const out: { occurred_from?: string; occurred_to?: string } = {};
  if (isIsoDate(from)) out.occurred_from = dayjs.tz(from, tz).startOf('day').toISOString();
  if (isIsoDate(to)) out.occurred_to = dayjs.tz(to, tz).add(1, 'day').startOf('day').toISOString();
  return out;
}
