import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import type { StatusTone } from '../../../components/display/StatusChip';
import type { InsightTrend, TenantMlState } from '../../../api/types';
import { humanize } from '../../../utils/text';

dayjs.extend(utc);
dayjs.extend(timezone);

/**
 * Wording for baseline insights and the model status. Insights compare a machine with its own
 * history ("outside its usual range"); nothing here is a judgement about a person, and tenants are
 * never shown a model score.
 */

export const INSIGHTS_NOTICE =
  'Insights compare each machine with its own history. A value outside the usual range is a prompt to look, not a conclusion about any person.';

export const OBSERVATIONS_NOTICE =
  "Unusual machine-week patterns compared with each machine's own history, surfaced for human review on a case. They are not a conclusion about any person.";

export const ML_STATE_TONES: Readonly<Record<TenantMlState, StatusTone>> = {
  MODEL_OFF: 'default',
  NOT_ASSESSED: 'default',
  NOT_ENOUGH_HISTORY: 'warning',
  EVALUATING: 'info',
  LEARNING_SHADOW: 'info',
  ACTIVE: 'success',
};

/** Short chip text; the server `label` (with reasons) is shown in full beside it. */
export const ML_STATE_LABELS: Readonly<Record<TenantMlState, string>> = {
  MODEL_OFF: 'Model off',
  NOT_ASSESSED: 'Not assessed yet',
  NOT_ENOUGH_HISTORY: 'Not enough history yet',
  EVALUATING: 'Being evaluated',
  LEARNING_SHADOW: 'Learning (shadow)',
  ACTIVE: 'Active',
};

export const TREND_LABELS: Readonly<Record<InsightTrend, string>> = {
  UP: 'Rising',
  DOWN: 'Falling',
  FLAT: 'Steady',
};

export const TREND_TONES: Readonly<Record<InsightTrend, StatusTone>> = {
  UP: 'info',
  DOWN: 'info',
  FLAT: 'default',
};

/** Readiness minimums / observed facts (backend `SufficiencyCriteria`) in plain words. */
const READINESS_LABELS: Readonly<Record<string, string>> = {
  min_machines: 'Machines with history',
  min_machine_weeks: 'Usable machine-weeks',
  min_weeks_history: 'Weeks of history',
  min_present_fraction: 'Share of measures recorded',
  min_validation_rows: 'Machine-weeks to check the model',
  min_test_rows: 'Machine-weeks to test the model',
};

export function readinessLabel(key: string): string {
  return READINESS_LABELS[key] ?? humanize(key.replace(/^min_/, ''));
}

/** Formats a JSON fact (number, boolean, text) for a key/value list. */
export function factText(value: unknown, key = ''): string {
  if (typeof value === 'number') {
    return key.endsWith('_fraction') ? `${formatNumber(value * 100, 0)}%` : formatNumber(value, 2);
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (value === null || value === undefined) return '—';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** `12.3` (trailing zeros trimmed), `—` when absent. */
export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return value.toLocaleString('en-US', { maximumFractionDigits: digits });
}

interface HistoryFacts {
  weeks_observed: number;
  min_weeks_required: number;
  missing: readonly string[];
}

/** What INSUFFICIENT_DATA means for this item, in plain words. */
export function insufficientText(item: HistoryFacts): string {
  const weeks = `Not enough history yet: ${String(item.weeks_observed)} of ${String(
    item.min_weeks_required,
  )} weeks observed.`;
  // Server reasons are sentences: drop their own full stops so the joined text ends with exactly one.
  const missing = item.missing.map((m) => m.trim().replace(/\.+$/, ''));
  return missing.length === 0 ? weeks : `${weeks} Missing: ${missing.join('; ')}.`;
}

/** Start of a tenant-local calendar day as a UTC instant (inclusive lower bound). */
export function localDayStart(isoDate: string, tz: string): string {
  return dayjs.tz(isoDate, tz).toISOString();
}

/** Start of the day after a tenant-local calendar day (exclusive upper bound). */
export function localDayEndExclusive(isoDate: string, tz: string): string {
  return dayjs.tz(isoDate, tz).add(1, 'day').toISOString();
}

/** `Week ending 12 Oct 2026` in the display zone. */
export function weekEndingLabel(instant: string, tz: string): string {
  return `Week ending ${dayjs.utc(instant).tz(tz).format('D MMM YYYY')}`;
}
